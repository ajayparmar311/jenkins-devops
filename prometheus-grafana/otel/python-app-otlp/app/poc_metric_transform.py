from fastapi import FastAPI, HTTPException, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel
import logging
import time
from typing import Optional
import uvicorn
import re

app = FastAPI()

# ========== MODELS ==========
# class AppInfo(BaseModel):
#     app_name: str
#     filter_type: str
#     store_id: str

class LogData(BaseModel):
    app_info: str
    message_id: str
    event: str
    event_value: str
    timestamp: Optional[str] = None
    duration_ms: Optional[int] = None
    user_id: Optional[str] = None

# ========== METRICS DEFINITION ==========
EVENT_COUNTER = Counter(
    'app_events_total',
    'Total count of application events by type and value',
    ['app_name', 'store', 'filter_type', 'error_type','cam_id']
)

ERROR_COUNTER = Counter(
    'app_errors_total',
    'Total count of application errors',
    ['app_name', 'store', 'filter_type', 'error']
)

REQUEST_LATENCY = Histogram(
    'api_request_duration_ms',
    'Duration of API requests in milliseconds',
    ['app_name', 'store', 'filter_type', 'status'],
    buckets=[50, 100, 200, 500, 1000, 2000]
)

ACTIVE_APPS = Gauge(
    'active_applications',
    'Number of active applications sending logs',
    ['app_name', 'store', 'filter_type']
)

LAST_EVENT_TIMESTAMP = Gauge(
    'app_last_event_timestamp',
    'Timestamp of last received event per application',
    ['app_name', 'store', 'filter_type']
)

# ========== HELPER FUNCTIONS ==========
def record_metrics(log_data: LogData):
    """Extract and record metrics from log data"""
    labels = {
        'app_name': log_data.app_info,
        'store' : '1111',
    }
    
    # Count all events
    if log_data.message_id in 'LOG_ERROR':
      match = re.search(r":\s*(\d+)", log_data.event_value)
      extracted_number = match.group(1) if match else None
      logging.info(f"message contain: {log_data.message_id} : CAM_ID : {extracted_number}")
      
      EVENT_COUNTER.labels(
          **labels,
          filter_type=log_data.message_id,
          error_type=log_data.event,
          cam_id=extracted_number
      ).inc()
      
    
    # # Track active applications
    # ACTIVE_APPS.labels(**labels).set(1)
    # LAST_EVENT_TIMESTAMP.labels(**labels).set_to_current_time()
    
    # # Special handling for API requests
    # if log_data.event == 'API_REQUEST':
    #     duration = log_data.duration_ms or 0
    #     REQUEST_LATENCY.labels(
    #         **labels,
    #         status=log_data.event_value
    #     ).observe(duration)
        
    #     if 'error' in log_data.event_value:
    #         ERROR_COUNTER.labels(
    #             **labels,
    #             error_type=log_data.event_value
    #         ).inc()

# ========== API ENDPOINTS ==========
@app.post("/log")
async def handle_log(log_data: LogData):
    """Endpoint for receiving application logs"""
    try:
        # Add timestamp if not provided
        if not log_data.timestamp:
            log_data.timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Process the log and record metrics
        record_metrics(log_data)
        
        # In production, you would store the log here
        logging.info(f"Received log: {log_data.message_id}")
        
        return {
            "status": "success",
            "message_id": log_data.message_id,
            "processed_at": time.time()
        }
    except Exception as e:
        logging.error(f"Error processing log: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

# ========== MAIN ==========
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_config=None  # Use default logging config
    )
