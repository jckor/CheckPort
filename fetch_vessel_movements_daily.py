import requests
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import urlencode
from collections import defaultdict

def fetch_vessel_movements_daily(
    service_key: str,
    prtAgCd: str,
    start_date: str,
    end_date: str,
    out_csv: str = "yeosu_daily_movements.csv",
    raw_csv: str = "yeosu_raw_records.csv",
    per_page: int = 50
):
    """
    여수항(또는 지정 항만청코드)의 일별 선박 입출항 현황을 CSV로 저장합니다.

    Parameters
    ----------
    service_key : str
        공공데이터포털 발급 서비스키 (URL-encoded 필요 없음: 아래에서 자동 인코딩)
    prtAgCd : str
        항만청코드(3자리). 예) '020' (부산 예시) — 여수항 코드를 넣으세요.
    start_date : str
        조회 시작일 (YYYYMMDD)
    end_date : str
        조회 종료일 (YYYYMMDD)
    out_csv : str
        일별 집계 CSV 저장 경로
    raw_csv : str
        원시 레코드(상세) CSV 저장 경로
    per_page : int
        페이지당 조회 건수 (최대 50)
    """

    BASE = "http://apis.data.go.kr/1192000/VsslEtrynd5/Info5"
    # API 명세: prtAgCd(항만청코드), sde(시작일), ede(종료일), deGb(I/O), clsgn(호출부호, 옵션)
    # 상세 응답 필드(예시): etryptDt(입항일시), tkoffDt(출항일시), etryndNm('입항'/'출항'), vsslNm, clsgn 등

    def call_api(page_no: int):
        params = {
            "serviceKey": service_key,   # 가이드는 URL Encode 표기이나, requests가 처리하므로 원문 key 사용 가능
            "prtAgCd": prtAgCd,
            "sde": start_date,
            "ede": end_date,
            # deGb 생략 시 기본=I(입항기준)이나, 전체 포착 위해 생략하고 상세 detail에서 ‘입항/출항’ 모두 사용
            "pageNo": page_no,
            "numOfRows": per_page,
        }
        url = f"{BASE}?{urlencode(params, doseq=True)}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.text

    # 응답이 XML이므로 ElementTree로 파싱
    import xml.etree.ElementTree as ET

    all_details = []  # 원시 상세 레코드 수집

    # 첫 호출로 totalCount 파악
    first_xml = call_api(1)
    root = ET.fromstring(first_xml)
    # 에러 체크
    result_code = root.findtext(".//resultCode")
    result_msg  = root.findtext(".//resultMsg")
    if result_code != "00":
        raise RuntimeError(f"OpenAPI error: {result_code} - {result_msg}")

    total_count_text = root.findtext(".//totalCount")
    total_count = int(total_count_text) if total_count_text and total_count_text.isdigit() else 0

    def extract_items(xml_text: str):
        rt = ET.fromstring(xml_text)
        items = rt.findall(".//items/item")
        for it in items:
            # 상위 공통 필드
            port_code = it.findtext("prtAgCd")
            port_name = it.findtext("prtAgNm")
            call_sign = it.findtext("clsgn")
            vssl_nm   = it.findtext("vsslNm")
            # detail 배열
            details = it.findall(".//details/detail")
            for d in details:
                entry_exit = d.findtext("etryndNm")  # '입항' 또는 '출항'
                etrypt_dt  = d.findtext("etryptDt")  # 입항일시(ISO) 예: 2017-02-09T17:00:00+09:00
                tkoff_dt   = d.findtext("tkoffDt")   # 출항일시(ISO)
                berth_name = d.findtext("laidupFcltyNm")
                ibob_name  = d.findtext("ibobprtNm")  # 내외항구분명
                tug_yn     = d.findtext("tugYn")
                pilot_yn   = d.findtext("piltgYn")
                ldadngFrghtClCd = d.findtext("ldadngFrghtClCd")
                grtg       = d.findtext("grtg")       # 총톤수
                satmnt     = d.findtext("satmntEntrpsNm")

                # 일자 파싱: 입항/출항 각각의 일시가 다름
                if entry_exit == "입항" and etrypt_dt:
                    dt_str = etrypt_dt.split("+")[0].replace("T", " ")
                    date_only = dt_str.split(" ")[0]
                elif entry_exit == "출항" and tkoff_dt:
                    dt_str = tkoff_dt.split("+")[0].replace("T", " ")
                    date_only = dt_str.split(" ")[0]
                else:
                    # 일시가 없으면 스킵
                    continue

                all_details.append({
                    "date": date_only,               # YYYY-MM-DD
                    "entry_exit": entry_exit,        # 입항/출항
                    "port_code": port_code,
                    "port_name": port_name,
                    "vessel_name": vssl_nm,
                    "call_sign": call_sign,
                    "berth_name": berth_name,
                    "in_out": ibob_name,
                    "tug_used": tug_yn,
                    "pilot_used": pilot_yn,
                    "ldadngFrghtClCd": ldadngFrghtClCd,
                    "grtg": grtg,
                    "de_raw_entry_dt": etrypt_dt,
                    "de_raw_depart_dt": tkoff_dt,
                    "declarer": satmnt
                })

    # 페이지 루프
    if total_count == 0:
        print("조회 결과가 없습니다.")
    else:
        pages = (total_count + per_page - 1) // per_page
        # 첫 페이지에서 이미 한 번 파싱 필요
        extract_items(first_xml)
        for p in range(2, pages + 1):
            xml_text = call_api(p)
            extract_items(xml_text)

    # 원시 상세 CSV 저장
    if all_details:
        raw_df = pd.DataFrame(all_details)
        raw_df.sort_values(["date", "entry_exit", "vessel_name"], inplace=True)
        raw_df.to_csv(raw_csv, index=False, encoding="utf-8-sig")

        # 일자별 입항/출항 카운트 집계
        agg = defaultdict(lambda: {"arrivals": 0, "departures": 0})
        for r in all_details:
            if r["entry_exit"] == "입항":
                agg[r["date"]]["arrivals"] += 1
            elif r["entry_exit"] == "출항":
                agg[r["date"]]["departures"] += 1

        rows = []
        # 조회기간의 전체 날짜를 만들고, 누락일은 0으로
        sd = datetime.strptime(start_date, "%Y%m%d").date()
        ed = datetime.strptime(end_date, "%Y%m%d").date()
        cur = sd
        while cur <= ed:
            d = cur.isoformat()
            rows.append({
                "date": d,
                "arrivals": agg[d]["arrivals"] if d in agg else 0,
                "departures": agg[d]["departures"] if d in agg else 0
            })
            cur += timedelta(days=1)

        daily_df = pd.DataFrame(rows).sort_values("date")
        daily_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"[완료] 일별 집계: {out_csv} / 원시 상세: {raw_csv}")
    else:
        print("상세 레코드가 없어 CSV를 생성하지 않았습니다.")


# ===== 사용 예시 =====
# 여수항 prtAgCd(항만청코드)를 정확히 넣어주세요.
# fetch_vessel_movements_daily(
#     service_key="여기에_서비스키_붙여넣기",
#     prtAgCd="여수항_항만청코드(예:'0xx')",
#     start_date="20250801",  # YYYYMMDD
#     end_date="20250831",
#     out_csv="yeosu_daily_movements.csv",
#     raw_csv="yeosu_raw_records.csv",
#     per_page=50
# )
