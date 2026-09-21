from functools import wraps
from flask import Flask, jsonify, json, render_template, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash
import redis
from datetime import datetime, timedelta
from my_flask_app_secret import USER_DATA
from shared_config import POWER_ALERT_THRESHOLD_W, CO2_ALERT_THRESHOLD_PPM

auth = HTTPBasicAuth()
app = Flask(__name__)

# ダッシュボードの自動更新間隔 [秒]
REFRESH_SECONDS = 30

# 瞬時電力の計器スケール上限 [W]／目盛りの刻み [W]
POWER_SCALE_MAX_W = 6000
POWER_SCALE_STEP_W = 1000

# 閾値の何割から「警告」表示にするか
WARN_RATIO = 0.8

# 個別計測プラグ（計器パネルに内訳として並べる）
PLUG_KEYS = ("KEN_PLUG", "YACHI_PLUG")

# 部屋の空気は「部屋 × 測定項目」の表にする。列を揃えることで部屋どうしを
# 目で比較できる（どの部屋の CO2 が高いか、が一目で分かる）。
# Redis のキーは "<測定項目>_<部屋>" 形式。
ROOMS = (
    ("Bedroom", "BEDROOM"),
    ("Living Room", "LIVING"),
    ("Study Room", "STUDY"),
    ("1F", "1F"),
)
MEASURES = (
    ("Temp", "TEMPERATURE"),
    ("Humidity", "HUMIDITY"),
    ("CO₂", "CO2"),
    ("Light", "LIGHT_LEVEL"),
)


@auth.verify_password
def verify(username, password):
    """USER_DATA の値は generate_password_hash() で生成したハッシュ文字列。"""
    if not (username and password):
        return False
    password_hash = USER_DATA.get(username)
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)

# Redisクライアントのセットアップ
redis_client = redis.StrictRedis(host='redis', port=6379, decode_responses=True)

def get_redis_data():
    """
    Redisからデータを取得し、デコードして返す。
    エラー時にはNoneを返す。
    """
    try:
        value = redis_client.get('my_key')
        if not value:
            return None
        decoded_value = json.loads(value)
        if isinstance(decoded_value, str):
            decoded_value = json.loads(decoded_value)
        return decoded_value
    except Exception as e:
        app.logger.error(f"Error accessing Redis: {e}")
        return None


def validate_power_data(data):
    """
    POWERデータの存在と更新時間が条件を満たしているかを検証。
    条件を満たせばTrueを返し、満たさない場合はFalseを返す。
    """
    power_data = data.get("POWER")
    if not power_data or "value" not in power_data or "updated_at" not in power_data:
        return False

    try:
        # updated_atのフォーマットを検証し、現在時刻との差を計算
        updated_at = datetime.strptime(power_data["updated_at"], "%Y-%m-%d %H:%M:%S%z")
        current_time = datetime.now(updated_at.tzinfo)
        if current_time - updated_at > timedelta(minutes=1):
            return False
    except ValueError:
        return False

    return True


# --------------------------------------------------------------------------
# 表示用ヘルパー
# テンプレート側で計算せずに済むよう、ここで表示モデルを組み立てる。
# --------------------------------------------------------------------------

def sensor_meta(key):
    """センサーキーから (表示名, 単位, 目盛りレンジ) を返す。

    目盛り（バー）は「警報点までどれだけ余裕があるか」を示す装置なので、
    閾値を持つ POWER と CO2 にだけレンジを与える。それ以外は数値のみ。
    """
    if key == "KEN_PLUG":          return ("Ken's plug", "W", None)
    if key == "YACHI_PLUG":        return ("Yachi's plug", "W", None)
    if "TEMPERATURE" in key:       return ("Temp", "°C", None)
    if "HUMIDITY" in key:          return ("Humidity", "%", None)
    if "CO2" in key:               return ("CO₂", "ppm", (400, CO2_ALERT_THRESHOLD_PPM))
    if "LIGHT_LEVEL" in key:       return ("Light", "", None)
    if key == "POWER":             return ("Power", "W", (0, POWER_SCALE_MAX_W))
    return (key, "", None)


def as_float(value):
    """数値として解釈できれば float、できなければ None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_number(value):
    """1284.0 → '1,284'、24.1 → '24.1'。数値でなければそのまま文字列化。"""
    number = as_float(value)
    if number is None:
        return str(value)
    if number % 1:
        return f"{number:,.1f}"
    return f"{number:,.0f}"


def scale_percent(number, low, high):
    """レンジ内の位置を 0〜100 の整数で返す。"""
    if number is None or high == low:
        return None
    return max(0, min(100, round((number - low) / (high - low) * 100)))


def alert_state(key, number):
    """閾値に対する状態を '' / 'warn' / 'alert' で返す。閾値を持たないセンサーは常に ''。"""
    if number is None:
        return ""
    if key == "POWER":
        threshold = POWER_ALERT_THRESHOLD_W
    elif "CO2" in key:
        threshold = CO2_ALERT_THRESHOLD_PPM
    else:
        return ""
    if number > threshold:
        return "alert"
    if number >= threshold * WARN_RATIO:
        return "warn"
    return ""


def build_reading(key, entry):
    """Redis の 1 エントリを表示モデルへ変換する。データが無ければ None。"""
    if not isinstance(entry, dict) or "value" not in entry:
        return None
    label, unit, value_range = sensor_meta(key)
    number = as_float(entry["value"])
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "text": format_number(entry["value"]),
        "pct": scale_percent(number, *value_range) if value_range else None,
        "state": alert_state(key, number),
        "updated_at": entry.get("updated_at"),
    }


def build_hero(entry):
    """瞬時電力の計器表示モデル。POWER が無ければ None。"""
    reading = build_reading("POWER", entry)
    if reading is None:
        return None
    number = as_float(entry["value"])
    if number is None:
        # 数値として読めない値で目盛りを描くと 0 W に見えてしまうので、値だけ出す
        return {
            "text": reading["text"],
            "state": "",
            "note": "The meter returned a value that could not be read.",
            "updated_at": reading["updated_at"],
            "pct": None,
        }
    state = reading["state"]
    if state == "alert":
        note = f"Over the {POWER_ALERT_THRESHOLD_W:,} W alarm point."
    elif state == "warn":
        note = f"Nearing the {POWER_ALERT_THRESHOLD_W:,} W alarm point."
    else:
        note = f"Under the {POWER_ALERT_THRESHOLD_W:,} W alarm point."
    return {
        "text": reading["text"],
        "state": state,
        "note": note,
        "updated_at": reading["updated_at"],
        "pct": scale_percent(number, 0, POWER_SCALE_MAX_W) or 0,
        "alarm_pct": scale_percent(POWER_ALERT_THRESHOLD_W, 0, POWER_SCALE_MAX_W),
        "alarm_text": f"{POWER_ALERT_THRESHOLD_W:,}",
        "step_pct": round(POWER_SCALE_STEP_W / POWER_SCALE_MAX_W * 100, 3),
        "max": f"{POWER_SCALE_MAX_W:,}",
    }


def build_matrix(data):
    """部屋 × 測定項目の表を組み立てる。値が 1 つも無い行・列は落とす。"""
    columns = [
        (name, suffix) for name, suffix in ROOMS
        if any(f"{prefix}_{suffix}" in data for _, prefix in MEASURES)
    ]
    if not columns:
        return None

    rows = []
    for label, prefix in MEASURES:
        cells = [build_reading(f"{prefix}_{suffix}", data.get(f"{prefix}_{suffix}"))
                 for _, suffix in columns]
        if any(cells):
            rows.append({"label": label, "cells": cells})
    if not rows:
        return None

    # 部屋ごとの更新時刻は各センサーでほぼ同じなので、列に 1 つだけ出す
    ages = []
    for _, suffix in columns:
        stamps = [data[key]["updated_at"]
                  for key in (f"{prefix}_{suffix}" for _, prefix in MEASURES)
                  if isinstance(data.get(key), dict) and data[key].get("updated_at")]
        ages.append(max(stamps) if stamps else None)

    return {"columns": [name for name, _ in columns], "rows": rows, "ages": ages}


def build_view(data):
    """Redis のデータ全体からダッシュボードの表示モデルを組み立てる。"""
    return {
        "hero": build_hero(data.get("POWER")),
        "plugs": [r for r in (build_reading(k, data.get(k)) for k in PLUG_KEYS) if r],
        "matrix": build_matrix(data),
    }


def ip_based_authentication(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        app.logger.info(f"Request IP: {client_ip}")
        if client_ip == '172.19.0.20':
            app.logger.info("Applying basic authentication")
            return auth.login_required(f)(*args, **kwargs)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/get_data', methods=['GET'])
@ip_based_authentication
def get_data():
    try:
        data = get_redis_data()
        if data is None:
            return "No data found", 404

        return render_template(
            'dashboard.html',
            client_ip=request.remote_addr,
            refresh_seconds=REFRESH_SECONDS,
            power_threshold=POWER_ALERT_THRESHOLD_W,
            **build_view(data),
        )
    except Exception as e:
        app.logger.exception("Failed to render dashboard")
        return f"Error: {str(e)}", 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    RedisのPOWERデータを検証し、条件を満たす場合に200を返すエンドポイント。
    """
    try:
        data = get_redis_data()
        if data is None:
            return jsonify({"status": "fail", "reason": "No data in Redis"}), 503

        if not validate_power_data(data):
            return jsonify({"status": "fail", "reason": "POWER data is invalid or outdated"}), 503

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "reason": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
