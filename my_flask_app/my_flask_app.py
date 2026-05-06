from flask import Flask, jsonify, Response, render_template_string, json, request
from flask_httpauth import HTTPBasicAuth
import redis
from datetime import datetime, timedelta
from my_flask_app_secret import USER_DATA

auth = HTTPBasicAuth()
app = Flask(__name__)


@auth.verify_password
def verify(username, password):
    if not (username and password):
        return False
    return USER_DATA.get(username) == password

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

def ip_based_authentication(f):
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
        client_ip = request.remote_addr
        data = get_redis_data()
        if data is None:
            return "No data found", 404

        # 表示順序とグループ
        groups = {
            "Power and Plugs": ["POWER", "KEN_PLUG", "YACHI_PLUG"],
            "Bedroom": ["TEMPERATURE_BEDROOM", "HUMIDITY_BEDROOM", "CO2_BEDROOM", "LIGHT_LEVEL_BEDROOM"],
            "Living Room": ["TEMPERATURE_LIVING", "HUMIDITY_LIVING", "CO2_LIVING", "LIGHT_LEVEL_LIVING"],
            "Study Room": ["TEMPERATURE_STUDY", "HUMIDITY_STUDY", "CO2_STUDY", "LIGHT_LEVEL_STUDY"],
            "1F": ["TEMPERATURE_1F", "HUMIDITY_1F", "CO2_1F", "LIGHT_LEVEL_1F"]
        }

        def _sensor_range(key):
            if "CO2" in key:         return (400, 2000)
            if "TEMPERATURE" in key: return (10, 40)
            if "HUMIDITY" in key:    return (0, 100)
            if "LIGHT_LEVEL" in key: return (0, 20)
            if key == "POWER":       return (0, 6000)
            if "PLUG" in key:        return (0, 1500)
            return None

        def _sensor_unit(key):
            if "CO2" in key:         return "ppm"
            if "TEMPERATURE" in key: return "°C"
            if "HUMIDITY" in key:    return "%"
            if "LIGHT_LEVEL" in key: return ""
            if key == "POWER":       return "W"
            if "PLUG" in key:        return "W"
            return ""

        all_keys = [k for ks in groups.values() for k in ks]
        ranges = {k: _sensor_range(k) for k in all_keys if _sensor_range(k)}
        units  = {k: _sensor_unit(k)  for k in all_keys}

        # JSONをHTMLテーブルとして表示するテンプレート
        html_template = """
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Home Dashboard</title>
            <style>
                :root {
                    --bg: #f4f6fb;
                    --surface: #ffffff;
                    --surface2: #eef0f6;
                    --border: #d1d5e8;
                    --text: #1e2235;
                    --text-muted: #6470a0;
                    --accent: #6366f1;
                    --accent-glow: rgba(99,102,241,0.12);
                    --green: #16a34a;
                    --amber: #d97706;
                    --red: #dc2626;
                    --red-glow: rgba(220,38,38,0.10);
                    --heading-gradient: linear-gradient(135deg, #4f46e5, #6366f1);
                }
                @media (prefers-color-scheme: dark) {
                    :root {
                        --bg: #0f1117;
                        --surface: #1a1d27;
                        --surface2: #22263a;
                        --border: #2e3350;
                        --text: #e2e8f0;
                        --text-muted: #8892a4;
                        --accent: #6366f1;
                        --accent-glow: rgba(99,102,241,0.15);
                        --green: #22c55e;
                        --amber: #f59e0b;
                        --red: #ef4444;
                        --red-glow: rgba(239,68,68,0.15);
                        --heading-gradient: linear-gradient(135deg, #a5b4fc, #818cf8);
                    }
                }
                * { box-sizing: border-box; margin: 0; padding: 0; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    background: var(--bg);
                    color: var(--text);
                    min-height: 100vh;
                    padding: 24px 16px 48px;
                }
                header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    flex-wrap: wrap;
                    gap: 12px;
                    margin-bottom: 32px;
                    padding-bottom: 20px;
                    border-bottom: 1px solid var(--border);
                }
                header h1 {
                    font-size: 1.6rem;
                    font-weight: 700;
                    letter-spacing: -0.02em;
                    background: var(--heading-gradient);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                .header-meta {
                    display: flex;
                    align-items: center;
                    gap: 16px;
                    flex-wrap: wrap;
                }
                .meta-chip {
                    font-size: 0.78rem;
                    color: var(--text-muted);
                    background: var(--surface2);
                    border: 1px solid var(--border);
                    border-radius: 20px;
                    padding: 4px 12px;
                    white-space: nowrap;
                }
                .meta-chip span { color: var(--text); font-weight: 500; }
                .countdown-ring {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 0.78rem;
                    color: var(--text-muted);
                    background: var(--surface2);
                    border: 1px solid var(--border);
                    border-radius: 20px;
                    padding: 4px 12px;
                }
                .countdown-ring #countdown {
                    color: var(--accent);
                    font-weight: 700;
                    font-variant-numeric: tabular-nums;
                    min-width: 18px;
                    text-align: center;
                }
                .progress-bar {
                    width: 100%;
                    height: 2px;
                    background: var(--border);
                    border-radius: 2px;
                    overflow: hidden;
                    margin-bottom: 28px;
                }
                .progress-fill {
                    height: 100%;
                    background: linear-gradient(90deg, var(--accent), #a78bfa);
                    border-radius: 2px;
                    transition: width 1s linear;
                }
                .section { margin-bottom: 28px; }
                .section-header {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 10px;
                }
                .section-icon {
                    width: 8px; height: 8px;
                    border-radius: 50%;
                    background: var(--accent);
                    box-shadow: 0 0 6px var(--accent);
                    flex-shrink: 0;
                }
                .section-title {
                    font-size: 0.85rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.08em;
                    color: var(--text-muted);
                }
                .card {
                    background: var(--surface);
                    border: 1px solid var(--border);
                    border-radius: 12px;
                    overflow: hidden;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                thead th {
                    background: var(--surface2);
                    color: var(--text-muted);
                    font-size: 0.72rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.07em;
                    padding: 8px 16px;
                    text-align: left;
                    border-bottom: 1px solid var(--border);
                }
                tbody tr {
                    border-bottom: 1px solid var(--border);
                    transition: background 0.15s;
                }
                tbody tr:last-child { border-bottom: none; }
                tbody tr:hover { background: var(--surface2); }
                tbody td {
                    padding: 11px 16px;
                    font-size: 0.88rem;
                    vertical-align: middle;
                }
                td.key-column {
                    width: 30%;
                    color: var(--text-muted);
                    font-size: 0.82rem;
                    font-weight: 500;
                    font-family: 'SF Mono', 'Fira Code', monospace;
                    letter-spacing: 0.01em;
                }
                td.value-column {
                    width: 40%;
                    font-weight: 600;
                    font-size: 0.95rem;
                    color: var(--text);
                }
                td.updated-at-column {
                    width: 30%;
                    color: var(--text-muted);
                    font-size: 0.76rem;
                    font-variant-numeric: tabular-nums;
                }
                .badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 5px;
                    padding: 3px 10px;
                    border-radius: 6px;
                    font-size: 0.88rem;
                    font-weight: 600;
                }
                .badge-normal {
                    background: rgba(34,197,94,0.12);
                    color: var(--green);
                    border: 1px solid rgba(34,197,94,0.25);
                }
                .badge-alert {
                    background: var(--red-glow);
                    color: var(--red);
                    border: 1px solid rgba(239,68,68,0.3);
                    animation: pulse 1.8s ease-in-out infinite;
                }
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.6; }
                }
                .value-wrap { display: flex; flex-direction: column; gap: 6px; }
                .mini-bar {
                    height: 4px;
                    background: var(--border);
                    border-radius: 2px;
                    overflow: hidden;
                    width: 100%;
                    max-width: 240px;
                }
                .mini-bar-fill {
                    height: 100%;
                    border-radius: 2px;
                    background: linear-gradient(90deg, #22c55e, #4ade80);
                    transition: width 0.6s cubic-bezier(.4,0,.2,1);
                }
                .mini-bar-fill.bar-alert {
                    background: linear-gradient(90deg, var(--amber), var(--red));
                }
                .unit {
                    font-size: 0.72rem;
                    color: var(--text-muted);
                    font-weight: 400;
                    margin-left: 2px;
                }
                @media (max-width: 600px) {
                    td.updated-at-column { display: none; }
                    thead th:last-child { display: none; }
                    td.key-column { width: 45%; }
                    td.value-column { width: 55%; }
                }
            </style>
        </head>
        <body>
            <header>
                <h1>&#127968; Home Dashboard</h1>
                <div class="header-meta">
                    <div class="meta-chip">IP: <span>{{ client_ip }}</span></div>
                    <div class="meta-chip">Updated: <span id="lastReload">—</span></div>
                    <div class="countdown-ring">Reload in <span id="countdown">30</span>s</div>
                </div>
            </header>
            <div class="progress-bar"><div class="progress-fill" id="progressFill" style="width:100%"></div></div>

            {% for group_name, keys in groups.items() %}
            <div class="section">
                <div class="section-header">
                    <div class="section-icon"></div>
                    <div class="section-title">{{ group_name }}</div>
                </div>
                <div class="card">
                    <table>
                        <thead>
                            <tr>
                                <th class="key-column">Sensor</th>
                                <th class="value-column">Value</th>
                                <th class="updated-at-column">Updated At</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for key in keys %}
                            {% if key in data %}
                            <tr>
                                <td class="key-column">{{ key }}</td>
                                <td class="value-column">
                                    {% if data[key] is mapping and 'value' in data[key] %}
                                        {% set raw = data[key]['value'] %}
                                        {% set is_alert = (key == "POWER" and raw|float > 4800) or ("CO2" in key and raw|float > 1500) %}
                                        <div class="value-wrap">
                                            {% if is_alert %}
                                                <span class="badge badge-alert">
                                                    {% if key == "POWER" %}&#9889;{% else %}&#9888;{% endif %}
                                                    {{ raw }}<span class="unit">{{ units.get(key, '') }}</span>
                                                </span>
                                            {% else %}
                                                <span class="badge badge-normal">
                                                    {{ raw }}<span class="unit">{{ units.get(key, '') }}</span>
                                                </span>
                                            {% endif %}
                                            {% if key in ranges %}
                                                {% set rmin = ranges[key][0] %}
                                                {% set rmax = ranges[key][1] %}
                                                {% set pct = [[(( raw|float - rmin ) / ( rmax - rmin ) * 100)|int, 0]|max, 100]|min %}
                                                <div class="mini-bar">
                                                    <div class="mini-bar-fill{% if is_alert %} bar-alert{% endif %}" style="width:{{ pct }}%"></div>
                                                </div>
                                            {% endif %}
                                        </div>
                                    {% else %}
                                        <span class="badge badge-normal">{{ data[key] }}</span>
                                    {% endif %}
                                </td>
                                <td class="updated-at-column">
                                    {% if data[key] is mapping and 'updated_at' in data[key] %}
                                        {{ data[key]['updated_at'] }}
                                    {% else %}
                                        —
                                    {% endif %}
                                </td>
                            </tr>
                            {% endif %}
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            {% endfor %}

            <script>
                let countdown = 30;
                const countdownEl = document.getElementById('countdown');
                const lastReloadEl = document.getElementById('lastReload');
                const progressFill = document.getElementById('progressFill');

                lastReloadEl.textContent = new Date().toLocaleString('ja-JP');

                setInterval(() => {
                    countdown--;
                    countdownEl.textContent = countdown;
                    progressFill.style.width = (countdown / 30 * 100) + '%';
                    if (countdown <= 0) location.reload();
                }, 1000);
            </script>
        </body>
        </html>
        """
        return render_template_string(html_template, data=data, groups=groups, client_ip=client_ip, ranges=ranges, units=units)
    except Exception as e:
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
