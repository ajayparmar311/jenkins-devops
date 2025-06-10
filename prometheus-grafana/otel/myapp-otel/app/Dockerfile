# Use an official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose port
EXPOSE 5000

# Use entrypoint to run OpenTelemetry auto-instrumentation
ENTRYPOINT ["opentelemetry-instrument", "--service_name", "flask-app", "python", "app.py"]

