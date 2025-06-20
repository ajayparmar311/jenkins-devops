# health_monitor.py
import requests
import time
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics._internal.measurement import Measurement

# Configure OpenTelemetry
resource = Resource.create({
    "service.name": "flask-health-monitor",
    "service.version": "1.0",
})

# Set up metrics export to OpenTelemetry Collector
exporter = OTLPMetricExporter(endpoint="otel-collector:4317", insecure=True, timeout=30)
reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5000)
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("health.monitor")

# Create metrics
#health_status = meter.create_up_down_counter(
#    "health_status",
#    description="Health status of the Flask app (1=up, 0=down)"
#)

health_gauge = meter.create_gauge(
    name="health_status",
    description="1 if service is up, 0 if down",
    unit="1"
)

last_status = None

response_time = meter.create_histogram(
    "health_response_time",
    description="Response time of health endpoint in seconds",
    unit="s"
)
health_components = meter.create_up_down_counter(
    "health_components_status",
    description="Status of individual components (1=ok, 0=error)"
)

def get_health_status(callback_options=None):
    """Returns 1 (up) or 0 (down) for the gauge metric."""
    global last_status
    return [Measurement(1 if last_status else 0)]


def check_health():
    """Check the health endpoint and record metrics"""
    global last_status
    start_time = time.time()
    
    try:
        response = requests.get("http://flask-app:5001/health", timeout=1)
        last_status = response.ok

        duration = time.time() - start_time
        
        # Record response time
        response_time.record(duration)

        health_gauge.set(1 if response.ok else 0)

        if response.status_code == 200:
            # Health is up
            #health_status.add(1, {"app": "flask-sample"})
            
            # Record component statuses
            data = response.json()
            for component, status in data["details"].items():
                value = 1 if status == "ok" else 0
                health_components.add(value, {"component": component})
        else:
            # Health is down
            #health_status.add(0, {"app": "flask-sample"})
            
            # Record component statuses if available
            try:
                data = response.json()
                for component, status in data["details"].items():
                    value = 1 if status == "ok" else 0
                    health_components.add(value, {"component": component})
            except:
                pass
    
    except Exception as e:
        # Record failure
        #last_status = False
        health_gauge.set(0)
        #health_status.add(0, {"app": "flask-sample"})
        print(f"Health check failed: {str(e)}")

# Create a GAUGE metric (not a counter!)
#health_status = meter.create_observable_gauge(
#    name="health_status",
#    callbacks=[get_health_status],  # Called on each export
#    description="1 if service is up, 0 if down",
#    unit="1",
#)

if __name__ == "__main__":
    print("Starting health monitor...")
    while True:
        check_health()
        time.sleep(5)  # Check every 5 seconds
