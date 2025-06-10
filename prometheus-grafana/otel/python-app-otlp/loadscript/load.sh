#!/bin/bash

echo "Starting CPU load for 2 minutes on all available cores..."

# Duration in seconds
DURATION=120

# Spawn background jobs equal to number of CPU cores
for i in $(seq 1 "$(nproc)"); do
  timeout $DURATION bash -c "while :; do :; done" &
done

wait
echo "CPU load test completed."

