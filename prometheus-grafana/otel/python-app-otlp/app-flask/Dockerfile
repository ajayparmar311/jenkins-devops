FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5001

#ENTRYPOINT ["opentelemetry-instrument", "--logs_exporter", "otlp", "--service_name", "flask-app", "python", "metrics_generator.py"]

CMD ["python", "app.py"]
