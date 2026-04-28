FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY analysis/anomaly_scorer /app/analysis/anomaly_scorer
COPY datasets /app/datasets

EXPOSE 8012

CMD ["uvicorn", "analysis.anomaly_scorer.app:app", "--host", "0.0.0.0", "--port", "8012"]
