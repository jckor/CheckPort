import requests
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import urlencode
from collections import defaultdict
import xml.etree.ElementTree as ET

CARGO_CODE_MAP = {
    "-":  "미분류",
    "1":  "산동물",
    "2":  "육과 식용설육",
    "3":  "어패류",
    "4":  "낙농품·조란·천연꿀",
    "5":  "기타 동물성 생산품",
    "6":  "산수목·꽃",
    "7":  "채소",
    "8":  "과실·견과류",
    "9":  "커피·차·향신료",
    "10": "곡물",
    "11": "곡물의 분과 조분 밀가루·전분",
    "12": "채유용 종자 인삼",
    "13": "식물성 엑스",
    "14": "기타 식물성 생산품",
    "15": "동식물성 유지",
    "16": "육·어류 조제품",
    "17": "당류·설탕과자",
    "18": "코코아 초콜렛",
    "19": "곡물·곡분의 주체품과 빵류",
    "20": "채소·과실의 조제품",
    "21": "기타의 조제 식료품",
    "22": "음료, 주류, 식초",
    "23": "조제사료",
    "24": "담배",
    "25": "토석류·소금",
    "26": "광 슬랙, 회",
    "27": "광물성 연료·에너지",
    "28": "무기화합물",
    "29": "유기 화합물",
    "30": "의료용품",
    "31": "비료",
    "32": "염료·안료·페인트 잉크",
    "33": "향료·화장품",
    "34": "비누·계면활성제 왁스",
    "35": "카세인·알부민 변성전분·효소",
    "36": "화약류·성냥",
    "37": "필름인화지 사진용재료",
    "38": "각종 화학공업 생산품",
    "39": "플라스틱과 그제품",
    "40": "고무와 그 제품",
    "41": "원피·가죽",
    "42": "가죽제품",
    "43": "모피, 모피제품",
    "44": "목재 목탄",
    "45": "코르크·짚",
    "46": "조물재료의 제품",
    "47": "펄프",
    "48": "지와판지",
    "49": "서적·신문 인쇄물",
    "50": "견·견사 견직물",
    "51": "양모·수모",
    "52": "면, 면사 면직물",
    "53": "마류의사와 직물",
    "54": "인조 필라멘트 섬유",
    "55": "인조 스테이플 섬유",
    "56": "워딩·부직포",
    "57": "양탄자",
    "58": "특수직물",
    "59": "침투 도포한 직물",
    "60": "편물",
    "61": "의류(편물제)",
    "62": "의류(편물제 이외)",
    "63": "기타 섬유제품·넝마",
    "64": "신발류",
    "65": "모자류",
    "66": "우산·지팡이",
    "67": "조제우모·인조제품",
    "68": "석, 시멘트, 석면제품",
    "69": "도자 제품",
    "70": "유리",
    "71": "귀석, 반귀석, 귀금속",
    "72": "철강",
    "73": "철강 제품",
    "74": "동과 그제품",
    "75": "니켈과 그제품",
    "76": "알루미늄과 그제품",
    "77": "<유보>",
    "78": "연과 그제품",
    "79": "아연과 그제품",
    "80": "주석과 그제품",
    "81": "기타의 비금속",
    "82": "비금속 제공구·스푼포크",
    "83": "각종 비금속 제품",
    "84": "보일러 기계류",
    "85": "전기기기·TV VTR",
    "86": "철도차량",
    "87": "일반차량",
    "88": "항공기",
    "89": "선박",
    "90": "광학·의료·측정·검사 정밀기기",
    "91": "시계",
    "92": "악기",
    "93": "무기",
    "94": "가구류·조명기구",
    "95": "완구·운동용구",
    "96": "잡품",
    "97": "예술품 골동품",
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

    def extract_items(xml_text: str) -> None:  # mutates all_details via closure
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
