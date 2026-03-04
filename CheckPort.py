from fetch_vessel_movements_daily import fetch_vessel_movements_daily

fetch_vessel_movements_daily(
    service_key="1ivAlQLTQlMF1UimfNRtjOiWCkWX68XaVMi6g02eqFLWqevvT3uxbdPrWpsewTRcPOhI3Qt1di6saBW2ODWyeg==",
    prtAgCd="621",                 # 여수항 항만청코드
    start_date="20250801",         # 조회 시작일 (YYYYMMDD)
    end_date="20250831",           # 조회 종료일 (YYYYMMDD)
    out_csv="yeosu_daily_movements_08.csv",
    raw_csv="yeosu_raw_records_08.csv"
)
