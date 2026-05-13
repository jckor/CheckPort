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
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, port=5000)
