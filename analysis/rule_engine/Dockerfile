FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY analysis/rule_engine /app/analysis/rule_engine

EXPOSE 8011

CMD ["uvicorn", "analysis.rule_engine.app:app", "--host", "0.0.0.0", "--port", "8011"]
