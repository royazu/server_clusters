import httpx
from pydantic import BaseModel, IPvAnyAddress
from fastapi import HTTPException


class ValidIpDTO(BaseModel):
    ip: IPvAnyAddress


def ValidateIp(ip: str):
    try:
        validated = ValidIpDTO(ip=ip)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    print("validation passed: ", validated.ip)
    return validated.ip


async def MakeRequest(url, tout, svsName, meth="GET", JsonData=None):
    async with httpx.AsyncClient() as client:
        HttpMethod, kwargs = client.get, {"timeout": tout}
        if meth == "POST":
            HttpMethod, kwargs["json"] = client.post, JsonData
        if meth == "DELETE":
            HttpMethod = client.delete
        try:
            response = await HttpMethod(url, **kwargs)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail=f"{svsName} timed out")
    if response.status_code != 200:
        raise HTTPException(
            status_code=500, detail=f"{svsName} failed: {response.status_code}"
        )
    return response.json()
