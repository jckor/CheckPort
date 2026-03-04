import requests
import pandas as pd
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
from datetime import date

# =========================
# 설정
# =========================
SERVICE_KEY = "1ivAlQLTQlMF1UimfNRtjOiWCkWX68XaVMi6g02eqFLWqevvT3uxbdPrWpsewTRcPOhI3Qt1di6saBW2ODWyeg=="  # data.go.kr 또는 YGPA 개발계정에서 발급
PRT_AT_CODE = "620"  # 여수항 코드(가이드: prt_at_code, 3자리)  :contentReference[oaicite:1]{index=1}
YEAR = "2025"
YM_FROM = "202501"
YM_TO = "202508"

BASE = "http://www.ygpa.or.kr:9191/openapi/service"

# 엔드포인트 (가이드의 서비스 ID/URL 매핑)  :contentReference[oaicite:2]{index=2}
ENDPOINTS = {
    "StatCargoFac": f"{BASE}/statCargoFac/getStatCargoFac",     # SC-04: 부두별 화물 통계
    "StatCargoItem": f"{BASE}/statCargoItem/getStatCargoItem",  # SC-02: 품목별 화물 통계
    "StatVsslFac": f"{BASE}/statVsslFac/getStatVsslFac",        # SC-13: 부두별 선박접안 통계
    "StatVsslMonth": f"{BASE}/statVsslMonth/getStatVsslMonth",  # SC-10: 월별 선박 입출항 통계
    # 필요시 추가: 국가/지역/컨테이너 통계 등
}

def get_xml(url: str, params: dict) -> ET.Element:
    """YGPA OpenAPI XML 호출 + 파싱"""
    q = params.copy()
    q["ServiceKey"] = SERVICE_KEY  # 헤더 대신 쿼리로 전달 (가이드 예시와 동일)  :contentReference[oaicite:3]{index=3}
    full = f"{url}?{urlencode(q)}"
    r = requests.get(full, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    # 정상 응답 확인
    result_code = root.findtext(".//resultCode")
    if result_code != "00":
        msg = root.findtext(".//resultMsg") or "Unknown error"
        raise RuntimeError(f"API error ({result_code}): {msg}")
    return root

def xml_items_to_records(root: ET.Element) -> list[dict]:
    """<items><item>...</item></items> → list[dict]"""
    records = []
    for item in root.findall(".//items/item"):
        rec = {}
        for child in item:
            rec[child.tag] = child.text
        records.append(rec)
    return records

# -------------------------
# 1) 부두별 화물 통계 (SC-04)  :contentReference[oaicite:4]{index=4}
# 요청: prt_at_code, yyyymmfr, yyyymmto, g_in_out(옵션)
# 응답 주요필드: title(부두명), totTon, totOceanTon, korTon, forTon, coastTon
# -------------------------
def fetch_stat_cargo_fac(prt_at_code: str, ym_from: str, ym_to: str, g_in_out: str | None = None) -> pd.DataFrame:
    params = {
        "prt_at_code": prt_at_code,
        "yyyymmfr": ym_from,
        "yyyymmto": ym_to,
    }
    if g_in_out:
        params["g_in_out"] = g_in_out  # I(수입), O(수출), 미지정 시 전체  :contentReference[oaicite:5]{index=5}
    root = get_xml(ENDPOINTS["StatCargoFac"], params)
    recs = xml_items_to_records(root)
    df = pd.DataFrame(recs)
    # 컬럼 정리
    rename = {
        "title": "부두명",
        "totTon": "총톤수",
        "totOceanTon": "외항톤수",
        "korTon": "외항_아국적톤수",
        "forTon": "외항_외국적톤수",
        "coastTon": "연안톤수",
    }
    df = df.rename(columns=rename)
    return df

# -------------------------
# 2) 품목별 화물 통계 (SC-02)  :contentReference[oaicite:6]{index=6}
# 요청: prt_at_code, yyyy
# 응답: title(품목명), totTon/forTon/korTon/coastTon
# -------------------------
def fetch_stat_cargo_item(prt_at_code: str, yyyy: str) -> pd.DataFrame:
    params = {"prt_at_code": prt_at_code, "yyyy": yyyy}
    root = get_xml(ENDPOINTS["StatCargoItem"], params)
    recs = xml_items_to_records(root)
    df = pd.DataFrame(recs)
    rename = {
        "title": "품목명",
        "totTon": "총톤수",
        "totOceanTon": "외항톤수",
        "korTon": "외항_아국적톤수",
        "forTon": "외항_외국적톤수",
        "coastTon": "연안톤수",
    }
    df = df.rename(columns=rename)
    # 합계 행은 맨 마지막에 나오는 경우가 많음 → 숫자형 변환 전 문자열로 둠
    return df

# -------------------------
# 3) 부두별 선박 접안 통계 (SC-13)  :contentReference[oaicite:7]{index=7}
# 요청: prt_at_code, yyyymmfr, yyyymmto
# 응답: title(부두명), totCnt(총 접안척수), oceanCnt/korCnt/forCnt/coastCnt 등(가이드 표 참조)
# ※ 가이드에 명세와 예시가 있으나 필드명이 버전에 따라 달릴 수 있어 item 덤프 형태로 저장 권장.
# -------------------------
def fetch_stat_vssl_fac(prt_at_code: str, ym_from: str, ym_to: str) -> pd.DataFrame:
    params = {"prt_at_code": prt_at_code, "yyyymmfr": ym_from, "yyyymmto": ym_to}
    root = get_xml(ENDPOINTS["StatVsslFac"], params)
    recs = xml_items_to_records(root)
    return pd.DataFrame(recs)

# -------------------------
# 4) 월별 선박 입출항 통계 (SC-10)  :contentReference[oaicite:8]{index=8}
# 요청: prt_at_code, yyyy, (g_in_out 옵션)
# 응답: title(월), totCnt(총척수) 등(가이드는 톤수 중심 예시이나 API 버전에 따라 건수 제공)
# -------------------------
def fetch_stat_vssl_month(prt_at_code: str, yyyy: str, g_in_out: str | None = None) -> pd.DataFrame:
    params = {"prt_at_code": prt_at_code, "yyyy": yyyy}
    if g_in_out:
        params["g_in_out"] = g_in_out
    root = get_xml(ENDPOINTS["StatVsslMonth"], params)
    recs = xml_items_to_records(root)
    return pd.DataFrame(recs)

def save_csv(df: pd.DataFrame, path: str):
    if df is None or df.empty:
        print(f"[경고] 저장할 데이터가 없습니다: {path}")
        return
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"[저장 완료] {path}  (행:{len(df)})")

if __name__ == "__main__":
    print(f"=== YGPA OpenAPI 2025 조회 (여수항 {PRT_AT_CODE}) ===")
    # 1) 2025년 1~12월, 부두별 화물(톤수)
    df_cargo_fac_all = fetch_stat_cargo_fac(PRT_AT_CODE, YM_FROM, YM_TO, g_in_out=None)
    save_csv(df_cargo_fac_all, f"ygpa_yeosu_{YEAR}_부두별화물_전체.csv")

    # 2) 2025년 품목별 화물
    df_cargo_item = fetch_stat_cargo_item(PRT_AT_CODE, YEAR)
    save_csv(df_cargo_item, f"ygpa_yeosu_{YEAR}_품목별화물.csv")

    # 3) 2025년 1~12월, 부두별 선박접안
    df_vssl_fac = fetch_stat_vssl_fac(PRT_AT_CODE, YM_FROM, YM_TO)
    save_csv(df_vssl_fac, f"ygpa_yeosu_{YEAR}_부두별접안.csv")

    # 4) 2025년 월별 선박 입출항 통계(수입/수출 전체)
    df_vssl_month_all = fetch_stat_vssl_month(PRT_AT_CODE, YEAR, g_in_out=None)
    save_csv(df_vssl_month_all, f"ygpa_yeosu_{YEAR}_월별선박입출항_전체.csv")

    print("완료.")
