from flask import Flask, jsonify, json
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
            return jsonify({"error": "No data found"}), 404
        ret_value = data = json.loads(value)
        return jsonify(ret_value), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)