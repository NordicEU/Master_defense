FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/business_app /app/apps/business_app

RUN mkdir -p /app/runtime/metrics

EXPOSE 8004

CMD ["uvicorn", "apps.business_app.app:app", "--host", "0.0.0.0", "--port", "8004"]
