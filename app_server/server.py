#!/usr/bin/env python
# -*- coding: utf-8 -*-

# bottleのライブラリ
from bottle import route, run, request

# MySQLドライバはmysql.connector
import mysql.connector
import urllib.parse
import datetime
import pytz
import logging
import logging.handlers

# 補足
# 本当はテンプレートを入れるとHTMLが綺麗になります。
# その辺は後日…

# hostのIPアドレスは、$ docker inspect {データベースのコンテナ名}で調べる
# MySQLのユーザやパスワード、データベースはdocker-compose.ymlで設定したもの
# user     : MYSQL_USER
# password : MYSQL_PASSWORD
# database : MYSQL_DATABASE
instantaneous_connector = mysql.connector.connect (
            user     = 'bottle',
            password = 'bottle',
            host     = '172.19.0.3',
            database = 'instantaneous_measurement'
)

integrated_connector = mysql.connector.connect (
            user     = 'bottle',
            password = 'bottle',
            host     = '172.19.0.3',
            database = 'integrated_measurement'
)

logger = logging.getLogger('Logging')
logname = "/var/log/tools/bottle_server.log"
fmt = "%(asctime)s %(levelname)s %(name)s :%(message)s"
logging.basicConfig(level=10, format=fmt)
			
@route('/instantaneous_list')
def instantaneous_list():
    cursor = instantaneous_connector.cursor()
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
def integratd_list():
    cursor = integrated_connector.cursor()
    cursor.execute("select `integrated_power`, `power_delta`, `created_at` from integrated_value")

    disp  = "<table>"
    # ヘッダー
    disp += "<tr><th>積算電力(kWh)</th><th>差分(kwH)</th><th>計測日</th></tr>"
    
    # 一覧部分
    for row in cursor.fetchall():
        disp += "<tr><td>" + str(row[0]) + "</td><td>" + str(row[1]) + "</td><td>" + str(row[2]) + "</td><td>"
    
    disp += "</table>"
    
    cursor.close

    return "DBから取得 "+disp

@route('/input_instantaneous')
def input_instantaneous_power():
    logger.info(request.query)

    date_str = urllib.parse.unquote(request.query.date)

    # 瞬時値を入力
    cursor = instantaneous_connector.cursor()
    cursor.execute("INSERT INTO `instantaneous_value` (`server_id`, `power`, `created_at`, `created_user`, `updated_at`, `updated_user`) VALUES (" + request.query.server_id + ", " + request.query.power + ", '" + date_str + "', " + request.query.user_id + ", '" + date_str + "', " + request.query.user_id + ")")

    # コミット
    instantaneous_connector.commit()

    cursor.close

    return "OK"
    
    
@route('/input_integrated')
def input_integrated_power():
    logger.info(request.query)
    # 積算値を入力
    cursor = integrated_connector.cursor()
    
    date_str = urllib.parse.unquote(request.query.date)
    d = datetime.datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
    logger.info(date_str)
    logger.info(d)
    
    # 30分前
    _30min_before = d + datetime.timedelta(minutes=-30)
    _30min_before_str = _30min_before.strftime("%Y/%m/%d %H:%M:%S")
    logger.info(_30min_before_str)

    # 30分前の積算値を取得
    cursor.execute("SELECT `integrated_power`, `created_at` from integrated_value WHERE created_at='" + _30min_before_str+"'")
    
    _30min_power = 0
    
    record = cursor.fetchone()
    logger.info(record)

    if record != None :
        logger.info("found:"+str(cursor.fetchone()[0]))
   	    # ToDo: オーバーフロー処理
        _30min_power = request.query.integrated_power - cursor.fetchone()[1]

    cursor = integrated_connector.cursor()  
    cursor.execute("INSERT INTO `integrated_value` (`server_id`, `integrated_power`, `power_delta`, `power_charge`, `created_at`, `created_user`, `updated_at`, `updated_user`) VALUES (" + request.query.server_id + ", " + request.query.integrated_power + ", " + _30min_power + ", 0,'" + date_str + "'," + request.query.user_id + ", NOW(), " + request.query.user_id + ") on duplicate key update date=" + date_str + ", updated_at=NOW()")

    # コミット
    integrated_connector.commit()   

    cursor.close

    return "OK"
    

# コネクターをクローズ
integrated_connector.close
instantaneous_connector.close

# サーバ起動
run(host='0.0.0.0', port=8080, debug=True, reloader=True)