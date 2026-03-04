"""
Daily runner for CheckPort.
Fetches yesterday's vessel movements automatically.
Intended to be called by Windows Task Scheduler via run_daily.bat.
"""
from datetime import date, timedelta
from fetch_vessel_movements_daily import fetch_vessel_movements_daily

SERVICE_KEY = "1ivAlQLTQlMF1UimfNRtjOiWCkWX68XaVMi6g02eqFLWqevvT3uxbdPrWpsewTRcPOhI3Qt1di6saBW2ODWyeg=="
PRT_AG_CD = "621"  # 여수항

yesterday = date.today() - timedelta(days=1)
date_str = yesterday.strftime("%Y%m%d")

print(f"Fetching vessel movements for {yesterday} ...")

fetch_vessel_movements_daily(
    service_key=SERVICE_KEY,
    prtAgCd=PRT_AG_CD,
    start_date=date_str,
    end_date=date_str,
    out_csv=f"data\\daily_{date_str}.csv",
    raw_csv=f"data\\raw_{date_str}.csv",
)
