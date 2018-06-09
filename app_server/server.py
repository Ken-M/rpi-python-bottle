# bottleのライブラリ
from bottle import route, run, request

# MySQLドライバはmysql.connector
import mysql.connector
import urllib.parse

# 補足
# 本当はテンプレートを入れるとHTMLが綺麗になります。
# その辺は後日…

# hostのIPアドレスは、$ docker inspect {データベースのコンテナ名}で調べる
# MySQLのユーザやパスワード、データベースはdocker-compose.ymlで設定したもの
# user     : MYSQL_USER
# password : MYSQL_PASSWORD
# database : MYSQL_DATABASE
connector = mysql.connector.connect (
            user     = 'bottle',
            password = 'bottle',
            host     = '172.17.0.3',
            database = 'measurement'
)


			
@route('/instantaneous_list')
def list():
    cursor = connector.cursor()
    cursor.execute("select `id`, `power`, `created_at` from instantaneous_value")

    disp  = "<table>"
    # ヘッダー
    disp += "<tr><th>ID</th><th>瞬時電力(W)</th><th>登録日</th></tr>"
    
    # 一覧部分
    for row in cursor.fetchall():
        disp += "<tr><td>" + str(row[0]) + "</td><td>" + str(row[1]) + "</td><td>" + str(row[2]) + "</td></tr>"
    
    disp += "</table>"
    
    cursor.close

    return "DBから取得 "+disp
    
@route('/integrated_list')
def list():
    cursor = connector.cursor()
    cursor.execute("select `id`, `integrated_power`, `power_delta`, `created_at` from integrated_value")

    disp  = "<table>"
    # ヘッダー
    disp += "<tr><th>ID</th><th>積算電力(kWh)</th><th>差分(kwH)</th><th>計測日</th></tr>"
    
    # 一覧部分
    for row in cursor.fetchall():
        disp += "<tr><td>" + str(row[0]) + "</td><td>" + str(row[1]) + "</td><td>" + str(row[2]) + "</td><td>" + str(row[3]) + "</td></tr>"
    
    disp += "</table>"
    
    cursor.close

    return "DBから取得 "+disp

@route('/input_instantaneous')
def input_instantaneous_power():
    # 瞬時値を入力
    cursor = connector.cursor()
    cursor.execute("INSERT INTO `instantaneous_value` (`server_id`, `power`, `created_at`, `created_user`, `updated_at`, `updated_user`) VALUES (" + request.query.server_id + ", " + request.query.power + ", NOW(), " + request.query.user_id + ", NOW(), " + request.query.user_id + ")")

    # コミット
    connector.commit();

    cursor.close

    return "OK"
    
    
@route('/input_integrated')
def input_integrated_power():
    # 積算値を入力
    cursor = connector.cursor()
    
    d = datetime.datetime.today()
    date_str = urllib.parse.unquote(request.query.date)
    d.strptime(date_str, "%Y/%m/%d %H:%M:%S")
    
    # 30分前
    30min_before = d - datetime.timedelta(minutes=-30)
    30min_before_str = 30min_before.strftime("%Y/%m/%d %H:%M:%S")
    
    # 30分前の積算値を取得
    cursor.execute("select `id`, `integrated_power`, `created_at` from integrated_value where created_at = " + 30min_before_str)
    
    30min_power = 0
    
    for row in cursor.fetchone()
    	# ToDo: オーバーフロー処理
    	30min_power = request.query.integrated_power - row[1]
    
    cursor.execute("INSERT INTO `integrated_value` (`server_id`, `integrated_power`, `power_delta`, `power_charge`, `created_at`, `created_user`, `updated_at`, `updated_user`) VALUES (" + request.query.server_id + ", " + request.query.integrated_power + ", " + 30min_power + ", 0," + urllib.parse.unquote(request.query.date)+ "," + request.query.user_id + ", NOW(), " + request.query.user_id + ") on duplicate key update date=" + urllib.parse.unquote(request.query.date) + ", updated_at=NOW()")

    # コミット
    connector.commit();
    
    

    cursor.close

    return "OK"
    

# コネクターをクローズ
connector.close

# サーバ起動
run(host='0.0.0.0', port=8080, debug=True, reloader=True)