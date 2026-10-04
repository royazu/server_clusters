import asyncio
import time

import httpx
from pydantic import BaseModel

ERRORS = {400, 403, 429, 500, 503}


class ProviderError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail


class Geo(BaseModel):
    ipAddress: str
    latitude: float
    longitude: float
    countryName: str = ""
    cityName: str = ""
    asn: str = ""
    asnOrganization: str = ""
    isProxy: bool = False


class Provider(BaseModel):
    name: str
    limit: int
    window: float
    used: int = 0
    reset_at: float = 0.0
    cooldown_until: float = 0.0

    def _roll(self, now: float) -> None:
        if now >= self.reset_at:
            self.used = 0
            self.reset_at = now + self.window

    def ready(self, now: float) -> bool:
        self._roll(now)
        return now >= self.cooldown_until and self.used < self.limit

    def take(self, now: float) -> None:
        self._roll(now)
        self.used += 1

    def wait_left(self, now: float) -> float:
        self._roll(now)
        quota = 0.0 if self.used < self.limit else max(0.0, self.reset_at - now)
        cool = max(0.0, self.cooldown_until - now)
        return max(quota, cool)

    def url(self, ip: str) -> str:
        raise NotImplementedError

    def to_geo(self, data: dict, ip: str) -> Geo | None:
        raise NotImplementedError

    def note(self, headers, now: float) -> None:
        return


class FreeIpApi(Provider):
    name: str = "freeipapi"
    limit: int = 10
    window: float = 10

    def url(self, ip: str) -> str:
        return f"https://free.freeipapi.com/api/v1/json/{ip}"

    def to_geo(self, data: dict, ip: str) -> Geo | None:
        if "latitude" not in data or "longitude" not in data:
            return None
        return Geo(
            ipAddress=str(data.get("ipAddress") or ip),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            countryName=str(data.get("countryName") or ""),
            cityName=str(data.get("cityName") or ""),
            asn=str(data.get("asn") or ""),
            asnOrganization=str(data.get("asnOrganization") or ""),
            isProxy=bool(data.get("isProxy") or False),
        )


class IpApi(Provider):
    name: str = "ip-api"
    limit: int = 45
    window: float = 60

    def url(self, ip: str) -> str:
        return f"http://ip-api.com/json/{ip}"

    def to_geo(self, data: dict, ip: str) -> Geo | None:
        if data.get("status") == "fail" or "lat" not in data or "lon" not in data:
            return None
        asn, _, org = str(data.get("as") or "").partition(" ")
        return Geo(
            ipAddress=str(data.get("query") or ip),
            latitude=float(data["lat"]),
            longitude=float(data["lon"]),
            countryName=str(data.get("country") or ""),
            cityName=str(data.get("city") or ""),
            asn=asn,
            asnOrganization=org or str(data.get("isp") or ""),
            isProxy=False,
        )

    def note(self, headers, now: float) -> None:
        rl, ttl = headers.get("X-Rl"), headers.get("X-Ttl")
        print(f"X-Rl={rl} X-Ttl={ttl}")
        if rl == "0":
            self.cooldown_until = now + float(ttl or 0)


FREE = FreeIpApi()
PAID = IpApi()
ORDER = (FREE, PAID)
lock = asyncio.Lock()


async def _fetch(provider: Provider, ip: str, client: httpx.AsyncClient):
    try:
        response = await client.get(provider.url(ip), timeout=8)
    except httpx.TimeoutException:
        return ProviderError(504, f"{provider.name} timed out")
    except httpx.RequestError:
        return ProviderError(503, f"{provider.name} unreachable")
    now = time.monotonic()
    provider.note(response.headers, now)
    if response.status_code == 429:
        ttl = response.headers.get("X-Ttl") or response.headers.get("Retry-After")
        provider.cooldown_until = now + float(ttl or provider.window)
    if response.status_code in ERRORS or response.status_code != 200:
        return ProviderError(response.status_code, f"{provider.name} failed: {response.status_code}")
    try:
        geo = provider.to_geo(response.json(), ip)
    except (TypeError, ValueError):
        return ProviderError(500, f"{provider.name} bad json")
    return geo or ProviderError(502, f"{provider.name} lookup failed")


async def lookup_ip(ip: str) -> dict:
    skipped: set[str] = set()
    last = ProviderError(502, "lookup failed")
    async with httpx.AsyncClient() as client:
        while len(skipped) < len(ORDER):
            now = time.monotonic()
            async with lock:
                choice = next((p for p in ORDER if p.name not in skipped and p.ready(now)), None)
                if choice:
                    choice.take(now)
                else:
                    pending = [p for p in ORDER if p.name not in skipped]
                    wait = min(p.wait_left(now) for p in pending)
            if choice is None:
                await asyncio.sleep(max(wait, 0.05))
                continue
            result = await _fetch(choice, ip, client)
            if isinstance(result, Geo):
                return result.model_dump()
            skipped.add(choice.name)
            last = result
    raise last
