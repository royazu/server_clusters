# Project Coordinates

Three FastAPI services that resolve IP addresses, store their geolocation, and group nearby records into clusters.

Service A is the entry point. It validates an IP, asks Service C for coordinates, and stores the result on Service B. Service B keeps the records in memory and builds geographic clusters. Service C is the only service that calls the external geolocation API.

## Architecture

```
curl ──▶ Service A :8081
            │  validate IP
            ├── GET  svc-c-cont:8080/lookup/{ip}
            └── POST svc-b-cont:8080/AddIp
                     │
                     ▼
              Service B :8082  (in-memory store + clusters)
              Service C :8083  (freeipapi lookup)
```

Every container listens on port **8080**. Host ports are different so they do not collide: A is 8081, B is 8082, C is 8083.

## Layout

```
servers-submission/
├── docker-compose.yml
├── ips.json                 # sample body for POST /resolve-ip-list
├── service-a/               # gateway: validate, then call C and B
├── service-b/               # memory, CRUD, geographic clusters
└── service-c/               # freeipapi lookup
```

## Run

Docker Desktop must be running.

```powershell
docker compose up --build
```

That command attaches to the logs, so the terminal cannot accept more input. Press `d` to detach, or start in the background:

```powershell
docker compose up --build -d
```

Interactive docs: [http://127.0.0.1:8081/docs](http://127.0.0.1:8081/docs), [http://127.0.0.1:8082/docs](http://127.0.0.1:8082/docs), [http://127.0.0.1:8083/docs](http://127.0.0.1:8083/docs).

On Windows, use `curl.exe`. Plain `curl` is an alias for `Invoke-WebRequest`.

## Endpoints

### Service A — `http://127.0.0.1:8081`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | List every record stored on Service B |
| GET | `/resolve-ip/{ip}` | Validate one IP, look it up, store it |
| POST | `/resolve-ip-list` | JSON array of IPs; each is validated and stored the same way |
| GET | `/delete/{id}` | Delete one record by id |

A malformed IP returns **400**.

### Service B — `http://127.0.0.1:8082`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/getAll` | All stored records |
| POST | `/AddIp` | Store one geo record. Duplicate IPs are rejected |
| DELETE | `/delete/{id}` | Delete one record and update its cluster |
| GET | `/generate-geo-clusters` | Clusters of geographically close records |

`/AddIp` is POST only. Opening it in a browser sends GET and returns `Method Not Allowed`.

### Service C — `http://127.0.0.1:8083`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/lookup/{ip}` | Call freeipapi and return latitude, longitude, country, city, ASN, and proxy flag |

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

Memory is lost when the Service B container restarts.

## Examples

```powershell
curl.exe "http://127.0.0.1:8081/resolve-ip/8.8.8.8"

curl.exe -X POST "http://127.0.0.1:8081/resolve-ip-list" -H "Content-Type: application/json" --data-binary "@ips.json"

curl.exe "http://127.0.0.1:8081/"
curl.exe "http://127.0.0.1:8082/generate-geo-clusters"
curl.exe "http://127.0.0.1:8081/delete/RECORD_ID"
```

`ips.json` must exist in the folder where you run curl. A sample file is included:

```json
["1.1.1.1", "208.67.222.222"]
```

PowerShell rewrites a JSON array typed directly on the command line, so pass the file with `--data-binary`.
