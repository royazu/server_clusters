from fastapi import FastAPI
import connector

app = FastAPI()
B = "http://svc-b-cont:8080"
C = "http://svc-c-cont:8080"


async def ingest(ip):
    ip = connector.ValidateIp(ip)
    geo = await connector.MakeRequest(f"{C}/lookup/{ip}", 4, "ServiceC")
    return await connector.MakeRequest(
        f"{B}/AddIp", 8, "ServiceB-AddIp", meth="POST", JsonData=geo
    )


@app.get("/")
async def GetData():
    return await connector.MakeRequest(f"{B}/getAll", 2, "ServiceB-GetAll")


@app.get("/favicon.ico")
def favicon():
    return "ok"


@app.get("/resolve-ip/{ip}")
async def AddIp(ip: str):
    return await ingest(ip)


@app.post("/resolve-ip-list")
async def AddList(ips: list[str]):
    return [await ingest(ip) for ip in ips]


@app.get("/delete/{iid}")
async def delete(iid):
    return await connector.MakeRequest(
        f"{B}/delete/{iid}", 2, "ServiceB-Delete", meth="DELETE"
    )
