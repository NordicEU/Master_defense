FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY services/quarantine_service /app/services/quarantine_service

RUN mkdir -p /app/runtime/quarantine /app/runtime/audit /app/runtime/metrics

EXPOSE 8003

CMD ["uvicorn", "services.quarantine_service.app:app", "--host", "0.0.0.0", "--port", "8003"]
