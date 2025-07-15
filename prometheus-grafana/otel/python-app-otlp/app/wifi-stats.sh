#!/bin/bash
# Get WiFi signal strength (RSSI) in dBm
RSSI=$(iwconfig wlan0 2>/dev/null | grep 'Signal level' | awk '{print $4}' | cut -d'=' -f2)

# Get link speed in Mb/s
SPEED=$(iwconfig wlan0 2>/dev/null | grep 'Bit Rate' | awk '{print $2}' | cut -d'=' -f2)

# Output in OpenMetrics format
echo "# TYPE wifi_signal_strength gauge"
echo "wifi_signal_strength ${RSSI}"

echo "# TYPE wifi_link_speed gauge"
echo "wifi_link_speed ${SPEED}"
