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
    print(f"Web server started on port {port}")
    server.serve_forever()


def fetch_trains(api_key, route):
    url = f"{API_BASE}/ttpositions.aspx?rt={route}&key={api_key}&outputType=JSON"
    try:
        print(f"[{route.upper()}] Fetching from API...")
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            ctatt = data.get("ctatt", {})
            err_cd = ctatt.get("errCd", "unknown")
            err_nm = ctatt.get("errNm", "")
            print(f"[{route.upper()}] API response: errCd={err_cd}, errNm={err_nm}")
            if err_cd != "0":
                error_msg = f"{route}: API error {err_cd} - {err_nm}"
                print(f"[{route.upper()}] {error_msg}")
                debug_info["api_errors"].append({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "route": route,
                    "errCd": err_cd,
                    "errNm": err_nm,
                })
                return {}
            return ctatt
    except urllib.error.URLError as e:
        error_msg = f"{route}: URL error - {e}"
        print(f"[{route.upper()}] {error_msg}")
        debug_info["api_errors"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "route": route,
            "error": str(e),
        })
        return {}
    except json.JSONDecodeError as e:
        error_msg = f"{route}: JSON decode error - {e}"
        print(f"[{route.upper()}] {error_msg}")
        debug_info["api_errors"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "route": route,
            "error": f"JSON decode: {e}",
        })
        return {}
    except TimeoutError:
        error_msg = f"{route}: Request timeout"
        print(f"[{route.upper()}] {error_msg}")
        debug_info["api_errors"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "route": route,
            "error": "Timeout",
        })
        return {}
    except Exception as e:
        error_msg = f"{route}: Unexpected error - {e}"
        print(f"[{route.upper()}] {error_msg}")
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
        print(f"[{route.upper()}] No routes in response")
        return state

    target = TARGET_STATIONS.get(route)
    if not target:
        print(f"[{route.upper()}] No target station configured")
        return state

    trains_detected = {"total": 0, "matching_direction": 0, "at_target": 0}

    for route_data in routes:
        trains = route_data.get("train", [])
        if not trains:
            print(f"[{route.upper()}] No trains in route data")
            continue

        if isinstance(trains, dict):
            trains = [trains]

        trains_detected["total"] = len(trains)
        print(f"[{route.upper()}] Found {len(trains)} train(s)")

        for train in trains:
            rn = train.get("rn")
            tr_dr = train.get("trDr")
            next_stop_id = train.get("nextStapId")
            dest_nm = train.get("destNm", "unknown")

            trains_detected["total"] += 1
            
            if tr_dr == target["direction"]:
                trains_detected["matching_direction"] += 1
                print(f"[{route.upper()}] Train {rn}: trDr={tr_dr}, nextStapId={next_stop_id}, dest={dest_nm}")
                
                if next_stop_id == target["stop_id"]:
                    trains_detected["at_target"] += 1
                    print(f"[{route.upper()}] Train {rn} is AT target station {target['name']}")

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
                print(f"[{route.upper()}] LOGGED: Train {rn} departed {target['name']} -> {next_stop_id}")

            if next_stop_id:
                state[state_key] = next_stop_id

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

    print(f"Starting CTA Train Tracker (poll interval: {poll_interval}s, port: {server_port})")
    print(f"Target stations:")
    print(f"  Blue Line: Harlem (stop_id=40980), Forest Park bound (trDr=5)")
    print(f"  Red Line: Morse (stop_id=40100), Howard bound (trDr=1)")
    
    state = load_state()
    debug_info["state"] = state

    while True:
        try:
            debug_info["last_poll"] = datetime.now(timezone.utc).isoformat()
            print(f"\n--- Poll at {debug_info['last_poll']} ---")
            
            state = process_route(api_key, "blue", state)
            state = process_route(api_key, "red", state)
            
            debug_info["state"] = state
            save_state(state)
            save_debug_info()
            
            print(f"State now tracking {len(state)} train(s)")
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
