from flask import Flask
import logging
import time

from opentelemetry import trace, metrics
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

# Setup basic Python logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup Flask app
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
LoggingInstrumentor().instrument(set_logging_format=True)

# Resource with service name for telemetry
resource = Resource(attributes={
    SERVICE_NAME: "demo-python-service"
})

# Setup tracing
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)
span_exporter = OTLPSpanExporter(endpoint="http://grafana-alloy:4318/v1/traces")
span_processor = BatchSpanProcessor(span_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Setup metrics
metric_exporter = OTLPMetricExporter(endpoint="http://grafana-alloy:4318/v1/metrics")
metric_reader = PeriodicExportingMetricReader(metric_exporter)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(__name__)

# Example counter metric
counter = meter.create_counter("example_counter")

@app.route("/")
def hello():
    logger.info("Handling request to root endpoint")
    with tracer.start_as_current_span("root-span"):
        counter.add(1)  # Increment metric on each request
        time.sleep(0.2)  # Simulate work
        return "Hello from OpenTelemetry!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

