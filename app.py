import os
import io
import re
from flask import Flask, request, jsonify, render_template, send_file
from fetch_vessel_movements_daily import fetch_vessel_records
from dotenv import load_dotenv
import openpyxl

load_dotenv()

app = Flask(__name__)
SERVICE_KEY = os.environ.get("SERVICE_KEY", "")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/query", methods=["POST"])
def query():
    data = request.get_json() or {}
    prtAgCd    = data.get("prtAgCd", "").strip()
    start_date = data.get("start_date", "").strip()
    end_date   = data.get("end_date", "").strip()
    if not prtAgCd or not start_date or not end_date:
        return jsonify({"error": "prtAgCd, start_date, end_date 가 필요합니다."}), 400
    if not re.fullmatch(r'\d{8}', start_date) or not re.fullmatch(r'\d{8}', end_date):
        return jsonify({"error": "날짜 형식은 YYYYMMDD (8자리 숫자)여야 합니다."}), 400
    if start_date > end_date:
        return jsonify({"error": "start_date는 end_date보다 늦을 수 없습니다."}), 400
    try:
        records = fetch_vessel_records(SERVICE_KEY, prtAgCd, start_date, end_date)
        return jsonify({"records": records, "total": len(records)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


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
    if not re.fullmatch(r'\d{8}', start_date) or not re.fullmatch(r'\d{8}', end_date):
        return "날짜 형식은 YYYYMMDD (8자리 숫자)여야 합니다.", 400
    if start_date > end_date:
        return "start_date는 end_date보다 늦을 수 없습니다.", 400
    try:
        records = fetch_vessel_records(SERVICE_KEY, prtAgCd, start_date, end_date)
    except Exception as e:
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

    safe_port = re.sub(r'[^\w-]', '_', prtAgCd)
    filename = f"vessel_movements_{safe_port}_{start_date}_{end_date}.xlsx"
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, port=5000)
