FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/input_app /app/apps/input_app

EXPOSE 8080

CMD ["uvicorn", "apps.input_app.app:app", "--host", "0.0.0.0", "--port", "8080"]
