FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir aiokafka httpx
COPY *.py .
ENTRYPOINT ["python", "consumer.py"]
