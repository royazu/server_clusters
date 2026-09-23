from fastapi import FastAPI
from memory import IpMemory
from cluster import GeoClusters

app = FastAPI()


@app.get("/getAll")
async def GetData():
    print(f"START: Get Data. Length: {await IpMemory.aquireTheLock(IpMemory.lengthofData)}")
    return await IpMemory.aquireTheLock(IpMemory.getData)


@app.post("/AddIp")
async def AddIp(request_data: dict):
    print("START: Add IP")
    ip = request_data.get("ipAddress")
    if await IpMemory.aquireTheLock(IpMemory.doesIpExist, ip):
        return {"success": False, "message": "IP address already exists"}
    newId = await IpMemory.aquireTheLock(IpMemory.addIpAndGeoData, request_data)
    return {
        "success": True,
        "new_id": newId,
        "data_length": await IpMemory.aquireTheLock(IpMemory.lengthofData),
    }


@app.delete("/delete/{iid}")
async def delete(iid):
    print(f"START: delete {iid}")
    if not await IpMemory.aquireTheLock(IpMemory.doesKeyExist, iid):
        return {"success": False, "message": "IP address does not exists"}
    await IpMemory.aquireTheLock(IpMemory.deleteKeyValuePair, iid)
    return {
        "success": True,
        "data_length": await IpMemory.aquireTheLock(IpMemory.lengthofData),
    }


@app.get("/generate-geo-clusters")
async def generate_geo_clusters():
    data = await IpMemory.aquireTheLock(IpMemory.getData)
    return GeoClusters.as_json(data)
