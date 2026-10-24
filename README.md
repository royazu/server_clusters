# Project Coordinates

Three FastAPI services that resolve IP addresses, store their geolocation, and group nearby records into clusters. A sign-in request on Service A is published to Kafka. A separate consumer asks Service B whether that email is new.

Service A is the entry point. It validates an IP, asks Service C for coordinates, and stores the result on Service B. Service B keeps the records in memory and builds geographic clusters. Service C is the only service that calls the external geolocation providers. Sign-in does not call Service C and does not create a cluster point.

## Architecture

```
curl ──▶ Service A :8081
            │  validate IP
            ├── GET  svc-c-cont:8080/lookup/{ip}
            │         │
            │         ├── freeipapi   10 requests / 10 seconds
            │         └── ip-api       45 requests / minute
            └── POST svc-b-cont:8080/AddIp
                     │
                     ▼
              Service B :8082  (in-memory store + clusters)
              Service C :8083  (provider switch + lookup)

curl ──▶ POST Service A /signin
            │  pydantic: email, optional password, ip-address
            │  skip publish when this IP was published in the last 60 seconds
            ▼
         kafka-broker  topic user-gateway
            │
            ▼
         kafka-consumer  (group user-gateway-group)
            ├── GET  svc-b-cont:8080/user/{email}
            └── POST svc-b-cont:8080/user     only when the email is new
```

Services A, B, and C listen on port **8080**. Host ports are different so they do not collide: A is 8081, B is 8082, C is 8083. Kafka listens on **9092** inside the Docker network.

## Layout

```
servers-submission/
├── docker-compose.yml
├── ips.json                 # sample body for POST /resolve-ip-list
├── service-a/               # gateway: validate, then call C and B; POST /signin
├── service-b/               # memory, CRUD, geographic clusters, user store
├── kafka-consumer/          # user-gateway subscriber
└── service-c/
    ├── server.py            # GET /lookup/{ip}
    └── providers.py         # both providers, quotas, shared record shape
```

## Run

Docker Desktop must be running.

```powershell
docker compose up --build -d
```

`docker compose up --build` without `-d` attaches to the logs, so that terminal cannot accept more input. Press `d` to detach.

Interactive docs: [http://127.0.0.1:8081/docs](http://127.0.0.1:8081/docs), [http://127.0.0.1:8082/docs](http://127.0.0.1:8082/docs), [http://127.0.0.1:8083/docs](http://127.0.0.1:8083/docs).

On Windows, use `curl.exe`. Plain `curl` is an alias for `Invoke-WebRequest`.

## Geolocation providers

Service C keeps one Pydantic provider type. `FreeIpApi` and `IpApi` only add their URL and field mapping. Quota checks, HTTP calls, and failover are shared.

| Provider | URL | Limit |
| --- | --- | --- |
| freeipapi | `https://free.freeipapi.com/api/v1/json/{ip}` | 10 requests every 10 seconds |
| ip-api | `http://ip-api.com/json/{ip}` | 45 requests per minute |

Each lookup uses the ready provider with the most calls left in its window. ip-api starts with 45 and freeipapi with 10, so ip-api is chosen until it has fewer remaining calls than freeipapi. A provider that is closed, or whose `X-Rl` cooldown has not ended, is not a candidate. Each ip-api response prints `X-Rl` and `X-Ttl`. When `X-Rl` is `0`, ip-api is not called again for `X-Ttl` seconds.

One IP is sent to one provider. The other provider is used only when the first is out of quota or returns **400**, **403**, **429**, **500**, **503**, a timeout, or a connection error. ip-api can also answer HTTP 200 with `"status": "fail"`; that is treated as a failed lookup.

Both JSON shapes are stored as the same record: `ipAddress`, `latitude`, `longitude`, `countryName`, `cityName`, `asn`, `asnOrganization`, `isProxy`.

`POST /resolve-ip-list` looks up every address at once. The call from A to C waits up to 70 seconds so a closed rate-limit window does not become a timeout.

## Endpoints

### Service A — `http://127.0.0.1:8081`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | List every record stored on Service B |
| GET | `/resolve-ip/{ip}` | Validate one IP, look it up, store it |
| POST | `/resolve-ip-list` | JSON array of IPs; each is validated and stored the same way |
| GET | `/delete/{id}` | Delete one record by id |
| POST | `/signin` | Validate a sign-in and publish it to `user-gateway` |

A malformed IP returns **400**. `POST /signin` takes `email` (required), `password` (optional), and `ip-address` (required). A valid body returns `{"message": "your request was received"}`. The same IP is not published again for 60 seconds. An invalid body returns **422**. If Kafka rejects the publish, the response is **503**.

### Service B — `http://127.0.0.1:8082`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/getAll` | All stored records |
| POST | `/AddIp` | Store one geo record. Duplicate IPs are rejected |
| DELETE | `/delete/{id}` | Delete one record and update its cluster |
| GET | `/generate-geo-clusters` | Clusters of geographically close records |
| GET | `/user/{email}` | Whether this email is already stored |
| POST | `/user` | Write the user when the email is new |

`GET /user/{email}` returns `{"exists": true}` or `{"exists": false}`. `POST /user` returns `{"success": true, "case": "signup"}` when it writes, and `{"success": false, "case": "signin"}` when the email is already there. Users are a separate in-memory map from the IP records.

`/AddIp` is POST only. Opening it in a browser sends GET and returns `Method Not Allowed`.

### Service C — `http://127.0.0.1:8083`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/lookup/{ip}` | Pick an available provider and return the unified geo record |

## Clustering

Each new record joins the nearest cluster when its Euclidean distance to that cluster's centroid is at most **5.0** degrees of longitude and latitude. Otherwise it starts a new cluster. The centroid is the running mean and moves as records are added or deleted.

`GET /generate-geo-clusters` returns:

```json
{
  "cluster_1": {
    "median_coordinates": [lon, lat],
    "mean_coordinates": [lon, lat],
    "record_id": { "ipAddress": "...", "latitude": 0, "longitude": 0 }
  }
}
```

Memory is lost when the Service B container restarts, including users. Provider quotas reset when the Service C container restarts. Kafka logs stay in the `kafka-data` volume.

## Sign-in events

`kafka-init` creates the topic `user-gateway` (1 partition, replication factor 1) after the broker is healthy, then exits. `kafka-consumer` reads that topic as group `user-gateway-group`. The first time an email appears, the consumer logs `signup` and Service B stores `email`, `password`, and `ip-address`. A later event for the same email logs `signin` and does not write again.

Two more subscribers can read the same topic. Each needs its own group id, so it receives every event while `user-gateway-group` keeps doing signup and signin. They are examples, not extra containers.

- **Audit subscriber**, group `user-gateway-audit`. Append each event to a log: email, ip-address, offset, and time. It does not call Service B.
- **Geo subscriber**, group `user-gateway-geo`. On signup only, call `GET svc-c-cont:8080/lookup/{ip}` and `POST svc-b-cont:8080/AddIp`, so that sign-in IP joins the existing coordinate clusters.

## Examples

```powershell
curl.exe "http://127.0.0.1:8081/resolve-ip/8.8.8.8"

curl.exe -X POST "http://127.0.0.1:8081/resolve-ip-list" -H "Content-Type: application/json" --data-binary "@ips.json"

curl.exe "http://127.0.0.1:8081/"
curl.exe "http://127.0.0.1:8082/generate-geo-clusters"
curl.exe "http://127.0.0.1:8081/delete/RECORD_ID"

Set-Content -Path signin.json -Value '{"email":"a@b.com","ip-address":"8.8.8.8"}' -Encoding ascii
curl.exe -X POST "http://127.0.0.1:8081/signin" -H "Content-Type: application/json" --data-binary "@signin.json"
Set-Content -Path signin.json -Value '{"email":"a@b.com","password":"x","ip-address":"1.1.1.1"}' -Encoding ascii
curl.exe -X POST "http://127.0.0.1:8081/signin" -H "Content-Type: application/json" --data-binary "@signin.json"
docker logs kafka-consumer
curl.exe "http://127.0.0.1:8082/user/a@b.com"
```

`ips.json` must exist in the folder where you run curl. A sample file is included:

```json
["1.1.1.1", "208.67.222.222"]
```

PowerShell rewrites a JSON array typed directly on the command line, so pass the file with `--data-binary`.

## Check the provider switch

Watch Service C while calling lookup directly. The first calls print `X-Rl` and `X-Ttl` because ip-api has more room. After 36 of those, freeipapi has more room left, so the next call does not print `X-Rl`.

```powershell
docker logs -f svc-c-cont
```

```powershell
1..12 | ForEach-Object { curl.exe -s "http://127.0.0.1:8083/lookup/8.8.8.8"; Write-Host "" }
```
