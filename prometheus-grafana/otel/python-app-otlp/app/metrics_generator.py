import time
import random
import logging

from opentelemetry import metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

# ------------------ Resource Metadata ------------------ #
resource = Resource(attributes={
    "service.name": "metric-generator",
    "service.namespace": "my.sample.app",
    "environment": "dev"
})

# ------------------ Metrics Setup ------------------ #
metric_exporter = OTLPMetricExporter(endpoint="http://otel-collector:4318/v1/metrics")
reader = PeriodicExportingMetricReader(metric_exporter)
metrics_provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(metrics_provider)
meter = metrics.get_meter("my.sample.app")

request_counter = meter.create_counter("app_requests_total", description="Total requests")
error_counter = meter.create_counter("app_errors_total", description="Total errors")

# ------------------ Logging Setup ------------------ #
log_exporter = OTLPLogExporter(endpoint="http://otel-collector:4318/v1/logs")
log_processor = BatchLogRecordProcessor(log_exporter)
logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(log_processor)

# Attach OpenTelemetry logging to standard logging
otel_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logging.getLogger().addHandler(otel_handler)
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger("metric-logger")

# ------------------ App Loop ------------------ #
attributes = {"env": "dev"}

print("Generating metrics and logs... Press Ctrl+C to stop.")
try:
    while True:
        request_counter.add(1, attributes=attributes)
        logger.info("Request processed successfully")

        if random.random() < 0.2:
            error_counter.add(1, attributes=attributes)
            logger.error("⚠️ Simulated error occurred")

        time.sleep(2)

except KeyboardInterrupt:
    print("Stopped generating metrics and logs.")
