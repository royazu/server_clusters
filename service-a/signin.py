import json
import time

from aiokafka import AIOKafkaProducer
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, IPvAnyAddress

BOOTSTRAP = "kafka-broker:9092"
TOPIC = "user-gateway"
WINDOW = 60.0

recent: dict[str, float] = {}
producer: AIOKafkaProducer | None = None


class SignIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    email: EmailStr
    password: str | None = None
    ip_address: IPvAnyAddress = Field(alias="ip-address")


def allow(ip: str, now: float) -> bool:
    for key in [k for k, seen in recent.items() if now - seen >= WINDOW]:
        del recent[key]
    return ip not in recent


async def start() -> None:
    global producer
    producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP)
    await producer.start()


async def stop() -> None:
    if producer is not None:
        await producer.stop()


async def publish(body: SignIn) -> None:
    ip = str(body.ip_address)
    now = time.monotonic()
    if not allow(ip, now):
        return
    recent[ip] = now
    payload = body.model_dump(mode="json", by_alias=True)
    try:
        await producer.send_and_wait(
            TOPIC, json.dumps(payload).encode(), key=body.email.encode()
        )
    except Exception as exc:
        recent.pop(ip, None)
        raise HTTPException(status_code=503, detail=f"Kafka publish failed: {exc}")
