# Use an official Python runtime as a base image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install system dependencies (optional, depending on needs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose the Flask port
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
