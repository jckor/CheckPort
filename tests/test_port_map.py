"""Tests for make_port_map_v3.py helper functions."""
import os
import sys
import datetime
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import make_port_map_v3 as port_map


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "date":       ["2025-08-01", "2025-08-01", "2025-08-02", "2025-08-02", "2025-08-02"],
        "port_name":  ["여수항",      "광양항",      "여수항",      "여수항",      "광양항"],
        "in_out":     ["외항",        "내항",        "외항",        "내항",        "외항"],
        "entry_exit": ["입항",        "출항",        "입항",        "입항",        "출항"],
    })


# --- build_daily_tables ---

def test_build_daily_tables_inout_totals(sample_df):
    (pivot, _), _ = port_map.build_daily_tables(sample_df)
    aug1 = pivot[pivot["date"] == datetime.date(2025, 8, 1)].iloc[0]
    assert int(aug1["총계"]) == 2  # 1 내항 + 1 외항


def test_build_daily_tables_entryexit_counts(sample_df):
    _, (pivot, _) = port_map.build_daily_tables(sample_df)
    aug1 = pivot[pivot["date"] == datetime.date(2025, 8, 1)].iloc[0]
    assert int(aug1["입항"]) == 1
    assert int(aug1["출항"]) == 1


def test_build_daily_tables_show_uses_comma_format(sample_df):
    """The 'show' DataFrames should format numbers with thousand separators."""
    _, (_, show) = port_map.build_daily_tables(sample_df)
    # All values in the formatted columns should be strings
    for col in ["입항", "출항", "총계"]:
        assert show[col].dtype == object, f"Column {col} should be string-typed"


def test_build_daily_tables_missing_column_filled_zero():
    """If only one direction exists, the other should default to 0."""
    df = pd.DataFrame({
        "date":       ["2025-08-01"],
        "port_name":  ["여수항"],
        "in_out":     ["외항"],   # no 내항 rows
        "entry_exit": ["입항"],
    })
    (pivot, _), _ = port_map.build_daily_tables(df)
    assert "내항" in pivot.columns
    assert int(pivot.iloc[0]["내항"]) == 0


# --- load_cache / save_cache ---

def test_load_cache_returns_empty_df_when_file_missing(tmp_path):
    cache = port_map.load_cache(str(tmp_path / "nonexistent.csv"))
    assert cache.empty
    assert list(cache.columns) == ["port_name", "lat", "lng", "formatted_address"]


def test_load_cache_reads_existing_file(tmp_path):
    csv_path = tmp_path / "cache.csv"
    pd.DataFrame({
        "port_name": ["여수항"],
        "lat": [34.74],
        "lng": [127.74],
        "formatted_address": ["전남 여수시"],
    }).to_csv(csv_path, index=False)
    cache = port_map.load_cache(str(csv_path))
    assert len(cache) == 1
    assert cache.iloc[0]["port_name"] == "여수항"


def test_load_cache_strips_whitespace(tmp_path):
    csv_path = tmp_path / "cache.csv"
    pd.DataFrame({
        "port_name": [" 여수항 "],
        "lat": [34.74], "lng": [127.74], "formatted_address": ["addr"],
    }).to_csv(csv_path, index=False)
    cache = port_map.load_cache(str(csv_path))
    assert cache.iloc[0]["port_name"] == "여수항"


def test_save_cache_deduplicates_keeps_last(tmp_path):
    cache_path = str(tmp_path / "cache.csv")
    df = pd.DataFrame({
        "port_name": ["여수항", "여수항"],
        "lat": [34.74, 34.99],
        "lng": [127.74, 127.99],
        "formatted_address": ["old", "new"],
    })
    port_map.save_cache(df, cache_path)
    loaded = pd.read_csv(cache_path)
    assert len(loaded) == 1
    assert loaded.iloc[0]["formatted_address"] == "new"


def test_save_cache_preserves_multiple_ports(tmp_path):
    cache_path = str(tmp_path / "cache.csv")
    df = pd.DataFrame({
        "port_name": ["여수항", "광양항"],
        "lat": [34.74, 34.93],
        "lng": [127.74, 127.71],
        "formatted_address": ["여수", "광양"],
    })
    port_map.save_cache(df, cache_path)
    loaded = pd.read_csv(cache_path)
    assert len(loaded) == 2


# --- geocode_google ---

def _mock_geocode_resp(status, lat=None, lng=None, address=""):
    m = MagicMock()
    m.raise_for_status = MagicMock()
    if status == "OK":
        m.json.return_value = {
            "status": "OK",
            "results": [{"geometry": {"location": {"lat": lat, "lng": lng}},
                         "formatted_address": address}],
        }
    else:
        m.json.return_value = {"status": status, "results": []}
    return m


def test_geocode_google_success():
    with patch("requests.get", return_value=_mock_geocode_resp("OK", 34.74, 127.74, "전남 여수시")):
        lat, lng, addr = port_map.geocode_google("여수항", "fake_key")
    assert lat == 34.74
    assert lng == 127.74
    assert addr == "전남 여수시"


def test_geocode_google_zero_results_returns_none():
    with patch("requests.get", return_value=_mock_geocode_resp("ZERO_RESULTS")):
        lat, lng, addr = port_map.geocode_google("없는항구", "fake_key")
    assert lat is None
    assert lng is None
    assert addr is None


def test_geocode_google_passes_api_key():
    """Verify the API key is included in the request parameters."""
    with patch("requests.get", return_value=_mock_geocode_resp("OK", 0, 0, "")) as mock_get:
        port_map.geocode_google("여수항", "my_secret_key")
    call_kwargs = mock_get.call_args
    params = call_kwargs[1].get("params") or call_kwargs[0][1]
    assert params.get("key") == "my_secret_key"
