# CTA Train Tracker

Home Assistant app that collects CTA (Chicago Transit Authority) train tracking data.

## What it does

Polls the CTA Train Tracker API to monitor train movements and records when trains depart specific stations. Serves collected data via a built-in web server.

### Tracked routes

- **Blue Line**: Forest Park bound trains departing Harlem station (stop_id: 40980)
- **Red Line**: Howard bound trains departing Morse station (stop_id: 40100)

For each departure, it records the next stop the train appears at.

## Configuration

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | Your CTA Train Tracker API key |
| `poll_interval` | integer | No | 60 | Seconds between API polls |
| `server_port` | integer | No | 8080 | Port for the web server |

## Web Server

The app runs a web server that serves the collected data:

| Endpoint | Description |
|----------|-------------|
| `/` or `/data` | Train movements as JSON |
| `/data.csv` | Train movements as CSV download |
| `/health` | Health check (returns "OK") |
| `/status` | Poll status and error summary |
| `/debug` | Full debug info |

Access the data at `http://<your-home-assistant-ip>:8080/data.csv`

## Troubleshooting

If no data is appearing:

1. Check `/status` endpoint - shows if API calls are succeeding
2. Check `/debug` endpoint - shows raw API responses and any errors
3. Verify API key is correct in configuration
4. Note: Events are only logged when a train **departs** the target station. A train must first be detected at Harlem/Morse, then detected at a different station on the next poll.

## Getting an API Key

1. Visit [CTA Developer Center](https://www.transitchicago.com/developers/traintrackerapply/)
2. Complete the API key application form
3. Agree to the Developer License Agreement
4. You'll receive your API key via email

## Data Output

Data is stored in `/share/cta_data/train_movements.jsonl` as JSON Lines format and served via the web server as JSON.

### JSON Format

```json
{
  "ts": "2026-03-25T20:32:23.752476+00:00",
  "line": "red",
  "rn": "825",
  "trDr": 1,
  "from_stop": "40100",
  "from_stop_name": "Morse",
  "to_stop": "41190",
  "to_stop_name": "Jarvis",
  "locations_nextStaId": "40900",
  "follow_nextStop": "41190",
  "full_route": ["41190", "40900"]
}
```

### Fields

- `ts`: ISO 8601 timestamp of the event
- `line`: Route name (blue or red)
- `rn`: Train run number
- `trDr`: Train direction code
- `from_stop`: Stop ID where train departed
- `from_stop_name`: Stop name
- `to_stop`: True next stop ID (from Follow This Train API)
- `to_stop_name`: True next stop name
- `locations_nextStaId`: What Locations API reported as next stop
- `follow_nextStop`: What Follow This Train API reported as next stop
- `full_route`: Array of all upcoming stop IDs

### Verification

If `locations_nextStaId` differs from `to_stop`, this indicates the Locations API returned an incorrect next stop (e.g., showing Howard instead of Jarvis).

## API Limits

The CTA Train Tracker API has a default limit of 50,000 transactions per day. With a 60-second poll interval, this app uses approximately 2,880 requests per day (well under the limit).
