FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/defer_service /app/services/defer_service

RUN mkdir -p /app/runtime/deferred_cases

EXPOSE 8006

CMD ["uvicorn", "services.defer_service.app:app", "--host", "0.0.0.0", "--port", "8006"]
