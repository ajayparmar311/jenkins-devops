from flask import Flask
import logging
import time

from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.logs import LoggerProvider, LoggingHandler
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.logs_exporter import OTLPLogExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.logs.export import BatchLogProcessor

# Setup app and OpenTelemetry
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
LoggingInstrumentor().instrument()

resource = Resource(attributes={
    SERVICE_NAME: "demo-python-service"
})

# Traces
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://alloy:4318/v1/traces"))
)

# Metrics
metric_exporter = OTLPMetricExporter(endpoint="http://alloy:4318/v1/metrics")
metric_reader = PeriodicExportingMetricReader(metric_exporter)
provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
meter = provider.get_meter(__name__)
counter = meter.create_counter("example_counter")
counter.add(1)

# Logs
logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_processor(BatchLogProcessor(OTLPLogExporter(endpoint="http://alloy:4318/v1/logs")))
handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

@app.route("/")
def hello():
    logging.info("Handling request to root endpoint")
    with tracer.start_as_current_span("root-span"):
        time.sleep(0.2)
        return "Hello from OpenTelemetry!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
