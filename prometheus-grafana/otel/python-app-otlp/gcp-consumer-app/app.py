import json
from datetime import datetime, timezone
from google.cloud import pubsub_v1
from google.cloud import bigquery

PROJECT_ID = os.getenv("PROJECT_ID", "np-store-sim")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID", "otel_metrics_subscription")
BQ_DATASET = os.getenv("BQ_DATASET", "otel_metrics")
METRIC_TABLE = os.getenv("METRIC_TABLE", "otel_metrics_table")
LOG_TABLE = os.getenv("LOG_TABLE", "otel_logs_table")

# Two tables: one for metrics, one for logs
BQ_TABLE_METRICS = f"{PROJECT_ID}.{BQ_DATASET}.{METRIC_TABLE}"
BQ_TABLE_LOGS = f"{PROJECT_ID}.{BQ_DATASET}.{LOG_TABLE}"

# Initialize BigQuery client
bq_client = bigquery.Client(project=PROJECT_ID)

# Convert nanoseconds -> BigQuery TIMESTAMP
def convert_to_bq_ts(nano_str: str) -> str:
    """Convert nanoseconds to BigQuery-compatible TIMESTAMP string (UTC)."""
    ts_int = int(nano_str)
    dt = datetime.fromtimestamp(ts_int / 1e9, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

# Prepare schema-aware rows
def parse_message(message_data: str):
    try:
        records = json.loads(message_data)

        # If it's a single dict, wrap in list
        if isinstance(records, dict):
            records = [records]

        metric_rows, log_rows = [], []

        for rec in records:
            if rec.get("metric_name"):  # Metrics
                metric_rows.append({
                    "store_id": rec.get("store_id"),
                    "metric_name": rec.get("metric_name"),
                    "timestamp": convert_to_bq_ts(rec.get("timestamp")),
                    "value": float(rec["value"]) if rec.get("value") not in (None, "None", "") else None,
                    "attributes": rec.get("attributes", "{}"),
                    "resource": rec.get("resource", "{}"),
                })
            else:  # Logs
                log_rows.append({
                    "store_id": rec.get("store_id"),
                    "timestamp": rec.get("timestamp"),
                    "app_info": rec.get("app_info"),
                    "message_id": rec.get("message_id"),
                    "event": rec.get("event"),
                    "event_value": rec.get("event_value"),
                    "insert_id": rec.get("insert_id")
                })

        return metric_rows, log_rows

    except Exception as e:
        print(f"❌ Failed to parse message: {e}")
        return [], []

# Insert into BigQuery
def insert_to_bq(rows, table_ref):
    if not rows:
        return

    errors = bq_client.insert_rows_json(table_ref, rows)
    if errors:
        print(f"❌ BigQuery insert errors into {table_ref}: {errors}")
    else:
        print(f"✅ Inserted {len(rows)} rows into {table_ref}")

# Pub/Sub callback
def callback(message):
    print(f"📥 Received message: {message.data}")
    metric_rows, log_rows = parse_message(message.data.decode("utf-8"))

    if metric_rows:
        insert_to_bq(metric_rows, BQ_TABLE_METRICS)
    if log_rows:
        insert_to_bq(log_rows, BQ_TABLE_LOGS)

    message.ack()

def main():
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    print(f"🚀 Listening for messages on {subscription_path}...")

    try:
        streaming_pull_future.result()
    except KeyboardInterrupt:
        streaming_pull_future.cancel()

if __name__ == "__main__":
    main()
