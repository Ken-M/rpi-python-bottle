from flask import Flask, render_template_string, json
import redis

app = Flask(__name__)

# Redisクライアントのセットアップ
redis_client = redis.StrictRedis(host='redis', port=6379, decode_responses=True)

@app.route('/get_data', methods=['GET'])
def get_data():
    try:
        # Redisからデータを取得
        value = redis_client.get('my_key')
        if value is None:
            return "No data found", 404

        # Redisから取得したデータをデコード
        decoded_value = json.loads(value)
        if isinstance(decoded_value, str):
            decoded_value = json.loads(decoded_value)

        # 表示順序とグループ
        keys_order = [
            "POWER", "KEN_PLUG", "YACHI_PLUG",
            "BED_ROOM_PLUG", "TEMPERATURE_BEDROOM", "HUMIDITY_BEDROOM", "CO2_BEDROOM", "LIGHT_LEVEL_BEDROOM",
            "TEMPERATURE_LIVING", "HUMIDITY_LIVING", "CO2_LIVING", "LIGHT_LEVEL_LIVING",
            "TEMPERATURE_STUDY", "HUMIDITY_STUDY", "CO2_STUDY", "LIGHT_LEVEL_STUDY",
            "TEMPERATURE_1F", "HUMIDITY_1F", "CO2_1F", "LIGHT_LEVEL_1F"
        ]

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
                        <td>{{ key }}</td>
                        <td>
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
                        <td>
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
        </body>
        </html>
        """
        return render_template_string(html_template, data=decoded_value, groups=groups)
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
