import asyncio
import json
import os

import httpx
from aiokafka import AIOKafkaConsumer

B = "http://svc-b-cont:8080"


async def handle(client, event):
    email = event["email"]
    found = await client.get(f"{B}/user/{email}")
    found.raise_for_status()
    if found.json()["exists"]:
        print(f"signin {email}", flush=True)
        return
    wrote = await client.post(f"{B}/user", json=event)
    wrote.raise_for_status()
    print(f"signup {email}", flush=True)


async def main():
    consumer = AIOKafkaConsumer(
        os.environ["KAFKA_TOPIC"],
        bootstrap_servers=os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        group_id=os.environ["KAFKA_GROUP_ID"],
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    await consumer.start()
    async with httpx.AsyncClient(timeout=8) as client:
        try:
            async for msg in consumer:
                await handle(client, json.loads(msg.value))
        finally:
            await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
