FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask kafka-python redis prom-client prometheus-client

COPY healthcare/ehr_ingestion_service.py /app/
COPY ai/pipelines/ /app/pipelines/

EXPOSE 8093

CMD ["python", "ehr_ingestion_service.py"]
