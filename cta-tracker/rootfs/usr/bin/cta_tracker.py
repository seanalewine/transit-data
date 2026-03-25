#!/usr/bin/env python3
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

API_BASE = "https://lapi.transitchicago.com/api/1.0"
DATA_FILE = "/share/cta_data/train_movements.jsonl"
STATE_FILE = "/share/cta_data/train_state.json"

TARGET_STATIONS = {
    "blue": {"stop_id": "40980", "direction": "5", "name": "Harlem"},
    "red": {"stop_id": "40100", "direction": "1", "name": "Morse"},
}


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def append_event(event):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def fetch_trains(api_key, route):
    url = f"{API_BASE}/ttpositions.aspx?rt={route}&key={api_key}&outputType=JSON"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("ctatt", {})
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"Error fetching {route} line: {e}")
        return {}


def process_route(api_key, route, state):
    ctatt = fetch_trains(api_key, route)
    routes = ctatt.get("route", [])
    if not routes:
        return state

    target = TARGET_STATIONS.get(route)
    if not target:
        return state

    for route_data in routes:
        trains = route_data.get("train", [])
        if not trains:
            continue

        if isinstance(trains, dict):
            trains = [trains]

        for train in trains:
            rn = train.get("rn")
            tr_dr = train.get("trDr")
            next_stop_id = train.get("nextStapId")

            if not rn or tr_dr != target["direction"]:
                continue

            state_key = f"{route}_{rn}"
            prev_stop = state.get(state_key)

            if prev_stop == target["stop_id"] and next_stop_id and next_stop_id != target["stop_id"]:
                event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "line": route,
                    "rn": rn,
                    "trDr": int(tr_dr),
                    "from_stop": target["stop_id"],
                    "from_stop_name": target["name"],
                    "to_stop": next_stop_id,
                }
                append_event(event)
                print(f"Logged: {route} line train {rn} departed {target['name']} -> {next_stop_id}")

            if next_stop_id:
                state[state_key] = next_stop_id

    return state


def main():
    api_key = os.environ.get("CTA_API_KEY", "")
    poll_interval = int(os.environ.get("POLL_INTERVAL", "60"))

    if not api_key:
        print("ERROR: CTA_API_KEY environment variable not set")
        return 1

    print(f"Starting CTA Train Tracker (poll interval: {poll_interval}s)")
    state = load_state()

    while True:
        try:
            state = process_route(api_key, "blue", state)
            state = process_route(api_key, "red", state)
            save_state(state)
        except Exception as e:
            print(f"Error in main loop: {e}")

        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
