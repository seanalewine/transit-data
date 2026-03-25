# AGENTS.md

## Project Overview

This is a Home Assistant app repository for collecting CTA (Chicago Transit Authority) train tracking data. The app polls the CTA Train Tracker API and stores collected data to answer specific questions about train movements.

### Goals
- Poll CTA Train Tracker API (Locations API and/or Follow This Train API)
- Store collected data
- Track train movements: when a train departs a station, what stop does it appear at next?
  - Blue line, Forest Park bound (trDr=5), departing Harlem station (stop_id=40980)
  - Red line, Howard bound (trDr=1), departing Morse station (stop_id=40100)

API Documentation: https://www.transitchicago.com/developers/ttdocs/

## Project Structure

```
transit-data/
├── cta-tracker/                  # Main app
│   ├── config.yaml               # App configuration (name, version, options, schema)
│   ├── Dockerfile                # Container build file
│   ├── rootfs/                   # Files copied into container at /
│   │   ├── etc/services.d/cta-tracker/
│   │   │   ├── run               # Service entrypoint (s6-overlay)
│   │   │   └── finish            # Service cleanup/halt handler
│   │   └── usr/bin/              # Executable scripts
│   │       └── cta_tracker.py    # Main Python data collector
│   ├── CHANGELOG.md              # Version history
│   └── README.md                 # App documentation
├── example/                      # Example app (blueprint)
├── .github/workflows/            # CI/CD pipelines
└── repository.yaml               # Repository metadata
```

## Build & Development

### Local Development
1. Comment out the `image` key in `cta-tracker/config.yaml` to build locally
2. Build the Docker image: `docker build -t cta-tracker ./cta-tracker`
3. Run locally: `docker run --rm -e CTA_API_KEY=your_key -e POLL_INTERVAL=60 cta-tracker`

### Version Bumping
When merging to main:
1. Update `version` in `cta-tracker/config.yaml`
2. Update `cta-tracker/CHANGELOG.md`
3. GitHub Actions will trigger a new build

### CI/CD
- Build workflow: `.github/workflows/build-app.yaml`
- Uses home-assistant/builder for multi-arch builds (aarch64, amd64)
- Publishes to GitHub Container Registry (ghcr.io)

## Code Conventions

### Shell Scripts
- Use `#!/usr/bin/with-contenv bashio` for service scripts
- Use `bashio::log.info`, `bashio::log.warning`, `bashio::log.error` for logging
- Access config options via `bashio::config 'key_name'`
- Use `exec` to run the main program in the `run` script

### Config Schema
- Define all user-configurable options in `config.yaml` under `options`
- Provide a `schema` for validation
- API keys should be app options, not hardcoded

### File Permissions
- Executable scripts in `rootfs/usr/bin/` should be executable
- Service scripts (`run`, `finish`) should be executable

## Key Dependencies

- **s6-overlay**: Service supervision (https://github.com/just-containers/s6-overlay)
- **bashio**: Bash helper library for Home Assistant apps
- **tempio**: Template processing tool

## Notes

- The `/share` directory is mapped for persistent storage (read/write)
- App options are accessible via bashio helpers
- The `finish` script handles service failures and can halt the container
