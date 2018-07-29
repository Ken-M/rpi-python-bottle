#!/usr/bin/env python
# -*- coding: utf-8 -*-

# bottleのライブラリ
from bottle import route, run, request

# MySQLドライバはmysql.connector
import mysql.connector
import urllib.parse
import datetime
import logging
import logging.handlers
import jpholiday

from retry import retry

# 補足
# 本当はテンプレートを入れるとHTMLが綺麗になります。
# その辺は後日…

# hostのIPアドレスは、$ docker inspect {データベースのコンテナ名}で調べる
# MySQLのユーザやパスワード、データベースはdocker-compose.ymlで設定したもの
# user     : MYSQL_USER
# password : MYSQL_PASSWORD
# database : MYSQL_DATABASE

instantaneous_connector = mysql.connector.cursor
integrated_connector = mysql.connector.cursor
temperature_connector = mysql.connector.cursor



def isHoliday(check_date):
    if(check_date.date.weekday >= 5) :
        return True
    if( jpholiday.isHoliday(check_date.date) ) :
        return True
    if( (check_date.date.month == 1) and (check_date.date.day == 2) ):
        return True
    if( (check_date.date.month == 1) and (check_date.date.day == 3) ):
        return True       
    if( (check_date.date.month == 4) and (check_date.date.day == 30) ):
        return True
    if( (check_date.date.month == 5) and (check_date.date.day == 1) ):
        return True
    if( (check_date.date.month == 5) and (check_date.date.day == 2) ):
        return True
    if( (check_date.date.month == 12) and (check_date.date.day == 30) ):
        return True
    if( (check_date.date.month == 12) and (check_date.date.day == 31) ):
        return True
    return False


def get_price_unit(check_date):
    logger.info(check_date)
    logger.info(check_date.date)
    logger.info(check_date.time)
    check_time = check_date.time - datetime.timedelta(minutes=10)
    logger.info(check_time)

    if( (22 <= check_time.hour) or (check_time.hour <= 8) ) :
        return 17.65

    if( isHoliday(check_date) == False ) :
        if((9<= check_time.hour) or (check_time.hour <= 18)) :
            return 32.45

    return 25.62

  



@retry()
def connect_to_db() :
    global instantaneous_connector
    global integrated_connector
    global temperature_connector
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

    temperature_connector = mysql.connector.connect (
                user     = 'bottle',
                password = 'bottle',
                host     = '172.19.0.3',
                database = 'temperature'
    )


connect_to_db()

logger = logging.getLogger('Logging')
logname = "/var/log/tools/bottle_server.log"
fmt = "%(asctime)s %(levelname)s %(name)s :%(message)s"
logging.basicConfig(level=10, format=fmt)



@route('/instantaneous_list')
def instantaneous_list():
    request_number = request.query.num or 100
    cursor = instantaneous_connector.cursor()

    if request.query.date :
        cursor.execute("select `id`, `power`, `created_at` from instantaneous_value WHERE created_at<='" + urllib.parse.unquote(request.query.date)+"' order by created_at DESC limit " + str(request_number))
    else:
        cursor.execute("select `id`, `power`, `created_at` from instantaneous_value order by created_at DESC limit " + str(request_number))

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
    request_number = request.query.num or 100

    cursor = integrated_connector.cursor()

    if request.query.date :
        cursor.execute("select `integrated_power`, `power_delta`,`power_charge`, `created_at` from integrated_value WHERE created_at<='" + urllib.parse.unquote(request.query.date)+"' order by created_at DESC limit " + str(request_number))
    else:
        cursor.execute("select `integrated_power`, `power_delta`,`power_charge`, `created_at` from integrated_value order by created_at DESC limit " + str(request_number))

    disp  = "<table>"
    # ヘッダー
    disp += "<tr><th>積算電力(kWh)</th><th>差分(kwH)</th><th>料金(yen)</th><th>計測日</th></tr>"
    
    # 一覧部分
    for row in cursor.fetchall():
        disp += "<tr><td>" + str(row[0]) + "</td><td>" + str(row[1]) + "</td><td>" + str(row[2]) + "</td><td>" + str(row[3]) +"</td></tr>"
    
    disp += "</table>"
    
    cursor.close

    return "DBから取得 "+disp



@route('/temperature_list')
def temperature_list():
    request_number = request.query.num or 100
    cursor = temperature_connector.cursor()

    if request.query.date :
        cursor.execute("select `id`, `temperature`, `created_at` from temperature_value WHERE created_at<='" + urllib.parse.unquote(request.query.date)+"' order by created_at DESC limit " + str(request_number))
    else:
        cursor.execute("select `id`, `temperature`, `created_at` from temperature_value order by created_at DESC limit " + str(request_number))

    disp  = "<table>"
    # ヘッダー
    disp += "<tr><th>ID</th><th>温度(℃)</th><th>登録日</th></tr>"
    
    # 一覧部分
    for row in cursor.fetchall():
        disp += "<tr><td>" + str(row[0]) + "</td><td>" + str(row[1]) + "</td><td>" + str(row[2]) + "</td></tr>"
    
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


@route('/input_temperature')
def input_temperature():
    logger.info(request.query)

    date_str = urllib.parse.unquote(request.query.date)

    # 瞬時値を入力
    cursor = temperature_connector.cursor()
    cursor.execute("INSERT INTO `temperature_value` (`server_id`, `temperature`, `created_at`, `created_user`, `updated_at`, `updated_user`) VALUES (" + request.query.server_id + ", " + request.query.temperature + ", '" + date_str + "', " + request.query.user_id + ", '" + date_str + "', " + request.query.user_id + ")")

    # コミット
    temperature_connector.commit()

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
    
    _30min_power = float(0.0)
    
    record = cursor.fetchone()
    logger.info(record)

    if record != None :
        logger.info("found:"+str(record[0]))
        logger.info("now:"+str(request.query.integrated_power))
   	    # ToDo: オーバーフロー処理
        _30min_power = float(request.query.integrated_power) - float(record[0])
        logger.info("delta:"+str(_30min_power))

    unit_price = get_price_unit(d)
    logger.info(unit_price)
    charge = _30min_power * unit_price

    cursor = integrated_connector.cursor()  
    cursor.execute("INSERT INTO `integrated_value` (`server_id`, `integrated_power`, `power_delta`, `power_charge`, `created_at`, `created_user`, `updated_at`, `updated_user`) VALUES (" + request.query.server_id + ", " + request.query.integrated_power + ", " + str(_30min_power) + ", " + str(charge)+ ",'" + date_str + "'," + request.query.user_id + ", NOW(), " + request.query.user_id + ") on duplicate key update created_at='" + date_str + "', updated_at=NOW()")

    # コミット
    integrated_connector.commit()   

    cursor.close

    return "OK"
    

# コネクターをクローズ
integrated_connector.close
instantaneous_connector.close
temperature_connector.close

# サーバ起動
run(host='0.0.0.0', port=8080, debug=True, reloader=True)