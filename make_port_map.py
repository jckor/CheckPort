#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Make a Google Maps–geocoded Folium map that shows, per port_name,
the counts of '내항' and '외항' from a CSV (columns: port_name, in_out).

Usage (example):
  export GOOGLE_MAPS_API_KEY="AIzaSyDwYByNS_VqUTxo6kKaVuDYYxDd6yRW4RQ"
  python make_port_map.py --csv yeosu_raw_records_08.csv --region "대한민국" --out map_ports.html

Notes:
- Requires internet access and a Google Maps Geocoding API key.
- Results are cached in geocoded_ports.csv so you don't repeat geocoding.
- If a port cannot be geocoded, it will be listed in a separate CSV (geocode_failures.csv).
"""
import os
import sys
import json
import time
import argparse
import pandas as pd
import requests
import folium

def geocode_google(address, api_key, language="ko"):
    """Geocode a single address string using Google Geocoding API."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": language}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    status = data.get("status")
    if status == "OK" and data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"], data["results"][0].get("formatted_address", "")
    else:
        return None, None, None

def load_cache(cache_path):
    if os.path.exists(cache_path):
        try:
            cache = pd.read_csv(cache_path)
            # normalize
            cache['port_name'] = cache['port_name'].astype(str).str.strip()
            return cache
        except Exception:
            pass
    return pd.DataFrame(columns=["port_name", "lat", "lng", "formatted_address"])

def save_cache(cache_df, cache_path):
    cache_df.drop_duplicates(subset=["port_name"], keep="last").to_csv(cache_path, index=False, encoding="utf-8-sig")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to the source CSV (must include columns: port_name, in_out).")
    ap.add_argument("--out", default="map_ports.html", help="Output HTML for the map.")
    ap.add_argument("--cache", default="geocoded_ports.csv", help="CSV cache for geocoded results.")
    ap.add_argument("--fail", default="geocode_failures.csv", help="CSV to record ports that failed geocoding.")
    ap.add_argument("--region", default="대한민국", help="Region/country hint appended to address to improve accuracy.")
    ap.add_argument("--language", default="ko", help="Geocoding language (en/ko/...).")
    ap.add_argument("--sleep", type=float, default=0.2, help="Sleep seconds between API calls (respect rate limits).")
    args = ap.parse_args()

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        sys.exit("ERROR: Please set GOOGLE_MAPS_API_KEY environment variable.")

    df = pd.read_csv(args.csv)
    df['port_name'] = df['port_name'].astype(str).str.strip()
    df['in_out'] = df['in_out'].astype(str).str.strip()

    # Aggregate counts
    counts = df.pivot_table(index='port_name', columns='in_out', aggfunc='size', fill_value=0).reset_index()
    if '내항' not in counts.columns:
        counts['내항'] = 0
    if '외항' not in counts.columns:
        counts['외항'] = 0
    counts['총계'] = counts['내항'] + counts['외항']

    # Load cache and figure out which ports still need geocoding
    cache_df = load_cache(args.cache)
    cached_names = set(cache_df['port_name'].tolist())
    to_geo = [p for p in counts['port_name'].unique() if p not in cached_names]

    new_rows = []
    fail_rows = []
    for name in to_geo:
        # Build an address query; include region hint to bias results
        query = f"{name} 항만 {args.region}"
        lat, lng, fmt_addr = geocode_google(query, api_key, language=args.language)
        if lat is None:
            # Fallback: try without '항만'
            query = f"{name} {args.region}"
            lat, lng, fmt_addr = geocode_google(query, api_key, language=args.language)
        if lat is None:
            fail_rows.append({"port_name": name})
        else:
            new_rows.append({"port_name": name, "lat": lat, "lng": lng, "formatted_address": fmt_addr})
        time.sleep(args.sleep)

    if new_rows:
        cache_df = pd.concat([cache_df, pd.DataFrame(new_rows)], ignore_index=True)
        save_cache(cache_df, args.cache)

    if fail_rows:
        pd.DataFrame(fail_rows).to_csv(args.fail, index=False, encoding="utf-8-sig")

    # Merge counts with coordinates
    merged = counts.merge(cache_df, how="left", on="port_name")

    # Center map: use mean of known coordinates or fallback to Seoul
    center_lat = 37.5665
    center_lng = 126.9780
    if merged['lat'].notna().any():
        center_lat = merged['lat'].mean()
        center_lng = merged['lng'].mean()

    m = folium.Map(location=[center_lat, center_lng], zoom_start=7, control_scale=True)

    # Add markers
    for _, row in merged.iterrows():
        name = row['port_name']
        lat = row['lat']
        lng = row['lng']
        nei = int(row.get('내항', 0))
        wei = int(row.get('외항', 0))
        total = int(row.get('총계', 0))

        popup_html = f"""
        <b>{name}</b><br>
        내항: {nei}회<br>
        외항: {wei}회<br>
        총계: {total}회<br>
        <i>{row.get('formatted_address','')}</i>
        """
        if pd.notna(lat) and pd.notna(lng):
            folium.CircleMarker(
                location=[lat, lng],
                radius=max(5, min(20, total)),  # scale radius by volume
                tooltip=name,
                popup=folium.Popup(popup_html, max_width=300),
                fill=True
            ).add_to(m)
        else:
            # List unresolved ports in a LayerControl-less FeatureGroup so user can fix later
            folium.Marker(
                location=[center_lat, center_lng],
                tooltip=f"[좌표없음] {name}",
                popup=folium.Popup(f"{popup_html}<br><b>⚠ 좌표를 찾지 못했습니다. 캐시를 확인하세요.</b>", max_width=300),
                icon=folium.Icon(icon="info-sign")
            ).add_to(m)

    m.save(args.out)
    print(f"Map saved to: {args.out}")
    print("Tip: If some ports are misplaced or missing, edit geocoded_ports.csv to correct lat/lng and re-run.")

if __name__ == "__main__":
    main()
