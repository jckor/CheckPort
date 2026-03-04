"""Tests for ygpa_2025.py"""
import os
import sys
import xml.etree.ElementTree as ET
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ygpa_2025


# --- XML fixtures ---

CARGO_FAC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE</resultMsg></header>
  <body>
    <items>
      <item>
        <title>1부두</title>
        <totTon>100000</totTon>
        <totOceanTon>80000</totOceanTon>
        <korTon>50000</korTon>
        <forTon>30000</forTon>
        <coastTon>20000</coastTon>
      </item>
      <item>
        <title>2부두</title>
        <totTon>50000</totTon>
        <totOceanTon>40000</totOceanTon>
        <korTon>25000</korTon>
        <forTon>15000</forTon>
        <coastTon>10000</coastTon>
      </item>
    </items>
  </body>
</response>"""

ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>30</resultCode><resultMsg>SERVICE KEY ERROR</resultMsg></header>
</response>"""


def _mock_resp(xml_text):
    m = MagicMock()
    m.text = xml_text
    m.raise_for_status = MagicMock()
    return m


# --- xml_items_to_records ---

def test_xml_items_to_records_returns_all_items():
    root = ET.fromstring(CARGO_FAC_XML)
    records = ygpa_2025.xml_items_to_records(root)
    assert len(records) == 2


def test_xml_items_to_records_field_values():
    root = ET.fromstring(CARGO_FAC_XML)
    records = ygpa_2025.xml_items_to_records(root)
    assert records[0]["title"] == "1부두"
    assert records[0]["totTon"] == "100000"
    assert records[1]["title"] == "2부두"


def test_xml_items_to_records_empty_items():
    xml = "<response><body><items></items></body></response>"
    root = ET.fromstring(xml)
    assert ygpa_2025.xml_items_to_records(root) == []


def test_xml_items_to_records_all_child_tags_captured():
    root = ET.fromstring(CARGO_FAC_XML)
    records = ygpa_2025.xml_items_to_records(root)
    first = records[0]
    assert set(first.keys()) == {"title", "totTon", "totOceanTon", "korTon", "forTon", "coastTon"}


# --- get_xml ---

def test_get_xml_raises_on_error_code():
    with patch("requests.get", return_value=_mock_resp(ERROR_XML)):
        with pytest.raises(RuntimeError, match="30"):
            ygpa_2025.get_xml("http://example.com", {})


def test_get_xml_returns_root_element():
    with patch("requests.get", return_value=_mock_resp(CARGO_FAC_XML)):
        root = ygpa_2025.get_xml("http://example.com", {})
    assert root is not None
    assert root.tag == "response"


# --- fetch_stat_cargo_fac ---

def test_fetch_stat_cargo_fac_renames_columns():
    with patch("requests.get", return_value=_mock_resp(CARGO_FAC_XML)):
        df = ygpa_2025.fetch_stat_cargo_fac("620", "202501", "202508")
    assert "부두명" in df.columns
    assert "총톤수" in df.columns
    assert "외항톤수" in df.columns
    assert "연안톤수" in df.columns


def test_fetch_stat_cargo_fac_row_count():
    with patch("requests.get", return_value=_mock_resp(CARGO_FAC_XML)):
        df = ygpa_2025.fetch_stat_cargo_fac("620", "202501", "202508")
    assert len(df) == 2
    assert df.iloc[0]["부두명"] == "1부두"


# --- fetch_stat_cargo_item ---

def test_fetch_stat_cargo_item_renames_columns():
    item_xml = CARGO_FAC_XML.replace("<title>1부두</title>", "<title>철광석</title>") \
                             .replace("<title>2부두</title>", "<title>석탄</title>")
    with patch("requests.get", return_value=_mock_resp(item_xml)):
        df = ygpa_2025.fetch_stat_cargo_item("620", "2025")
    assert "품목명" in df.columns
    assert df.iloc[0]["품목명"] == "철광석"


# --- fetch_stat_vssl_fac ---

def test_fetch_stat_vssl_fac_returns_dataframe():
    with patch("requests.get", return_value=_mock_resp(CARGO_FAC_XML)):
        df = ygpa_2025.fetch_stat_vssl_fac("620", "202501", "202508")
    assert len(df) == 2


# --- fetch_stat_vssl_month ---

def test_fetch_stat_vssl_month_returns_dataframe():
    with patch("requests.get", return_value=_mock_resp(CARGO_FAC_XML)):
        df = ygpa_2025.fetch_stat_vssl_month("620", "2025")
    assert len(df) == 2


def test_fetch_stat_vssl_month_with_direction():
    """g_in_out param should be passed through to the API call."""
    with patch("requests.get", return_value=_mock_resp(CARGO_FAC_XML)) as mock_get:
        ygpa_2025.fetch_stat_vssl_month("620", "2025", g_in_out="I")
    url_called = mock_get.call_args[0][0]
    assert "g_in_out=I" in url_called
