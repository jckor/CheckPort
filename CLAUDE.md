# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- **Python**: 3.13.7
- **Virtual environment**: `PycharmProjects/CheckPortCongestion/.venv`
- **Platform**: Windows (WSL2)
- **IDE**: PyCharm

To activate the virtual environment:
```bash
source ~/PycharmProjects/CheckPortCongestion/.venv/bin/activate
```

Key dependencies: `pandas`, `requests`, `folium`, `numpy`

## Running Tests

```bash
cd ~/Code
python.exe -m pytest tests/ -v          # all tests (33 total)
python.exe -m pytest tests/test_fetch_vessel.py -v   # single file
```

`python.exe` refers to the Windows Python at `~/AppData/Local/Programs/Python/Python313/python.exe`. All tests mock external APIs — no real network calls are made.

Install pytest once if needed: `python.exe -m pip install pytest`

## Running Scripts

```bash
# Fetch vessel movement data (edit service_key and date range in script first)
cd ~/Code && python CheckPort.py

# Generate interactive port map
cd ~/Code
export GOOGLE_MAPS_API_KEY="your_key_here"
python make_port_map_v3.py --csv yeosu_raw_records.csv --region "대한민국" --out map_ports.html

# Fetch YGPA statistics (edit YM_FROM/YM_TO constants in script)
cd ~/Code && python ygpa_2025.py
```

## Project Structure

```
~/Code/                          # Main port analytics project
  CheckPort.py                   # Entry point — calls fetch_vessel_movements_daily()
  fetch_vessel_movements_daily.py # Core API module (Korean gov data portal)
  make_port_map.py / v2 / v3     # Folium map generators (v3 is current)
  ygpa_2025.py                   # YGPA OpenAPI statistics aggregator
  geocoded_ports.csv             # Geocoding cache (port name → lat/lng)
  yeosu_raw_records.csv          # Raw vessel movement records (output)
  daily_inout_counts.csv         # Aggregated daily stats (output)

~/PycharmProjects/CheckPortCongestion/  # Same scripts, separate virtualenv
~/PycharmProjects/LLM/microgpt.py       # Standalone minimal GPT (Karpathy-style, no ML deps)
```

## Architecture

### Port Analytics Pipeline

**1. Data Fetch** (`fetch_vessel_movements_daily.py`)
- Calls Korean government OpenAPI (`apis.data.go.kr/1192000/VsslEtrynd5/Info5`)
- Authenticates with `serviceKey` (URL-encoded), paginates at 50 records/page
- Parses XML responses, extracts `입항` (arrival) / `출항` (departure) per vessel
- Outputs: raw detail CSV + daily aggregated CSV

**2. YGPA Statistics** (`ygpa_2025.py`)
- Calls YGPA OpenAPI (`www.ygpa.or.kr:9191/openapi/service`)
- Four endpoints: berth cargo stats, item cargo stats, berth vessel stats, monthly vessel stats
- Port code for Yeosu: `PRT_AT_CODE = "620"` (YGPA) / `prtAgCd = "621"` (gov portal)
- Saves one CSV per endpoint

**3. Visualization** (`make_port_map_v3.py`)
- Takes the raw records CSV as input
- Geocodes port names via Google Maps API (with CSV cache to avoid re-querying)
- Generates `folium.CircleMarker` per port, radius scaled to vessel count
- Embeds a daily in/out table panel in the HTML output
- `GOOGLE_MAPS_API_KEY` must be set as an environment variable

### API Authentication
- **Korean gov portal**: `serviceKey` param — passed raw to `requests`, which handles URL encoding
- **YGPA**: `ServiceKey` param (capital S) — also passed as query param
- **Google Maps**: API key via `GOOGLE_MAPS_API_KEY` env var

### Key Constants to Update Per Run
- `CheckPort.py`: `service_key`, `prtAgCd`, `start_date`, `end_date`
- `ygpa_2025.py`: `SERVICE_KEY`, `YEAR`, `YM_FROM`, `YM_TO`

### Data Formats
- Date fields from Korean gov API: ISO 8601 with `+09:00` timezone suffix (e.g., `2025-08-01T17:00:00+09:00`)
- All CSVs saved with `encoding="utf-8-sig"` for Excel compatibility (Korean characters)
- Port codes are 3-digit strings

### microgpt.py
Standalone educational GPT implementation (Karpathy's "makemore"). Pure Python with custom autograd. No build/test setup — just `python microgpt.py`. Downloads `names.txt` automatically on first run.
