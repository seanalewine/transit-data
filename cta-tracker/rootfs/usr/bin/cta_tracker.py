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
DEBUG_FILE = "/share/cta_data/debug_info.json"

TARGET_STATIONS = {
    "blue": {"stop_id": "40980", "direction": "5", "name": "Harlem"},
    "red": {"stop_id": "40100", "direction": "1", "name": "Morse"},
}

debug_info = {
    "last_poll": None,
    "last_api_responses": {},
    "api_errors": [],
    "trains_detected": {},
    "state": {},
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
        json.dump(state, f, indent=2)


def save_debug_info():
    os.makedirs(os.path.dirname(DEBUG_FILE), exist_ok=True)
    with open(DEBUG_FILE, "w") as f:
        json.dump(debug_info, f, indent=2, default=str)


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
    fieldnames = [
        "ts", "line", "rn", "trDr",
        "from_stop", "from_stop_name",
        "to_stop", "to_stop_name",
        "locations_nextStaId", "follow_nextStop",
        "full_route"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for event in events:
        writer.writerow(event)
    return output.getvalue()


class DataHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/data":
            events = read_events()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(events, indent=2, default=str).encode("utf-8"))
        elif self.path == "/data.csv":
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
        elif self.path == "/status":
            status = {
                "last_poll": debug_info.get("last_poll"),
                "total_events": len(read_events()),
                "trains_being_tracked": len(debug_info.get("state", {})),
                "trains_detected": debug_info.get("trains_detected", {}),
                "api_errors": debug_info.get("api_errors", [])[-5:],
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status, indent=2, default=str).encode("utf-8"))
        elif self.path == "/debug":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(debug_info, indent=2, default=str).encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")


def run_server(port):
    server = HTTPServer(("0.0.0.0", port), DataHandler)
    server.serve_forever()


def fetch_train_follow(api_key, run_number):
    url = f"{API_BASE}/ttfollow.aspx?runnumber={run_number}&key={api_key}&outputType=JSON"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            ctatt = data.get("ctatt", {})
            err_cd = ctatt.get("errCd", "unknown")

            if err_cd != "0":
                return None

            etas = ctatt.get("eta", [])
            if not etas:
                return None

            if isinstance(etas, dict):
                etas = [etas]

            stops = []
            for eta in etas:
                stops.append({
                    "staId": eta.get("staId"),
                    "staNm": eta.get("staNm"),
                    "arrT": eta.get("arrT"),
                })

            return stops

    except Exception as e:
        print(f"ERROR [follow] train {run_number}: {e}")
        return None


def fetch_trains(api_key, route):
    url = f"{API_BASE}/ttpositions.aspx?rt={route}&key={api_key}&outputType=JSON"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            ctatt = data.get("ctatt", {})
            err_cd = ctatt.get("errCd", "unknown")
            err_nm = ctatt.get("errNm", "")

            if err_cd != "0":
                debug_info["api_errors"].append({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "route": route,
                    "errCd": err_cd,
                    "errNm": err_nm,
                })
                return {}
            return ctatt
    except Exception as e:
        print(f"ERROR [{route}] {e}")
        debug_info["api_errors"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "route": route,
            "error": str(e),
        })
        return {}


def process_route(api_key, route, state):
    ctatt = fetch_trains(api_key, route)
    routes = ctatt.get("route", [])

    debug_info["last_api_responses"][route] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "has_routes": bool(routes),
        "route_count": len(routes) if routes else 0,
    }

    if not routes:
        return state

    target = TARGET_STATIONS.get(route)
    if not target:
        return state

    target_id = target["stop_id"]
    trains_detected = {"total": 0, "matching_direction": 0, "at_target": 0}

    for route_data in routes:
        trains = route_data.get("train", [])
        if not trains:
            continue

        if isinstance(trains, dict):
            trains = [trains]

        trains_detected["total"] = len(trains)

        for train in trains:
            rn = train.get("rn")
            tr_dr = train.get("trDr")
            locations_next_staid = train.get("nextStaId")

            if tr_dr == target["direction"]:
                trains_detected["matching_direction"] += 1
                if locations_next_staid == target_id:
                    trains_detected["at_target"] += 1

            if not rn or tr_dr != target["direction"]:
                continue

            state_key = f"{route}_{rn}"
            prev_state = state.get(state_key, {})
            prev_has_target = prev_state.get("has_target", False)
            prev_stops = prev_state.get("stops", [])

            current_state = {"locations_nextStaId": locations_next_staid}

            if locations_next_staid == target_id:
                stops = fetch_train_follow(api_key, rn)

                if stops:
                    stop_ids = [s["staId"] for s in stops]
                    has_target = target_id in stop_ids
                    current_state["has_target"] = has_target
                    current_state["stops"] = stops

                    if prev_has_target and not has_target:
                        follow_next_stop = stops[0] if stops else None
                        event = {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "line": route,
                            "rn": rn,
                            "trDr": int(tr_dr),
                            "from_stop": target_id,
                            "from_stop_name": target["name"],
                            "to_stop": follow_next_stop["staId"] if follow_next_stop else locations_next_staid,
                            "to_stop_name": follow_next_stop["staNm"] if follow_next_stop else None,
                            "locations_nextStaId": locations_next_staid,
                            "follow_nextStop": follow_next_stop["staId"] if follow_next_stop else None,
                            "full_route": stop_ids,
                        }
                        append_event(event)
                        print(f"{event['ts']} {route} train {rn} {target['name']} -> {event['to_stop_name'] or event['to_stop']}")
                else:
                    current_state["has_target"] = False
                    current_state["stops"] = []

            elif prev_has_target:
                follow_next_stop = prev_stops[0] if prev_stops else None
                event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "line": route,
                    "rn": rn,
                    "trDr": int(tr_dr),
                    "from_stop": target_id,
                    "from_stop_name": target["name"],
                    "to_stop": follow_next_stop["staId"] if follow_next_stop else locations_next_staid,
                    "to_stop_name": follow_next_stop["staNm"] if follow_next_stop else None,
                    "locations_nextStaId": locations_next_staid,
                    "follow_nextStop": follow_next_stop["staId"] if follow_next_stop else None,
                    "full_route": [s["staId"] for s in prev_stops],
                }
                append_event(event)
                print(f"{event['ts']} {route} train {rn} {target['name']} -> {event['to_stop_name'] or event['to_stop']}")

                current_state["has_target"] = False
                current_state["stops"] = []

            state[state_key] = current_state

    debug_info["trains_detected"][route] = trains_detected
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

    print(f"CTA Train Tracker running (interval: {poll_interval}s, port: {server_port})")

    state = load_state()
    debug_info["state"] = state

    while True:
        try:
            debug_info["last_poll"] = datetime.now(timezone.utc).isoformat()

            state = process_route(api_key, "blue", state)
            state = process_route(api_key, "red", state)

            debug_info["state"] = state
            save_state(state)
            save_debug_info()
        except Exception as e:
            print(f"ERROR [main] {e}")

        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
