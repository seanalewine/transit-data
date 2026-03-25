#!/usr/bin/env python3
import csv
import io
import json
import os
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

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


def read_events():
    if not os.path.exists(DATA_FILE):
        return []
    events = []
    try:
        with open(DATA_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except (IOError, json.JSONDecodeError):
        pass
    return events


def events_to_csv(events):
    if not events:
        return ""
    output = io.StringIO()
    fieldnames = ["ts", "line", "rn", "trDr", "from_stop", "from_stop_name", "to_stop"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for event in events:
        writer.writerow(event)
    return output.getvalue()


class DataHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/data.csv":
            events = read_events()
            csv_data = events_to_csv(events)
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", "attachment; filename=train_movements.csv")
            self.end_headers()
            self.wfile.write(csv_data.encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")


def run_server(port):
    server = HTTPServer(("0.0.0.0", port), DataHandler)
    print(f"Web server started on port {port}")
    server.serve_forever()


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
    server_port = int(os.environ.get("SERVER_PORT", "8080"))

    if not api_key:
        print("ERROR: CTA_API_KEY environment variable not set")
        return 1

    server_thread = threading.Thread(target=run_server, args=(server_port,), daemon=True)
    server_thread.start()

    print(f"Starting CTA Train Tracker (poll interval: {poll_interval}s, port: {server_port})")
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
