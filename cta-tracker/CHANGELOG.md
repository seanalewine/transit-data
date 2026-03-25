## 1.0.0

- Initial release
- Polls CTA Train Tracker Locations API for Blue and Red lines
- Tracks train departures from Harlem (Blue, Forest Park bound) and Morse (Red, Howard bound)
- Records next stop after departure to JSONL log file
- Built-in web server serving data as CSV at `/data.csv`
- Health check endpoint at `/health`
- Status endpoint at `/status` for monitoring
- Debug endpoint at `/debug` for troubleshooting
- Detailed logging of API responses and train detection
- Configurable API key, poll interval, and server port
