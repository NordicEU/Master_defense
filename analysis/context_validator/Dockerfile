FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY analysis/context_validator /app/analysis/context_validator

EXPOSE 8013

CMD ["uvicorn", "analysis.context_validator.app:app", "--host", "0.0.0.0", "--port", "8013"]
