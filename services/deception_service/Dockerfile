FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/deception_service /app/services/deception_service

RUN mkdir -p /app/runtime/deception_cases

EXPOSE 8007

CMD ["uvicorn", "services.deception_service.app:app", "--host", "0.0.0.0", "--port", "8007"]
