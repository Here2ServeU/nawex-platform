FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask kafka-python redis prometheus-client

COPY fintech/transaction_engine.py /app/
COPY ai/pipelines/ /app/pipelines/

EXPOSE 8090

CMD ["python", "transaction_engine.py"]
