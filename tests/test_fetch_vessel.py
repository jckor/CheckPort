"""Tests for fetch_vessel_movements_daily.py"""
import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fetch_vessel_movements_daily import fetch_vessel_movements_daily


# --- XML builders ---

def _xml_response(total_count, items_xml=""):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header>
    <resultCode>00</resultCode>
    <resultMsg>NORMAL SERVICE</resultMsg>
  </header>
  <body>
    <totalCount>{total_count}</totalCount>
    <items>{items_xml}</items>
  </body>
</response>"""


def _item_xml(vssl_nm, entry_exit, dt):
    """One item with one detail record. Sets the right date field per direction."""
    if entry_exit == "입항":
        dt_fields = f"<etryptDt>{dt}</etryptDt><tkoffDt></tkoffDt>"
    else:
        dt_fields = f"<etryptDt></etryptDt><tkoffDt>{dt}</tkoffDt>"
    return f"""<item>
  <prtAgCd>621</prtAgCd><prtAgNm>여수항</prtAgNm>
  <clsgn>TEST1</clsgn><vsslNm>{vssl_nm}</vsslNm>
  <details>
    <detail>
      <etryndNm>{entry_exit}</etryndNm>
      {dt_fields}
      <laidupFcltyNm>1부두</laidupFcltyNm>
      <ibobprtNm>외항</ibobprtNm>
      <tugYn>Y</tugYn><piltgYn>Y</piltgYn>
      <ldadngFrghtClCd>01</ldadngFrghtClCd>
      <grtg>5000</grtg>
      <satmntEntrpsNm>TestCo</satmntEntrpsNm>
    </detail>
  </details>
</item>"""


def _mock_resp(xml_text):
    m = MagicMock()
    m.text = xml_text
    m.raise_for_status = MagicMock()
    return m


def _run(xml_mock, start="20250801", end="20250801", per_page=50):
    """Helper: run fetch inside a temp dir, return (out_path, raw_path)."""
    with patch("requests.get", **xml_mock):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "daily.csv")
            raw = os.path.join(d, "raw.csv")
            fetch_vessel_movements_daily(
                "fake_key", "621", start, end, out, raw, per_page=per_page
            )
            # Read before tempdir is deleted
            import pandas as pd
            daily = pd.read_csv(out) if os.path.exists(out) else None
            raw_df = pd.read_csv(raw) if os.path.exists(raw) else None
            return daily, raw_df


# --- Tests ---

def test_api_error_raises():
    err_xml = "<response><header><resultCode>99</resultCode><resultMsg>INVALID KEY</resultMsg></header></response>"
    with patch("requests.get", return_value=_mock_resp(err_xml)):
        with tempfile.TemporaryDirectory() as d:
            with pytest.raises(RuntimeError, match="99"):
                fetch_vessel_movements_daily(
                    "fake_key", "621", "20250801", "20250801",
                    os.path.join(d, "out.csv"), os.path.join(d, "raw.csv"),
                )


def test_empty_result_no_files_created():
    with patch("requests.get", return_value=_mock_resp(_xml_response(0))):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "daily.csv")
            raw = os.path.join(d, "raw.csv")
            fetch_vessel_movements_daily("fake_key", "621", "20250801", "20250801", out, raw)
            assert not os.path.exists(out)
            assert not os.path.exists(raw)


def test_single_arrival_counted():
    import pandas as pd
    item = _item_xml("VesselA", "입항", "2025-08-01T10:00:00+09:00")
    resp = _mock_resp(_xml_response(1, item))
    with patch("requests.get", return_value=resp):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "daily.csv")
            raw = os.path.join(d, "raw.csv")
            fetch_vessel_movements_daily("fake_key", "621", "20250801", "20250801", out, raw)
            daily = pd.read_csv(out)
            row = daily[daily["date"] == "2025-08-01"].iloc[0]
            assert row["arrivals"] == 1
            assert row["departures"] == 0


def test_single_departure_counted():
    import pandas as pd
    item = _item_xml("VesselB", "출항", "2025-08-02T08:00:00+09:00")
    with patch("requests.get", return_value=_mock_resp(_xml_response(1, item))):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "daily.csv")
            raw = os.path.join(d, "raw.csv")
            fetch_vessel_movements_daily("fake_key", "621", "20250802", "20250802", out, raw)
            daily = pd.read_csv(out)
            row = daily[daily["date"] == "2025-08-02"].iloc[0]
            assert row["arrivals"] == 0
            assert row["departures"] == 1


def test_date_range_fills_zero_for_missing_days():
    """Days within the range that have no data should appear with 0 counts."""
    import pandas as pd
    item = _item_xml("VesselA", "입항", "2025-08-01T10:00:00+09:00")
    with patch("requests.get", return_value=_mock_resp(_xml_response(1, item))):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "daily.csv")
            raw = os.path.join(d, "raw.csv")
            fetch_vessel_movements_daily("fake_key", "621", "20250801", "20250803", out, raw)
            daily = pd.read_csv(out)
            assert len(daily) == 3
            empty_days = daily[daily["date"] != "2025-08-01"]
            assert (empty_days["arrivals"] == 0).all()
            assert (empty_days["departures"] == 0).all()


def test_multiple_vessels_same_day():
    import pandas as pd
    items = (
        _item_xml("VesselA", "입항", "2025-08-05T08:00:00+09:00")
        + _item_xml("VesselB", "입항", "2025-08-05T10:00:00+09:00")
        + _item_xml("VesselC", "출항", "2025-08-05T14:00:00+09:00")
    )
    with patch("requests.get", return_value=_mock_resp(_xml_response(3, items))):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "daily.csv")
            raw = os.path.join(d, "raw.csv")
            fetch_vessel_movements_daily("fake_key", "621", "20250805", "20250805", out, raw)
            daily = pd.read_csv(out)
            row = daily[daily["date"] == "2025-08-05"].iloc[0]
            assert row["arrivals"] == 2
            assert row["departures"] == 1


def test_pagination_makes_two_api_calls():
    """totalCount=51 with per_page=50 should trigger exactly 2 API calls."""
    item1 = _item_xml("VesselA", "입항", "2025-08-01T10:00:00+09:00")
    item2 = _item_xml("VesselB", "출항", "2025-08-01T16:00:00+09:00")
    page1 = _mock_resp(_xml_response(51, item1))
    page2 = _mock_resp(_xml_response(51, item2))
    with patch("requests.get", side_effect=[page1, page2]) as mock_get:
        with tempfile.TemporaryDirectory() as d:
            fetch_vessel_movements_daily(
                "fake_key", "621", "20250801", "20250801",
                os.path.join(d, "out.csv"), os.path.join(d, "raw.csv"),
                per_page=50,
            )
            assert mock_get.call_count == 2


def test_raw_csv_has_expected_columns():
    import pandas as pd
    item = _item_xml("VesselA", "입항", "2025-08-01T10:00:00+09:00")
    with patch("requests.get", return_value=_mock_resp(_xml_response(1, item))):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "daily.csv")
            raw = os.path.join(d, "raw.csv")
            fetch_vessel_movements_daily("fake_key", "621", "20250801", "20250801", out, raw)
            df = pd.read_csv(raw)
            for col in ["date", "entry_exit", "vessel_name", "port_name", "berth_name"]:
                assert col in df.columns, f"Missing column: {col}"


def test_detail_with_missing_date_is_skipped():
    """A detail record with no timestamp should not appear in output."""
    item = """<item>
  <prtAgCd>621</prtAgCd><prtAgNm>여수항</prtAgNm>
  <clsgn>T1</clsgn><vsslNm>Ghost</vsslNm>
  <details>
    <detail>
      <etryndNm>입항</etryndNm>
      <etryptDt></etryptDt><tkoffDt></tkoffDt>
    </detail>
  </details>
</item>"""
    with patch("requests.get", return_value=_mock_resp(_xml_response(1, item))):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "daily.csv")
            raw = os.path.join(d, "raw.csv")
            fetch_vessel_movements_daily("fake_key", "621", "20250801", "20250801", out, raw)
            assert not os.path.exists(raw), "No raw CSV should be created when all records are skipped"
