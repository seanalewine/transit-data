# CTA Train Tracker

Home Assistant app that collects CTA (Chicago Transit Authority) train tracking data.

## What it does

Polls the CTA Train Tracker API to monitor train movements and records when trains depart specific stations.

### Tracked routes

- **Blue Line**: Forest Park bound trains departing Harlem station (stop_id: 40980)
- **Red Line**: Howard bound trains departing Morse station (stop_id: 40100)

For each departure, it records the next stop the train appears at.

## Configuration

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | Your CTA Train Tracker API key |
| `poll_interval` | integer | No | 60 | Seconds between API polls |

## Getting an API Key

1. Visit [CTA Developer Center](https://www.transitchicago.com/developers/traintrackerapply/)
2. Complete the API key application form
3. Agree to the Developer License Agreement
4. You'll receive your API key via email

## Data Output

Data is stored in `/share/cta_data/train_movements.jsonl` as JSON Lines format:

```json
{"ts":"2026-03-25T10:30:00Z","line":"blue","rn":"830","trDr":5,"from_stop":"40980","from_stop_name":"Harlem","to_stop":"40970"}
```

### Fields

- `ts`: ISO 8601 timestamp of the event
- `line`: Route name (blue or red)
- `rn`: Train run number
- `trDr`: Train direction code
- `from_stop`: Stop ID where train departed
- `from_stop_name`: Stop name
- `to_stop`: Next stop ID where train appeared

## API Limits

The CTA Train Tracker API has a default limit of 50,000 transactions per day. With a 60-second poll interval, this app uses approximately 2,880 requests per day (well under the limit).
