import json
from datetime import datetime, timezone
from google.cloud import pubsub_v1
from google.cloud import bigquery

PROJECT_ID = "my-kube-project-429018"
SUBSCRIPTION_ID = "otel_metrics_subscription"
BQ_DATASET = "otel_metrics"
BQ_TABLE = "otel_metrics_table"

# Initialize BigQuery client
bq_client = bigquery.Client(project=PROJECT_ID)
table_ref = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"

# Convert nanoseconds -> BigQuery TIMESTAMP
def convert_to_bq_ts(nano_str: str) -> str:
    """Convert nanoseconds to BigQuery-compatible TIMESTAMP string (UTC)."""
    ts_int = int(nano_str)
    dt = datetime.fromtimestamp(ts_int / 1e9, tz=timezone.utc)
    # BigQuery TIMESTAMP must be microsecond precision, with 'Z' suffix
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

# Prepare schema-aware rows
def parse_message(message_data: str):
    try:
        records = json.loads(message_data)

        rows = []
        for rec in records:
            rows.append({
                "store_id": rec.get("store_id"),
                "metric_name": rec.get("metric_name"),
                "timestamp": convert_to_bq_ts(rec.get("timestamp")),
                "value": float(rec["value"]) if rec.get("value") not in (None, "None", "") else None,
                "attributes": rec.get("attributes", "{}"),
                "resource": rec.get("resource", "{}"),
            })
        return rows
    except Exception as e:
        print(f"❌ Failed to parse message: {e}")
        return []

# Insert into BigQuery
def insert_to_bq(rows):
    if not rows:
        return

    errors = bq_client.insert_rows_json(table_ref, rows)
    if errors:
        print(f"❌ BigQuery insert errors: {errors}")
    else:
        print(f"✅ Inserted {len(rows)} rows into {table_ref}")

# Pub/Sub callback
def callback(message):
    print(f"📥 Received message: {message.data}")
    rows = parse_message(message.data.decode("utf-8"))
    insert_to_bq(rows)
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
