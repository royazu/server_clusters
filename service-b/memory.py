from uuid import uuid4
import asyncio
from cluster import GeoClusters


class IpMemory:
    data = {}
    UsedIps = set()
    memLock = asyncio.Lock()

    @classmethod
    async def aquireTheLock(cls, func, *args):
        async with cls.memLock:
            return await func(*args)

    @classmethod
    async def getData(cls):
        return cls.data

    @classmethod
    async def lengthofData(cls):
        return len(cls.data)

    @classmethod
    async def doesKeyExist(cls, key):
        return key in cls.data

    @classmethod
    async def doesIpExist(cls, ip):
        return ip in cls.UsedIps

    @classmethod
    async def addIpAndGeoData(cls, requestData):
        newId = str(uuid4())[:8]
        cls.data[newId] = requestData
        cls.UsedIps.add(requestData["ipAddress"])
        GeoClusters.add(newId, requestData)
        return newId

    @classmethod
    async def deleteKeyValuePair(cls, key):
        rec = cls.data.pop(key)
        cls.UsedIps.discard(rec.get("ipAddress"))
        GeoClusters.remove(key, cls.data)
