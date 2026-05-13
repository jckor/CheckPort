# CheckPort Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flask 웹 앱으로 항만청코드·날짜 조회 폼, 클라이언트 페이징/필터 테이블, XLSX 다운로드를 제공한다.

**Architecture:** `fetch_vessel_movements_daily.py`에서 API 호출·XML 파싱 로직을 `fetch_vessel_records()`로 추출해 Flask 엔드포인트와 기존 CLI 양쪽에서 재사용한다. POST `/query`는 전체 레코드를 JSON으로 반환하고, 브라우저 JS가 Summary·100건 페이징·3가지 필터를 처리한다. GET `/export`는 openpyxl로 XLSX를 생성해 다운로드한다.

**Tech Stack:** Python 3.13, Flask, openpyxl, Bootstrap 5 (CDN), Vanilla JS, pytest + unittest.mock

---

## File Map

| 경로 | 역할 | 변경 |
|---|---|---|
| `fetch_vessel_movements_daily.py` | `fetch_vessel_records()` 추출, `fetch_vessel_movements_daily()` 위임 | 수정 |
| `app.py` | Flask 앱: GET `/`, POST `/query`, GET `/export` | 신규 |
| `templates/index.html` | 조회 폼 + Summary + 필터 + 테이블 + 페이지네이션 | 신규 |
| `tests/test_fetch_vessel.py` | `fetch_vessel_records()` 테스트 추가 | 수정 |
| `tests/test_app.py` | Flask 엔드포인트 테스트 | 신규 |

---

## Task 1: 의존성 설치

**Files:** 없음 (pip 설치만)

- [ ] **Step 1: flask, openpyxl 설치**

```bash
python.exe -m pip install flask openpyxl
```

Expected output 포함:
```
Successfully installed flask-3.x.x openpyxl-3.x.x ...
```

- [ ] **Step 2: 설치 확인**

```bash
python.exe -c "import flask, openpyxl; print('OK')"
```

Expected: `OK`

---

## Task 2: `fetch_vessel_records()` 추출 (TDD)

**Files:**
- Modify: `fetch_vessel_movements_daily.py`
- Modify: `tests/test_fetch_vessel.py`

### Step 1: 실패 테스트 작성

`tests/test_fetch_vessel.py` 파일 상단 import 줄을 수정:

```python
from fetch_vessel_movements_daily import fetch_vessel_movements_daily, fetch_vessel_records
```

파일 맨 아래에 세 개의 테스트 추가:

```python
def test_fetch_vessel_records_returns_list():
    item = _item_xml("VesselA", "입항", "2025-08-01T10:00:00+09:00")
    with patch("requests.get", return_value=_mock_resp(_xml_response(1, item))):
        records = fetch_vessel_records("fake_key", "621", "20250801", "20250801")
    assert len(records) == 1
    assert records[0]["vessel_name"] == "VesselA"
    assert records[0]["entry_exit"] == "입항"
    assert records[0]["date"] == "2025-08-01"


def test_fetch_vessel_records_empty_returns_empty_list():
    with patch("requests.get", return_value=_mock_resp(_xml_response(0))):
        records = fetch_vessel_records("fake_key", "621", "20250801", "20250801")
    assert records == []


def test_fetch_vessel_records_api_error_raises():
    err_xml = "<response><header><resultCode>99</resultCode><resultMsg>INVALID</resultMsg></header></response>"
    with patch("requests.get", return_value=_mock_resp(err_xml)):
        with pytest.raises(RuntimeError, match="99"):
            fetch_vessel_records("fake_key", "621", "20250801", "20250801")
```

- [ ] **Step 2: 실패 확인**

```bash
python.exe -m pytest tests/test_fetch_vessel.py::test_fetch_vessel_records_returns_list -v
```

Expected: `ImportError` 또는 `FAILED` (함수 미정의)

- [ ] **Step 3: `fetch_vessel_movements_daily.py` 전체 교체**

기존 파일을 아래 내용으로 전체 교체한다 (기존 `CARGO_CODE_MAP`, XML 파싱 로직을 `fetch_vessel_records`로 이동):

```python
import requests
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import urlencode
from collections import defaultdict
import xml.etree.ElementTree as ET

CARGO_CODE_MAP = {
    "-":  "미분류",
    "25": "일반화물(철재 포함)",
    "26": "건화물/산물",
    "27": "석유류",
    "28": "화학액체",
    "29": "액화가스/화학제품",
    "31": "광물/곡물",
    "38": "특수화학물질",
}

_BASE_URL = "http://apis.data.go.kr/1192000/VsslEtrynd5/Info5"


def fetch_vessel_records(
    service_key: str,
    prtAgCd: str,
    start_date: str,
    end_date: str,
    per_page: int = 50,
) -> list[dict]:
    """API를 호출해 선박 입출항 상세 레코드 목록을 반환합니다 (CSV 저장 없음)."""

    def call_api(page_no: int) -> str:
        params = {
            "serviceKey": service_key,
            "prtAgCd": prtAgCd,
            "sde": start_date,
            "ede": end_date,
            "pageNo": page_no,
            "numOfRows": per_page,
        }
        r = requests.get(f"{_BASE_URL}?{urlencode(params, doseq=True)}", timeout=30)
        r.raise_for_status()
        return r.text

    all_details: list[dict] = []

    first_xml = call_api(1)
    root = ET.fromstring(first_xml)
    result_code = root.findtext(".//resultCode")
    result_msg  = root.findtext(".//resultMsg")
    if result_code != "00":
        raise RuntimeError(f"OpenAPI error: {result_code} - {result_msg}")

    total_count_text = root.findtext(".//totalCount")
    total_count = int(total_count_text) if total_count_text and total_count_text.isdigit() else 0

    def extract_items(xml_text: str) -> None:
        rt = ET.fromstring(xml_text)
        for it in rt.findall(".//items/item"):
            port_code   = it.findtext("prtAgCd")
            port_name   = it.findtext("prtAgNm")
            call_sign   = it.findtext("clsgn")
            vssl_nm     = it.findtext("vsslNm")
            vssl_knd_nm = it.findtext("vsslKndNm")
            vssl_nlt_nm = it.findtext("vsslNltyNm")
            purps_nm    = it.findtext("etryptPurpsNm")
            for d in it.findall(".//details/detail"):
                entry_exit = d.findtext("etryndNm")
                etrypt_dt  = d.findtext("etryptDt")
                tkoff_dt   = d.findtext("tkoffDt")
                if entry_exit == "입항" and etrypt_dt:
                    date_only = etrypt_dt.split("+")[0].split("T")[0]
                elif entry_exit == "출항" and tkoff_dt:
                    date_only = tkoff_dt.split("+")[0].split("T")[0]
                else:
                    continue
                cargo_cd = d.findtext("ldadngFrghtClCd")
                all_details.append({
                    "date":               date_only,
                    "entry_exit":         entry_exit,
                    "port_code":          port_code,
                    "port_name":          port_name,
                    "vessel_name":        vssl_nm,
                    "vessel_type":        vssl_knd_nm,
                    "vessel_nationality": vssl_nlt_nm,
                    "entry_purpose":      purps_nm,
                    "call_sign":          call_sign,
                    "berth_name":         d.findtext("laidupFcltyNm"),
                    "in_out":             d.findtext("ibobprtNm"),
                    "tug_used":           d.findtext("tugYn"),
                    "pilot_used":         d.findtext("piltgYn"),
                    "cargo_type_code":    cargo_cd,
                    "cargo_type_name":    CARGO_CODE_MAP.get(cargo_cd or "-", cargo_cd),
                    "ld_ton":             d.findtext("ldadngTon"),
                    "landng_ton":         d.findtext("landngFrghtTon"),
                    "trnpdt_ton":         d.findtext("trnpdtTon"),
                    "grtg":               d.findtext("grtg"),
                    "de_raw_entry_dt":    etrypt_dt,
                    "de_raw_depart_dt":   tkoff_dt,
                    "declarer":           d.findtext("satmntEntrpsNm"),
                })

    if total_count > 0:
        extract_items(first_xml)
        pages = (total_count + per_page - 1) // per_page
        for p in range(2, pages + 1):
            extract_items(call_api(p))

    return all_details


def fetch_vessel_movements_daily(
    service_key: str,
    prtAgCd: str,
    start_date: str,
    end_date: str,
    out_csv: str = "yeosu_daily_movements.csv",
    raw_csv: str = "yeosu_raw_records.csv",
    per_page: int = 50,
) -> None:
    """
    여수항(또는 지정 항만청코드)의 일별 선박 입출항 현황을 CSV로 저장합니다.

    Parameters
    ----------
    service_key : str  공공데이터포털 서비스키
    prtAgCd     : str  항만청코드 (예: '621')
    start_date  : str  조회 시작일 YYYYMMDD
    end_date    : str  조회 종료일 YYYYMMDD
    out_csv     : str  일별 집계 CSV 경로
    raw_csv     : str  원시 상세 CSV 경로
    per_page    : int  페이지당 레코드 수 (최대 50)
    """
    all_details = fetch_vessel_records(service_key, prtAgCd, start_date, end_date, per_page)

    if not all_details:
        print("상세 레코드가 없어 CSV를 생성하지 않았습니다.")
        return

    raw_df = pd.DataFrame(all_details)
    raw_df.sort_values(["date", "entry_exit", "vessel_name"], inplace=True)
    raw_df.to_csv(raw_csv, index=False, encoding="utf-8-sig")

    agg: dict[str, dict] = defaultdict(lambda: {"arrivals": 0, "departures": 0})
    for r in all_details:
        if r["entry_exit"] == "입항":
            agg[r["date"]]["arrivals"] += 1
        elif r["entry_exit"] == "출항":
            agg[r["date"]]["departures"] += 1

    rows = []
    cur = datetime.strptime(start_date, "%Y%m%d").date()
    ed  = datetime.strptime(end_date,   "%Y%m%d").date()
    while cur <= ed:
        d = cur.isoformat()
        rows.append({
            "date":       d,
            "arrivals":   agg[d]["arrivals"]   if d in agg else 0,
            "departures": agg[d]["departures"] if d in agg else 0,
        })
        cur += timedelta(days=1)

    pd.DataFrame(rows).sort_values("date").to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"[완료] 일별 집계: {out_csv} / 원시 상세: {raw_csv}")
```

- [ ] **Step 4: 전체 테스트 실행 (기존 + 신규)**

```bash
python.exe -m pytest tests/test_fetch_vessel.py -v
```

Expected: 모든 테스트 PASSED (기존 8개 + 신규 3개 = 11개)

- [ ] **Step 5: 커밋**

```bash
git add fetch_vessel_movements_daily.py tests/test_fetch_vessel.py
git commit -m "refactor: extract fetch_vessel_records() for Flask reuse"
```

---

## Task 3: Flask 앱 뼈대 + GET `/` (TDD)

**Files:**
- Create: `app.py`
- Create: `templates/index.html` (빈 shell)
- Create: `tests/test_app.py`

- [ ] **Step 1: 실패 테스트 작성 — `tests/test_app.py` 생성**

```python
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
```

- [ ] **Step 2: 실패 확인**

```bash
python.exe -m pytest tests/test_app.py::test_index_returns_200 -v
```

Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: `app.py` 생성**

```python
import os
import io
from flask import Flask, request, jsonify, render_template, send_file
from fetch_vessel_movements_daily import fetch_vessel_records
import openpyxl

app = Flask(__name__)
SERVICE_KEY = os.environ.get("SERVICE_KEY", "")


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

- [ ] **Step 4: `templates/index.html` 생성 (최소 shell)**

```html
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>선박 입출항 조회</title></head>
<body><h1>선박 입출항 조회 시스템</h1></body>
</html>
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python.exe -m pytest tests/test_app.py::test_index_returns_200 -v
```

Expected: `PASSED`

- [ ] **Step 6: 커밋**

```bash
git add app.py templates/index.html tests/test_app.py
git commit -m "feat: add Flask app skeleton with GET /"
```

---

## Task 4: POST `/query` + GET `/export` 엔드포인트 (TDD)

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app.py`

### 4-A: POST `/query`

- [ ] **Step 1: 실패 테스트 추가 — `tests/test_app.py`에 아래 내용 추가**

```python
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
```

- [ ] **Step 2: 실패 확인**

```bash
python.exe -m pytest tests/test_app.py::test_query_returns_records -v
```

Expected: `404 NOT FOUND` (라우트 미등록)

- [ ] **Step 3: `app.py`에 `/query` 라우트 추가 — `if __name__` 줄 위에 삽입**

```python
@app.route("/query", methods=["POST"])
def query():
    data = request.get_json() or {}
    prtAgCd    = data.get("prtAgCd", "").strip()
    start_date = data.get("start_date", "").strip()
    end_date   = data.get("end_date", "").strip()
    if not prtAgCd or not start_date or not end_date:
        return jsonify({"error": "prtAgCd, start_date, end_date 가 필요합니다."}), 400
    try:
        records = fetch_vessel_records(SERVICE_KEY, prtAgCd, start_date, end_date)
        return jsonify({"records": records, "total": len(records)})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
```

- [ ] **Step 4: `/query` 테스트 통과 확인**

```bash
python.exe -m pytest tests/test_app.py::test_query_returns_records tests/test_app.py::test_query_missing_params_returns_400 tests/test_app.py::test_query_api_error_returns_400 -v
```

Expected: 3개 모두 `PASSED`

### 4-B: GET `/export`

- [ ] **Step 5: 실패 테스트 추가**

```python
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
```

- [ ] **Step 6: 실패 확인**

```bash
python.exe -m pytest tests/test_app.py::test_export_returns_xlsx -v
```

Expected: `404 NOT FOUND`

- [ ] **Step 7: `app.py`에 `/export` 라우트 추가**

```python
def _sum_ton(records: list[dict], key: str) -> float:
    total = 0.0
    for r in records:
        try:
            total += float(r.get(key) or 0)
        except (ValueError, TypeError):
            pass
    return total


@app.route("/export")
def export():
    prtAgCd    = request.args.get("prtAgCd", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date   = request.args.get("end_date", "").strip()
    if not prtAgCd or not start_date or not end_date:
        return "prtAgCd, start_date, end_date 가 필요합니다.", 400
    try:
        records = fetch_vessel_records(SERVICE_KEY, prtAgCd, start_date, end_date)
    except RuntimeError as e:
        return str(e), 400

    wb = openpyxl.Workbook()

    # 시트1: Summary
    ws1 = wb.active
    ws1.title = "Summary"
    arrivals   = sum(1 for r in records if r["entry_exit"] == "입항")
    departures = sum(1 for r in records if r["entry_exit"] == "출항")
    vtype_cnt  = len({r["vessel_type"] for r in records if r.get("vessel_type")})
    ws1.append(["항목", "값"])
    for row in [
        ("총 레코드 수",           len(records)),
        ("입항 건수",              arrivals),
        ("출항 건수",              departures),
        ("선박 종류 수",           vtype_cnt),
        ("선적 화물 합계 (톤)",    _sum_ton(records, "ld_ton")),
        ("양하 화물 합계 (톤)",    _sum_ton(records, "landng_ton")),
        ("환적 화물 합계 (톤)",    _sum_ton(records, "trnpdt_ton")),
    ]:
        ws1.append(list(row))

    # 시트2: 상세 데이터
    ws2 = wb.create_sheet("상세 데이터")
    if records:
        headers = list(records[0].keys())
        ws2.append(headers)
        for r in records:
            ws2.append([r.get(h) for h in headers])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"vessel_movements_{prtAgCd}_{start_date}_{end_date}.xlsx"
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
```

- [ ] **Step 8: 전체 앱 테스트 통과 확인**

```bash
python.exe -m pytest tests/test_app.py -v
```

Expected: 6개 모두 `PASSED`

- [ ] **Step 9: 전체 테스트 스위트 회귀 확인**

```bash
python.exe -m pytest tests/ -v
```

Expected: 17개 모두 `PASSED` (기존 11개 + 신규 6개)

- [ ] **Step 10: 커밋**

```bash
git add app.py tests/test_app.py
git commit -m "feat: add /query and /export Flask endpoints with tests"
```

---

## Task 5: 완성된 HTML 템플릿 (`templates/index.html`)

**Files:**
- Modify: `templates/index.html` (전체 교체)

- [ ] **Step 1: `templates/index.html`을 아래 내용으로 전체 교체**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>선박 입출항 조회 시스템</title>
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        .summary-card { border-left: 4px solid; }
        .page-link { cursor: pointer; }
        #results-section { display: none; }
    </style>
</head>
<body class="bg-light">
<div class="container py-4">
    <h2 class="mb-4 fw-bold">선박 입출항 조회 시스템</h2>

    <!-- 조회 폼 -->
    <div class="card shadow-sm mb-4">
        <div class="card-body">
            <div class="row g-3 align-items-end">
                <div class="col-md-4">
                    <label class="form-label fw-bold">항만청코드</label>
                    <select id="port-select" class="form-select" onchange="syncPortInput()">
                        <option value="621">여수항 (621)</option>
                        <option value="011">부산항 (011)</option>
                        <option value="021">인천항 (021)</option>
                        <option value="031">울산항 (031)</option>
                        <option value="041">광양항 (041)</option>
                        <option value="051">마산항 (051)</option>
                        <option value="061">목포항 (061)</option>
                        <option value="custom">직접 입력...</option>
                    </select>
                    <input type="text" id="port-input" class="form-control mt-1"
                           placeholder="코드 직접 입력 (예: 621)" style="display:none"
                           oninput="syncPortSelect()">
                </div>
                <div class="col-md-3">
                    <label class="form-label fw-bold">조회 시작일</label>
                    <input type="date" id="start-date" class="form-control">
                </div>
                <div class="col-md-3">
                    <label class="form-label fw-bold">조회 종료일</label>
                    <input type="date" id="end-date" class="form-control">
                </div>
                <div class="col-md-2">
                    <button id="query-btn" class="btn btn-primary w-100"
                            onclick="runQuery()">조회하기</button>
                </div>
            </div>
            <div class="mt-2" id="loading-msg" style="display:none">
                <span class="spinner-border spinner-border-sm text-primary"></span>
                <span class="text-muted ms-1">데이터 조회 중...</span>
            </div>
            <div class="mt-2 text-danger fw-semibold" id="error-msg"
                 style="display:none"></div>
        </div>
    </div>

    <div id="results-section">
        <!-- Summary 카드 -->
        <div class="row g-3 mb-4" id="summary-cards"></div>

        <!-- 필터 + 다운로드 -->
        <div class="card shadow-sm mb-3">
            <div class="card-body">
                <div class="row g-2 align-items-center">
                    <div class="col-md-3">
                        <input type="text" id="filter-vessel-name" class="form-control"
                               placeholder="선박명 검색" oninput="applyFilters()">
                    </div>
                    <div class="col-md-3">
                        <select id="filter-vessel-type" class="form-select"
                                onchange="applyFilters()">
                            <option value="">전체 선박종류</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <select id="filter-cargo-type" class="form-select"
                                onchange="applyFilters()">
                            <option value="">전체 화물종류</option>
                        </select>
                    </div>
                    <div class="col-md-1">
                        <button class="btn btn-outline-secondary w-100"
                                onclick="resetFilters()">초기화</button>
                    </div>
                    <div class="col-md-2">
                        <button class="btn btn-success w-100"
                                onclick="downloadXlsx()">XLSX 다운로드</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- 테이블 -->
        <div class="card shadow-sm">
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-sm mb-0">
                        <thead class="table-dark" id="table-head"></thead>
                        <tbody id="table-body"></tbody>
                    </table>
                </div>
            </div>
            <div class="card-footer d-flex justify-content-between align-items-center
                        flex-wrap gap-2">
                <span id="page-info" class="text-muted small"></span>
                <nav aria-label="pagination">
                    <ul class="pagination pagination-sm mb-0" id="pagination"></ul>
                </nav>
            </div>
        </div>
    </div>
</div>

<script>
/* ── 상수 ─────────────────────────────────────────────── */
const COLUMNS = [
    ["date",               "날짜"],
    ["entry_exit",         "입출항"],
    ["port_name",          "항만명"],
    ["vessel_name",        "선박명"],
    ["vessel_type",        "선박종류"],
    ["vessel_nationality", "국적"],
    ["entry_purpose",      "입항목적"],
    ["berth_name",         "계류시설"],
    ["in_out",             "내외항"],
    ["tug_used",           "예선"],
    ["pilot_used",         "도선"],
    ["cargo_type_name",    "화물종류"],
    ["ld_ton",             "선적톤수"],
    ["landng_ton",         "양하톤수"],
    ["trnpdt_ton",         "환적톤수"],
    ["grtg",               "총톤수"],
];
const PAGE_SIZE = 100;

/* ── 상태 ─────────────────────────────────────────────── */
let allRecords      = [];
let filteredRecords = [];
let currentPage     = 1;
let currentParams   = {};

/* ── 항만코드 UI ──────────────────────────────────────── */
function syncPortInput() {
    const sel = document.getElementById("port-select");
    const inp = document.getElementById("port-input");
    inp.style.display = sel.value === "custom" ? "block" : "none";
    if (sel.value === "custom") inp.focus();
    else inp.value = "";
}

function syncPortSelect() {
    const sel = document.getElementById("port-select");
    if (sel.value !== "custom") sel.value = "custom";
}

function getPortCode() {
    const sel = document.getElementById("port-select");
    return sel.value === "custom"
        ? document.getElementById("port-input").value.trim()
        : sel.value;
}

/* ── 조회 ─────────────────────────────────────────────── */
async function runQuery() {
    const prtAgCd   = getPortCode();
    const startDate = document.getElementById("start-date").value.replace(/-/g, "");
    const endDate   = document.getElementById("end-date").value.replace(/-/g, "");

    if (!prtAgCd || !startDate || !endDate) {
        showError("항만청코드, 시작일, 종료일을 모두 입력해주세요.");
        return;
    }
    if (startDate > endDate) {
        showError("시작일이 종료일보다 늦을 수 없습니다.");
        return;
    }

    currentParams = { prtAgCd, start_date: startDate, end_date: endDate };
    showError("");
    showLoading(true);
    document.getElementById("results-section").style.display = "none";
    document.getElementById("query-btn").disabled = true;

    try {
        const resp = await fetch("/query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentParams),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || "서버 오류가 발생했습니다.");
        allRecords = data.records;
        renderAll();
        document.getElementById("results-section").style.display = "block";
    } catch (e) {
        showError(e.message);
    } finally {
        showLoading(false);
        document.getElementById("query-btn").disabled = false;
    }
}

/* ── 렌더링 ───────────────────────────────────────────── */
function renderAll() {
    renderSummary(allRecords);
    populateFilterDropdowns(allRecords);
    resetFilters();
}

function renderSummary(records) {
    const arrivals   = records.filter(r => r.entry_exit === "입항").length;
    const departures = records.filter(r => r.entry_exit === "출항").length;
    const vtypes     = new Set(records.map(r => r.vessel_type).filter(Boolean)).size;
    const sumTon = key =>
        records.reduce((s, r) => s + (parseFloat(r[key]) || 0), 0)
               .toLocaleString("ko-KR", { maximumFractionDigits: 0 });

    const cards = [
        ["총 레코드",    records.length.toLocaleString("ko-KR"), "primary",   "0d6efd"],
        ["입항",         arrivals.toLocaleString("ko-KR"),        "success",   "198754"],
        ["출항",         departures.toLocaleString("ko-KR"),      "warning",   "ffc107"],
        ["선박 종류 수", vtypes.toLocaleString("ko-KR"),          "info",      "0dcaf0"],
        ["선적톤 합계",  sumTon("ld_ton"),                         "secondary", "6c757d"],
        ["양하톤 합계",  sumTon("landng_ton"),                     "secondary", "6c757d"],
        ["환적톤 합계",  sumTon("trnpdt_ton"),                     "secondary", "6c757d"],
    ];

    document.getElementById("summary-cards").innerHTML = cards.map(
        ([label, value, cls, hex]) => `
        <div class="col-xl-3 col-md-4 col-6">
            <div class="card summary-card shadow-sm h-100"
                 style="border-left-color:#${hex}">
                <div class="card-body py-2">
                    <div class="text-muted small">${label}</div>
                    <div class="fs-5 fw-bold text-${cls}">${value}</div>
                </div>
            </div>
        </div>`
    ).join("");
}

/* ── 필터 드롭다운 자동 구성 ──────────────────────────── */
function populateFilterDropdowns(records) {
    const vtypes = [...new Set(records.map(r => r.vessel_type).filter(Boolean))].sort();
    const ctypes = [...new Set(records.map(r => r.cargo_type_name).filter(Boolean))].sort();

    document.getElementById("filter-vessel-type").innerHTML =
        `<option value="">전체 선박종류</option>` +
        vtypes.map(t => `<option value="${t}">${t}</option>`).join("");

    document.getElementById("filter-cargo-type").innerHTML =
        `<option value="">전체 화물종류</option>` +
        ctypes.map(t => `<option value="${t}">${t}</option>`).join("");
}

/* ── 필터 적용 ────────────────────────────────────────── */
function applyFilters() {
    const nameQ = document.getElementById("filter-vessel-name").value.toLowerCase();
    const vtQ   = document.getElementById("filter-vessel-type").value;
    const ctQ   = document.getElementById("filter-cargo-type").value;

    filteredRecords = allRecords.filter(r => {
        if (nameQ && !(r.vessel_name || "").toLowerCase().includes(nameQ)) return false;
        if (vtQ   && r.vessel_type      !== vtQ) return false;
        if (ctQ   && r.cargo_type_name  !== ctQ) return false;
        return true;
    });

    currentPage = 1;
    renderTable();
}

function resetFilters() {
    document.getElementById("filter-vessel-name").value = "";
    document.getElementById("filter-vessel-type").value = "";
    document.getElementById("filter-cargo-type").value = "";
    applyFilters();
}

/* ── 테이블 + 페이지네이션 ────────────────────────────── */
function renderTable() {
    const total      = filteredRecords.length;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const start      = (currentPage - 1) * PAGE_SIZE;
    const pageRecs   = filteredRecords.slice(start, start + PAGE_SIZE);

    document.getElementById("table-head").innerHTML =
        `<tr>${COLUMNS.map(([, label]) => `<th class="text-nowrap">${label}</th>`).join("")}</tr>`;

    document.getElementById("table-body").innerHTML = pageRecs.length
        ? pageRecs.map(r =>
            `<tr>${COLUMNS.map(([key]) =>
                `<td class="text-nowrap">${r[key] ?? ""}</td>`
            ).join("")}</tr>`
          ).join("")
        : `<tr><td colspan="${COLUMNS.length}" class="text-center text-muted py-4">
               조회 결과가 없습니다.
           </td></tr>`;

    document.getElementById("page-info").textContent =
        `총 ${total.toLocaleString("ko-KR")}건 / ${totalPages}페이지`;

    renderPagination(totalPages);
}

function renderPagination(totalPages) {
    const MAX_BTNS = 10;
    const half     = Math.floor(MAX_BTNS / 2);
    let   pStart   = Math.max(1, currentPage - half);
    let   pEnd     = Math.min(totalPages, pStart + MAX_BTNS - 1);
    if (pEnd - pStart < MAX_BTNS - 1) pStart = Math.max(1, pEnd - MAX_BTNS + 1);

    const items = [];
    items.push(li(currentPage === 1, "«", currentPage - 1));
    for (let p = pStart; p <= pEnd; p++)
        items.push(li(false, p, p, p === currentPage));
    items.push(li(currentPage === totalPages, "»", currentPage + 1));

    document.getElementById("pagination").innerHTML = items.join("");
}

function li(disabled, label, page, active = false) {
    return `<li class="page-item${disabled ? " disabled" : ""}${active ? " active" : ""}">
        <a class="page-link" onclick="goPage(${page})">${label}</a></li>`;
}

function goPage(p) {
    const totalPages = Math.ceil(filteredRecords.length / PAGE_SIZE);
    if (p < 1 || p > totalPages) return;
    currentPage = p;
    renderTable();
    document.getElementById("results-section").scrollIntoView({ behavior: "smooth" });
}

/* ── XLSX 다운로드 ────────────────────────────────────── */
function downloadXlsx() {
    const { prtAgCd, start_date, end_date } = currentParams;
    window.location.href =
        `/export?prtAgCd=${prtAgCd}&start_date=${start_date}&end_date=${end_date}`;
}

/* ── 유틸 ─────────────────────────────────────────────── */
function showLoading(visible) {
    document.getElementById("loading-msg").style.display = visible ? "block" : "none";
}

function showError(msg) {
    const el = document.getElementById("error-msg");
    el.textContent = msg;
    el.style.display = msg ? "block" : "none";
}
</script>
</body>
</html>
```

- [ ] **Step 2: 앱 서버 수동 기동 후 브라우저 확인**

```bash
python.exe app.py
```

브라우저에서 `http://127.0.0.1:5000` 접속 확인:
- 조회 폼 (드롭다운, 날짜 선택기, 조회 버튼) 렌더링 확인
- 직접 입력 토글 동작 확인 (드롭다운에서 "직접 입력..." 선택 시 텍스트필드 표시)

- [ ] **Step 3: 서버 종료 후 커밋**

```bash
git add templates/index.html
git commit -m "feat: complete HTML template with form, table, summary, filters"
```

---

## Task 6: 통합 스모크 테스트 + 최종 확인

**Files:** 없음 (수동 테스트)

- [ ] **Step 1: 전체 자동화 테스트 최종 실행**

```bash
python.exe -m pytest tests/ -v
```

Expected: 17개 모두 `PASSED`

- [ ] **Step 2: `SERVICE_KEY` 환경변수 설정 후 실제 API 조회 스모크 테스트**

```bash
$env:SERVICE_KEY="여기에_실제_서비스키"
python.exe app.py
```

브라우저에서 아래 시나리오 확인:
1. 여수항 (621), 기간 `2025-08-01 ~ 2025-08-07` 조회
2. Summary 카드 수치 확인 (총 레코드, 입항, 출항, 선박종류, 톤수)
3. 선박명 필터 텍스트 입력 → 테이블 즉시 갱신 확인
4. 선박종류 드롭다운 필터 → 테이블 갱신 확인
5. 초기화 버튼 → 필터 전체 해제 확인
6. 페이지 이동 버튼 (결과 100건 이상 시)
7. XLSX 다운로드 → 파일 열기 후 Summary 시트 / 상세 데이터 시트 확인

- [ ] **Step 3: 빈 결과 케이스 확인**

기간을 미래 날짜로 설정해 결과 없을 때 "조회 결과가 없습니다." 메시지 확인

- [ ] **Step 4: 최종 커밋**

```bash
git add .
git commit -m "feat: CheckPort web UI complete — Flask + client-side pagination/filter + XLSX export"
```

---

## 의존성 요약

```bash
python.exe -m pip install flask openpyxl
```

## 실행 명령

```bash
# 서비스키 환경변수 설정 (Windows PowerShell)
$env:SERVICE_KEY="발급받은_서비스키"

# 앱 기동
python.exe app.py
# → http://127.0.0.1:5000
```
