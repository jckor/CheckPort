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
