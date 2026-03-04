# CheckPort

Python tools for fetching and visualizing vessel movement data from Korean port authority APIs.

## Overview

Pulls vessel arrival/departure records from the Korean government public data portal and YGPA (Yeosu-Gwangyang Port Authority) OpenAPI, aggregates them by day, and renders an interactive Folium map with traffic volume per port.

## Scripts

| Script | Purpose |
|--------|---------|
| `CheckPort.py` | Entry point — fetches vessel movements for a date range |
| `fetch_vessel_movements_daily.py` | Core API module; outputs raw records CSV + daily aggregated CSV |
| `make_port_map_v3.py` | Generates an interactive HTML map from the raw records CSV |
| `ygpa_2025.py` | Fetches cargo and vessel statistics from the YGPA OpenAPI |

## Requirements

- Python 3.13
- `pandas`, `requests`, `folium`

```bash
pip install pandas requests folium
```

## Usage

### 1. Fetch vessel movements

Edit the parameters in `CheckPort.py` (service key, port code, date range), then:

```bash
python CheckPort.py
```

Outputs:
- `yeosu_raw_records.csv` — one row per vessel movement
- `yeosu_daily_movements.csv` — arrivals/departures aggregated by day

### 2. Generate port map

```bash
export GOOGLE_MAPS_API_KEY="your_key_here"
python make_port_map_v3.py --csv yeosu_raw_records.csv --region "대한민국" --out map_ports.html
```

Opens `map_ports.html` in any browser. Circle markers are sized by vessel traffic volume; clicking shows a popup with counts.

### 3. Fetch YGPA statistics

Edit `YEAR`, `YM_FROM`, `YM_TO` constants in `ygpa_2025.py`, then:

```bash
python ygpa_2025.py
```

Outputs four CSVs: berth cargo, item cargo, berth vessel, and monthly vessel statistics.

## API Keys

| API | Where to obtain |
|-----|----------------|
| Korean gov vessel data | [data.go.kr](https://www.data.go.kr) — search for `VsslEtrynd5` |
| YGPA statistics | [ygpa.or.kr](http://www.ygpa.or.kr) — OpenAPI developer account |
| Google Maps Geocoding | [Google Cloud Console](https://console.cloud.google.com) |

## Running Tests

```bash
python.exe -m pytest tests/ -v
```

All 33 tests mock external APIs — no real network calls or API keys required.
