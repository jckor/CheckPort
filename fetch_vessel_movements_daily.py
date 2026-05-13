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
