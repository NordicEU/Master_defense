FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY analysis/semantic_assist /app/analysis/semantic_assist

EXPOSE 8014

CMD ["uvicorn", "analysis.semantic_assist.app:app", "--host", "0.0.0.0", "--port", "8014"]
