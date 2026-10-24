import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
import connector
import signin


@asynccontextmanager
async def lifespan(_app):
    await signin.start()
    yield
    await signin.stop()


app = FastAPI(lifespan=lifespan)
B = "http://svc-b-cont:8080"
C = "http://svc-c-cont:8080"


async def ingest(ip):
    ip = connector.ValidateIp(ip)
    geo = await connector.MakeRequest(f"{C}/lookup/{ip}", 70, "ServiceC")
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
    return list(await asyncio.gather(*(ingest(ip) for ip in ips)))


@app.post("/signin")
async def sign_in(body: signin.SignIn):
    await signin.publish(body)
    return {"message": "your request was received"}


@app.get("/delete/{iid}")
async def delete(iid):
    return await connector.MakeRequest(
        f"{B}/delete/{iid}", 2, "ServiceB-Delete", meth="DELETE"
    )
