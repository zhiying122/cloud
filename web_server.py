"""
web_server.py — 健康監測系統 Web Server

提供 REST API 端點與內建單頁網頁介面，整合現有 HealthDatabase 進行唯讀資料存取。
"""

import argparse
import logging
import sys
import time

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from db_manager import HealthDatabase

# 設定日誌
logging.basicConfig(
    filename="health_monitor.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# CORS 允許的來源
CORS_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
]


def create_app(db_path: str) -> Flask:
    """
    建立並回傳設定好的 Flask 應用程式實例。

    Args:
        db_path: SQLite 資料庫檔案路徑

    Returns:
        已註冊所有路由的 Flask app 實例
    """
    app = Flask(__name__)

    # 套用 CORS 設定
    CORS(app, origins=CORS_ORIGINS)

    # 初始化 HealthDatabase
    db = None
    try:
        db = HealthDatabase(db_name=db_path)
        logger.info(f"HealthDatabase 初始化成功：{db_path}")
    except Exception as e:
        logger.error(f"HealthDatabase 初始化失敗：{e}")

    # ------------------------------------------------------------------ #
    # 路由：/ — 提供網頁介面
    # ------------------------------------------------------------------ #
    @app.route("/", methods=["GET"])
    def serve_index():
        """回傳 templates/index.html 的 HTML 內容。"""
        return render_template("index.html")

    # ------------------------------------------------------------------ #
    # 路由：/api/data — 歷史數據 API
    # ------------------------------------------------------------------ #
    @app.route("/api/data", methods=["GET"])
    def get_data():
        """
        取得最近 N 秒的歷史心率與血氧數據。

        Query Parameters:
            seconds (int): 查詢時間範圍（1–3600），預設 60

        Returns:
            200: {"heart_rate": [...], "spo2": [...], "time": [...], "count": N}
            400: {"error": "..."} — 參數無效
            500: {"error": "..."} — 資料庫錯誤
        """
        # 解析 seconds 參數
        seconds_str = request.args.get("seconds", "60")
        try:
            seconds = int(seconds_str)
        except (ValueError, TypeError):
            return jsonify({"error": "seconds 必須為正整數"}), 400

        if seconds <= 0 or seconds > 3600:
            return jsonify({"error": "seconds 必須介於 1 到 3600 之間"}), 400

        # 資料庫未初始化
        if db is None:
            return jsonify({"error": "資料庫連線失敗"}), 500

        try:
            data = db.get_recent_data(seconds=seconds)
            data["count"] = len(data["heart_rate"])
            return jsonify(data), 200
        except Exception as e:
            logger.error(f"get_data 資料庫讀取失敗：{e}")
            return jsonify({"error": "資料庫讀取失敗"}), 500

    # ------------------------------------------------------------------ #
    # 路由：/api/latest — 最新數據 API
    # ------------------------------------------------------------------ #
    @app.route("/api/latest", methods=["GET"])
    def get_latest():
        """
        取得最新一筆感測數據及其健康狀態。

        Returns:
            200: {"heart_rate": float|null, "spo2": float|null,
                  "timestamp": float|null, "status": "normal"|"warning"|"no_data"}
            500: {"error": "..."} — 資料庫錯誤
        """
        if db is None:
            return jsonify({"error": "資料庫連線失敗"}), 500

        try:
            data = db.get_recent_data(seconds=60)

            if not data["heart_rate"]:
                return jsonify({
                    "heart_rate": None,
                    "spo2": None,
                    "timestamp": None,
                    "status": "no_data",
                }), 200

            # 取最後一筆（最新）記錄
            hr = data["heart_rate"][-1]
            spo2 = data["spo2"][-1]
            ts = data["time"][-1]

            # 判斷健康狀態
            try:
                hr_val = float(hr)
                spo2_val = float(spo2)
                if spo2_val < 95 or hr_val < 60 or hr_val > 100:
                    status = "warning"
                else:
                    status = "normal"
            except (TypeError, ValueError):
                status = "warning"

            return jsonify({
                "heart_rate": hr,
                "spo2": spo2,
                "timestamp": ts,
                "status": status,
            }), 200

        except Exception as e:
            logger.error(f"get_latest 資料庫讀取失敗：{e}")
            return jsonify({"error": "資料庫讀取失敗"}), 500

    # ------------------------------------------------------------------ #
    # 路由：/api/health — 健康檢查 API
    # ------------------------------------------------------------------ #
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """
        確認 Web Server 與資料庫的運作狀態。

        Returns:
            200: {"status": "ok"|"degraded", "db": "connected"|"disconnected",
                  "timestamp": float}
        """
        ts = time.time()

        if db is None:
            return jsonify({
                "status": "degraded",
                "db": "disconnected",
                "timestamp": ts,
            }), 200

        try:
            import sqlite3
            conn = sqlite3.connect(db.db_name)
            conn.execute("SELECT 1")
            conn.close()
            return jsonify({
                "status": "ok",
                "db": "connected",
                "timestamp": ts,
            }), 200
        except Exception as e:
            logger.error(f"health_check 資料庫連線失敗：{e}")
            return jsonify({
                "status": "degraded",
                "db": "disconnected",
                "timestamp": ts,
            }), 200

    return app


# ------------------------------------------------------------------ #
# 主程式進入點
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="健康監測系統 Web Server")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="綁定的主機位址（預設：127.0.0.1）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="監聽的埠號（預設：5000）",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="health_data.db",
        help="SQLite 資料庫檔案路徑（預設：health_data.db）",
    )

    args = parser.parse_args()

    # 驗證 host 格式（不可為空字串）
    if not args.host or not args.host.strip():
        print("錯誤：--host 參數不可為空", file=sys.stderr)
        sys.exit(1)

    # 驗證 port 範圍（1–65535）
    if not (1 <= args.port <= 65535):
        print(f"錯誤：--port 必須介於 1 到 65535 之間，收到：{args.port}", file=sys.stderr)
        sys.exit(1)

    app = create_app(db_path=args.db)
    print(f"Web Server 啟動中：http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
