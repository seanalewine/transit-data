## 1.0.0

- Initial release
- Polls CTA Train Tracker Locations API for Blue and Red lines
- Uses Follow This Train API to verify true next stops
- Tracks train departures from Harlem (Blue, Forest Park bound) and Morse (Red, Howard bound)
- Records next stop after departure to JSONL log file
- Built-in web server serving data as JSON and CSV
- Includes verification fields (`locations_nextStaId`, `follow_nextStop`) to compare API responses
- Health check endpoint at `/health`
- Status endpoint at `/status` for monitoring
- Debug endpoint at `/debug` for troubleshooting
- Configurable API key, poll interval, and server port
