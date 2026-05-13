"""Tests for Flask app endpoints."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch
import app as flask_app

@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<!DOCTYPE html" in resp.data or b"html" in resp.data.lower()


SAMPLE_RECORDS = [
    {
        "date": "2025-08-01", "entry_exit": "입항", "port_code": "621",
        "port_name": "여수항", "vessel_name": "TestShip",
        "vessel_type": "일반화물선", "vessel_nationality": "대한민국",
        "entry_purpose": "하역", "call_sign": "T1", "berth_name": "1부두",
        "in_out": "외항", "tug_used": "Y", "pilot_used": "Y",
        "cargo_type_code": "27", "cargo_type_name": "석유류",
        "ld_ton": "1000", "landng_ton": "2000", "trnpdt_ton": "0",
        "grtg": "5000", "de_raw_entry_dt": "2025-08-01T10:00:00+09:00",
        "de_raw_depart_dt": "", "declarer": "TestCo",
    }
]


def test_query_returns_records(client):
    with patch("app.fetch_vessel_records", return_value=SAMPLE_RECORDS):
        resp = client.post(
            "/query",
            json={"prtAgCd": "621", "start_date": "20250801", "end_date": "20250831"},
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert data["records"][0]["vessel_name"] == "TestShip"


def test_query_missing_params_returns_400(client):
    resp = client.post("/query", json={"prtAgCd": "621"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_query_api_error_returns_400(client):
    with patch("app.fetch_vessel_records", side_effect=RuntimeError("API error")):
        resp = client.post(
            "/query",
            json={"prtAgCd": "621", "start_date": "20250801", "end_date": "20250831"},
        )
    assert resp.status_code == 400
    assert "API error" in resp.get_json()["error"]


def test_export_returns_xlsx(client):
    with patch("app.fetch_vessel_records", return_value=SAMPLE_RECORDS):
        resp = client.get(
            "/export?prtAgCd=621&start_date=20250801&end_date=20250831"
        )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.content_type
    cd = resp.headers.get("Content-Disposition", "")
    assert "vessel_movements_621_20250801_20250831" in cd


def test_export_missing_params_returns_400(client):
    resp = client.get("/export?prtAgCd=621")
    assert resp.status_code == 400


def test_export_empty_records_returns_xlsx(client):
    with patch("app.fetch_vessel_records", return_value=[]):
        resp = client.get(
            "/export?prtAgCd=621&start_date=20250801&end_date=20250831"
        )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.content_type


def test_query_invalid_date_format_returns_400(client):
    resp = client.post(
        "/query",
        json={"prtAgCd": "621", "start_date": "2025-08-01", "end_date": "20250831"},
    )
    assert resp.status_code == 400
    assert "YYYYMMDD" in resp.get_json()["error"]


def test_export_invalid_date_format_returns_400(client):
    resp = client.get("/export?prtAgCd=621&start_date=2025-08-01&end_date=20250831")
    assert resp.status_code == 400
    assert "YYYYMMDD" in resp.data.decode()


def test_query_date_order_returns_400(client):
    resp = client.post(
        "/query",
        json={"prtAgCd": "621", "start_date": "20250831", "end_date": "20250801"},
    )
    assert resp.status_code == 400
