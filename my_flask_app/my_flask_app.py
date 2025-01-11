from flask import Flask, jsonify, Response, render_template_string, json
import redis
from datetime import datetime, timedelta

app = Flask(__name__)

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

@app.route('/get_data', methods=['GET'])
def get_data():
    """
    Redisからデータを取得し、HTML形式で表示するエンドポイント。
    """
    try:
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

        # JSONをHTMLテーブルとして表示するテンプレート
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>JSON Data Table</title>
            <style>
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }
                th, td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                th {
                    background-color: #f4f4f4;
                }
                td.key-column {
                    width: 25%;
                }
                td.value-column {
                    width: 50%;
                }
                td.updated-at-column {
                    width: 25%;
                }
                h2 {
                    margin-top: 20px;
                }
                .alert {
                    color: red;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <h1>JSON Data Table</h1>
            <p>Reload in <span id="countdown">30</span> seconds</p>
            <p>Last reload: <span id="lastReload">Not yet</span></p>
            {% for group_name, keys in groups.items() %}
            <h2>{{ group_name }}</h2>
            <table>
                <thead>
                    <tr>
                        <th>Key</th>
                        <th>Value</th>
                        <th>Updated At</th>
                    </tr>
                </thead>
                <tbody>
                    {% for key in keys %}
                    {% if key in data %}
                    <tr>
                        <td class="key-column">{{ key }}</td>
                        <td class="value-column">
                            {% if data[key] is mapping and 'value' in data[key] %}
                                {% if key == "POWER" and data[key]['value']|float > 4800 %}
                                    <span class="alert">{{ data[key]['value'] }}</span>
                                {% elif "CO2" in key and data[key]['value']|float > 1500 %}
                                    <span class="alert">{{ data[key]['value'] }}</span>
                                {% else %}
                                    {{ data[key]['value'] }}
                                {% endif %}
                            {% else %}
                                {{ data[key] }}
                            {% endif %}
                        </td>
                        <td class="updated-at-column">
                            {% if data[key] is mapping and 'updated_at' in data[key] %}
                                {{ data[key]['updated_at'] }}
                            {% else %}
                                N/A
                            {% endif %}
                        </td>
                    </tr>
                    {% endif %}
                    {% endfor %}
                </tbody>
            </table>
            {% endfor %}
            <script>
                let countdown = 30;
                const countdownElement = document.getElementById('countdown');
                const lastReloadElement = document.getElementById('lastReload');

                function updateCountdown() {
                    countdown--;
                    if (countdown <= 0) {
                        location.reload();
                    } else {
                        countdownElement.textContent = countdown;
                    }
                }

                function updateLastReload() {
                    const now = new Date();
                    lastReloadElement.textContent = now.toLocaleString();
                }

                // Update the countdown every second
                setInterval(updateCountdown, 1000);

                // Update the last reload time when the page loads
                updateLastReload();
            </script>
        </body>
        </html>
        """
        return render_template_string(html_template, data=data, groups=groups)
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
