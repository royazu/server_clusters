import asyncio


class UserMemory:
    data = {}
    memLock = asyncio.Lock()

    @classmethod
    async def aquireTheLock(cls, func, *args):
        async with cls.memLock:
            return await func(*args)

    @classmethod
    async def exists(cls, email):
        return email in cls.data

    @classmethod
    async def add(cls, user):
        email = user["email"]
        if email in cls.data:
            return False
        cls.data[email] = {
            "email": email,
            "password": user.get("password"),
            "ip-address": user.get("ip-address"),
        }
        return True
