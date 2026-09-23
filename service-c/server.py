from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI()
KEYS = {
    "ipAddress", "latitude", "longitude", "countryName",
    "cityName", "asn", "asnOrganization", "isProxy",
}


@app.get("/lookup/{ip}")
async def lookup(ip: str):
    url = f"https://free.freeipapi.com/api/v1/json/{ip}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=4)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="FreeIpAPI timed out")
    if response.status_code != 200:
        raise HTTPException(
            status_code=500, detail=f"FreeIpAPI failed: {response.status_code}"
        )
    return {k: v for k, v in response.json().items() if k in KEYS}
