from fastapi import FastAPI, HTTPException

from providers import ProviderError, lookup_ip

app = FastAPI()


@app.get("/lookup/{ip}")
async def lookup(ip: str):
    try:
        return await lookup_ip(ip)
    except ProviderError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)
