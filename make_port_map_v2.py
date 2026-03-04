#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced port map generator.

Adds:
- Month label overlay (auto from 'date' or via --month_label)
- Thousand separators for counts in popups
- Daily in/out table saved to CSV and embedded in the Folium map

Usage:
  export GOOGLE_MAPS_API_KEY="AIzaSyDwYByNS_VqUTxo6kKaVuDYYxDd6yRW4RQ"
  python make_port_map_v2.py --csv yeosu_raw_records_08.csv --region "대한민국" --out map_ports.html
"""
import os
import sys
import time
import argparse
import pandas as pd
import requests
import folium

def geocode_google(address, api_key, language="ko"):
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
            cache['port_name'] = cache['port_name'].astype(str).str.strip()
            return cache
        except Exception:
            pass
    return pd.DataFrame(columns=["port_name", "lat", "lng", "formatted_address"])

def save_cache(cache_df, cache_path):
    cache_df.drop_duplicates(subset=["port_name"], keep="last").to_csv(cache_path, index=False, encoding="utf-8-sig")

def build_daily_table(df):
    # Expect columns: date, in_out
    df = df.copy()
    df['date'] = pd.to_datetime(df['date']).dt.date
    df['in_out'] = df['in_out'].astype(str).str.strip()
    day_pivot = df.pivot_table(index='date', columns='in_out', aggfunc='size', fill_value=0).reset_index()
    if '내항' not in day_pivot.columns:
        day_pivot['내항'] = 0
    if '외항' not in day_pivot.columns:
        day_pivot['외항'] = 0
    day_pivot['총계'] = day_pivot['내항'] + day_pivot['외항']
    show = day_pivot.copy()
    for c in ['내항', '외항', '총계']:
        show[c] = show[c].map(lambda x: f"{int(x):,}")
    return day_pivot, show

def add_month_label(m, text):
    html = f"""
    <div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
                background: rgba(255,255,255,0.9); padding: 6px 12px; border-radius: 8px;
                font-weight: 600; font-size: 16px; z-index: 9999; box-shadow: 0 2px 6px rgba(0,0,0,0.2);">
        {text}
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))

def add_table_panel(m, html_table, title="일별 입항/출항 현황"):
    panel = f"""
    <div style="position: fixed; bottom: 12px; right: 12px; max-height: 45%; width: 420px; overflow: auto;
                background: rgba(255,255,255,0.95); padding: 10px 10px 12px; border-radius: 10px;
                z-index: 9999; box-shadow: 0 3px 10px rgba(0,0,0,0.25);">
        <div style="font-weight:700; margin-bottom:6px;">{title}</div>
        {html_table}
        <div style="font-size:11px; color:#555; margin-top:6px;">* 스크롤하여 전체 내역 확인</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(panel))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="CSV path (requires columns: date, port_name, in_out).")
    ap.add_argument("--out", default="map_ports.html", help="Output HTML path.")
    ap.add_argument("--cache", default="geocoded_ports.csv", help="CSV cache for geocoded results.")
    ap.add_argument("--fail", default="geocode_failures.csv", help="CSV for ports that failed geocoding.")
    ap.add_argument("--region", default="대한민국", help="Region hint (e.g., 대한민국).")
    ap.add_argument("--language", default="ko", help="Geocoding language.")
    ap.add_argument("--sleep", type=float, default=0.2, help="Delay between geocoding calls.")
    ap.add_argument("--month_label", default="", help="Override month label text on the map (e.g., '2025-08').")
    args = ap.parse_args()

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        sys.exit("ERROR: Please set GOOGLE_MAPS_API_KEY environment variable.")

    df = pd.read_csv(args.csv)
    df['port_name'] = df['port_name'].astype(str).str.strip()
    df['in_out'] = df['in_out'].astype(str).str.strip()

    # Month label auto-detect from 'date'
    try:
        dt = pd.to_datetime(df['date'])
        month_label_auto = dt.dt.strftime("%Y-%m").mode()[0]
    except Exception:
        month_label_auto = ""

    # Aggregate by port
    counts = df.pivot_table(index='port_name', columns='in_out', aggfunc='size', fill_value=0).reset_index()
    if '내항' not in counts.columns:
        counts['내항'] = 0
    if '외항' not in counts.columns:
        counts['외항'] = 0
    counts['총계'] = counts['내항'] + counts['외항']

    # Daily table (CSV + HTML panel)
    day_raw, day_show = build_daily_table(df)
    day_raw.to_csv("daily_inout_counts.csv", index=False, encoding="utf-8-sig")

    # Geocode with cache
    cache_df = load_cache(args.cache)
    cached_names = set(cache_df['port_name'].tolist())
    to_geo = [p for p in counts['port_name'].unique() if p not in cached_names]

    new_rows, fail_rows = [], []
    for name in to_geo:
        query = f"{name} 항만 {args.region}"
        lat, lng, fmt_addr = geocode_google(query, api_key, language=args.language)
        if lat is None:
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

    merged = counts.merge(cache_df, how="left", on="port_name")

    # Map center
    center_lat, center_lng = 37.5665, 126.9780
    if merged['lat'].notna().any():
        center_lat = merged['lat'].mean()
        center_lng = merged['lng'].mean()

    m = folium.Map(location=[center_lat, center_lng], zoom_start=7, control_scale=True)

    # Number formatter
    def fmt(n):
        try:
            return f"{int(n):,}"
        except Exception:
            return str(n)

    # Markers
    for _, row in merged.iterrows():
        name = row['port_name']
        lat = row['lat']
        lng = row['lng']
        nei = int(row.get('내항', 0))
        wei = int(row.get('외항', 0))
        total = int(row.get('총계', 0))

        popup_html = f"""
        <b>{name}</b><br>
        내항: {fmt(nei)}회<br>
        외항: {fmt(wei)}회<br>
        총계: {fmt(total)}회<br>
        <i>{row.get('formatted_address','')}</i>
        """
        if pd.notna(lat) and pd.notna(lng):
            folium.CircleMarker(
                location=[lat, lng],
                radius=max(5, min(20, total)),
                tooltip=name,
                popup=folium.Popup(popup_html, max_width=300),
                fill=True
            ).add_to(m)
        else:
            folium.Marker(
                location=[center_lat, center_lng],
                tooltip=f"[좌표없음] {name}",
                popup=folium.Popup(f"{popup_html}<br><b>⚠ 좌표를 찾지 못했습니다.</b>", max_width=300),
                icon=folium.Icon(icon="info-sign")
            ).add_to(m)

    # Month label overlay
    label_text = args.month_label if args.month_label else (month_label_auto if month_label_auto else "")
    if label_text:
        add_month_label(m, f"{label_text} 기준 입·출항")

    # Daily table panel (HTML)
    table_html = day_show.to_html(index=False, justify="center")
    add_table_panel(m, table_html)

    m.save(args.out)
    print(f"Map saved to: {args.out}")
    print("Saved daily table CSV: daily_inout_counts.csv")

if __name__ == "__main__":
    main()
