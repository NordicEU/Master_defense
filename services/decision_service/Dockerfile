FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY services/decision_service /app/services/decision_service

EXPOSE 8002

CMD ["uvicorn", "services.decision_service.app:app", "--host", "0.0.0.0", "--port", "8002"]
