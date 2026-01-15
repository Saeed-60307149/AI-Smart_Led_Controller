import requests
import pandas as pd
from datetime import datetime, timedelta

# === CONFIGURATION ===
THINGSBOARD_URL = "https://demo.thingsboard.io"   # or your local IP, e.g. "http://192.168.1.100:8080"
DEVICE_TOKEN = "YOUR_THINGSBOARD_DEVICE_TOKEN"   # from TB device

# Telemetry keys (must match your telemetry names in ThingsBoard)
TELEMETRY_KEYS = ["ldr", "motion", "led"]

# Time range: last 3 days
end_ts = int(datetime.now().timestamp() * 1000)
start_ts = int((datetime.now() - timedelta(days=3)).timestamp() * 1000)

def fetch_telemetry(key):
    """
    Fetch telemetry data for a specific key from ThingsBoard.
    """
    url = f"{THINGSBOARD_URL}/api/v1/{DEVICE_TOKEN}/telemetry"
    params = {
        "keys": key,
        "startTs": start_ts,
        "endTs": end_ts
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()

    if key not in data:
        print(f"⚠ No data for key '{key}'")
        return pd.DataFrame(columns=["ts", key])

    df = pd.DataFrame(data[key])
    df["value"] = pd.to_numeric(df["value"], errors='coerce')
    df.rename(columns={"value": key}, inplace=True)
    df["ts"] = pd.to_datetime(df["ts"], unit='ms')
    return df[["ts", key]]

# === FETCH ALL TELEMETRY KEYS ===
dfs = []
for key in TELEMETRY_KEYS:
    try:
        df = fetch_telemetry(key)
        dfs.append(df)
        print(f"✓ Fetched {len(df)} records for '{key}'")
    except Exception as e:
        print(f"✗ Error fetching '{key}': {e}")

# === MERGE ALL INTO ONE DATAFRAME ===
if len(dfs) == 0:
    print("\n✗ No telemetry data downloaded! Check your ThingsBoard credentials and device ID.")
    exit(1)

merged = dfs[0]
for df in dfs[1:]:
    merged = pd.merge_asof(merged.sort_values("ts"), df.sort_values("ts"), on="ts", tolerance=pd.Timedelta('5s'))

# === SAVE TO CSV ===
output_path = "../data/thingsboard_history.csv"
merged.to_csv(output_path, index=False)
print(f"\n✓ Saved telemetry data to {output_path}")