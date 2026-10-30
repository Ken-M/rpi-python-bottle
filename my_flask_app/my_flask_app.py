from functools import wraps
from flask import Flask, jsonify, json, render_template, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash, generate_password_hash
import ipaddress
import redis
import secrets
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

# ngrok コンテナの固定 IP。ここから来たリクエストにだけ Basic 認証を課す
NGROK_IP = '172.19.0.20'

# Basic 認証の総当たり対策（ngrok 経由のリクエストにだけ適用）。
# 失敗回数を Redis で数え（gunicorn の全ワーカーで共有するため）、最初の失敗から
# AUTH_FAIL_WINDOW_SECONDS 秒のうちに上限に達したら、その窓が明けるまで 429 を返す。
AUTH_FAIL_WINDOW_SECONDS = 15 * 60
AUTH_FAIL_LIMIT_PER_IP = 10
# 多数の IP に分散した総当たりへの歯止め。到達すると ngrok 経由は全員が一時的に締め出される
AUTH_FAIL_LIMIT_GLOBAL = 100
AUTH_FAIL_KEY_PREFIX = "auth_fail:"

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
        # 認証ダイアログを出すための最初のリクエスト（資格情報なし）は失敗に数えない
        return False
    ok = check_credentials(username, password)
    client_ip = get_tunnel_client_ip()
    try:
        if ok:
            clear_auth_failures(client_ip)
        else:
            record_auth_failure(client_ip)
    except redis.RedisError:
        app.logger.exception("Failed to update auth failure count")
    return ok


def _hash_method(password_hash):
    """ハッシュ文字列 "方式$salt$hash" の方式部分（例: "scrypt:32768:8:1"）を返す。

    check_password_hash() が導出まで進まない形式なら None。
    """
    if not isinstance(password_hash, str):
        return None
    parts = password_hash.split("$", 2)
    if len(parts) != 3:
        return None
    return parts[0]


def _make_dummy_hashes():
    """USER_DATA に現れるハッシュ方式ごとに、誰のパスワードとも一致しないダミーハッシュを作る。

    導出コストは方式文字列（アルゴリズムとパラメーター）で決まるので、
    同じ方式で作ったダミーとの照合は本物との照合と同じ時間がかかる。
    解釈できない方式は起動を止めずに飛ばす（そのユーザーのログイン時に従来どおりエラーになる）。
    """
    dummies = {}
    for password_hash in USER_DATA.values():
        method = _hash_method(password_hash)
        if method is None or method in dummies:
            continue
        try:
            dummies[method] = generate_password_hash(secrets.token_urlsafe(32), method=method)
        except Exception:
            continue
    return dummies


# 方式文字列 → ダミーハッシュ。ユーザー名の有無で応答時間が変わらないようにするために使う。
_DUMMY_HASHES = _make_dummy_hashes()


def check_credentials(username, password):
    """ユーザー名の存在が応答時間から漏れないよう、ユーザーの有無にかかわらず
    USER_DATA に現れる全方式について 1 回ずつ導出を行う。存在するユーザーの方式だけは
    本物のハッシュで照合し、それ以外の方式はダミーで照合して結果を捨てる。
    """
    password_hash = USER_DATA.get(username)
    own_method = _hash_method(password_hash) if password_hash else None
    for method, dummy_hash in _DUMMY_HASHES.items():
        if method != own_method:
            check_password_hash(dummy_hash, password)
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def get_tunnel_client_ip():
    """ngrok 経由のリクエストの接続元 IP を返す。

    ngrok が付ける X-Forwarded-For の末尾（ngrok 自身が追記した値）を使う。
    それより前の値はクライアントが自由に書けるので信用しない。
    取れなければ ngrok コンテナの IP を返す（全員が同じ枠に入るので安全側）。
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    candidate = forwarded.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return request.remote_addr


def _auth_fail_keys(client_ip):
    return (f"{AUTH_FAIL_KEY_PREFIX}ip:{client_ip}", f"{AUTH_FAIL_KEY_PREFIX}global")


def auth_lockout_seconds(client_ip):
    """IP 単位または全体の失敗回数が上限に達していれば、締め出しが解けるまでの秒数を返す。

    上限に達していなければ 0。
    """
    ip_key, global_key = _auth_fail_keys(client_ip)
    pipe = redis_client.pipeline()
    pipe.get(ip_key)
    pipe.ttl(ip_key)
    pipe.get(global_key)
    pipe.ttl(global_key)
    ip_count, ip_ttl, global_count, global_ttl = pipe.execute()

    wait = 0
    for count, ttl, limit in ((ip_count, ip_ttl, AUTH_FAIL_LIMIT_PER_IP),
                              (global_count, global_ttl, AUTH_FAIL_LIMIT_GLOBAL)):
        if count is not None and int(count) >= limit:
            wait = max(wait, ttl if ttl > 0 else AUTH_FAIL_WINDOW_SECONDS)
    return wait


def record_auth_failure(client_ip):
    # INCR と EXPIRE を 1 トランザクションで送り、期限なしのキーが残らないようにする。
    # EXPIRE NX なので、窓の起点は最初の失敗のまま延びない。
    pipe = redis_client.pipeline()
    for key in _auth_fail_keys(client_ip):
        pipe.incr(key)
        pipe.expire(key, AUTH_FAIL_WINDOW_SECONDS, nx=True)
    pipe.execute()


def clear_auth_failures(client_ip):
    # 認証に成功した IP の失敗回数だけを消す（全体の回数は窓が明けるまで残す）
    ip_key, _ = _auth_fail_keys(client_ip)
    redis_client.delete(ip_key)


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
        if client_ip == NGROK_IP:
            app.logger.info("Applying basic authentication")
            tunnel_ip = get_tunnel_client_ip()
            try:
                wait = auth_lockout_seconds(tunnel_ip)
            except redis.RedisError:
                # 失敗回数を確かめられないまま認証を通すと総当たりの歯止めが外れるので、閉じる側に倒す
                app.logger.exception("Failed to check auth failure count")
                return "Service Unavailable", 503
            if wait:
                app.logger.warning(f"Too many auth failures, locked out: {tunnel_ip} ({wait}s)")
                return "Too Many Requests", 429, {"Retry-After": str(wait)}
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
