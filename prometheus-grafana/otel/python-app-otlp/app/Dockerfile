FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY metrics_generator.py .
COPY rebitmqtest.py .
COPY health_metric.py .
COPY poc_metric_transform.py .

EXPOSE 5000

#ENTRYPOINT ["opentelemetry-instrument", "--logs_exporter", "otlp", "--service_name", "flask-app", "python", "metrics_generator.py"]

# Health check (optional)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["python", "poc_metric_transform.py"]
