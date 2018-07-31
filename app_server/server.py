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


def isHoliday(check_date):
    if(check_date.weekday >= 5) :
        return True
    if( jpholiday.isHoliday(check_date) ) :
        return True
    if( (check_date.month == 1) and (check_date.day == 2) ):
        return True
    if( (check_date.month == 1) and (check_date.day == 3) ):
        return True       
    if( (check_date.month == 4) and (check_date.day == 30) ):
        return True
    if( (check_date.month == 5) and (check_date.day == 1) ):
        return True
    if( (check_date.month == 5) and (check_date.day == 2) ):
        return True
    if( (check_date.month == 12) and (check_date.day == 30) ):
        return True
    if( (check_date.month == 12) and (check_date.day == 31) ):
        return True
    return False


def get_price_unit(check_date):
    logger.info(check_date)
    check_time = check_date - datetime.timedelta(minutes=10)
    logger.info(check_time)

    if( (22 <= check_time.hour) or (check_time.hour <= 8) ) :
        return 17.65

    if( isHoliday(check_date) == False ) :
        if((9<= check_time.hour) or (check_time.hour <= 18)) :
            return 32.45

    return 25.62


class DB:
    conn = None
    user = None
    password = None
    host = None
    database = None

    def __init__(self,user,password,host,database):
        self.user = user
        self.password = password
        self.host = host
        self.database = database

    @retry()
    def connect(self):
        self.conn = mysql.connector.connect (
                user     = self.user,
                password = self.password,
                host     = self.host,
                database = self.database
        )

    def query(self, sql):
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
        except (AttributeError, mysql.OperationalError):
            self.connect()
            cursor = self.conn.cursor()
            cursor.execute(sql)
        return cursor

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def connect_to_db() :
    global instantaneous_db
    global integrated_db
    global temperature_db

    instantaneous_db = DB('bottle', 'bottle', '172.19.0.3','instantaneous_measurement')
    integrated_db = DB('bottle', 'bottle', '172.19.0.3','integrated_measurement')
    temperature_db = DB('bottle', 'bottle', '172.19.0.3','temperature')

    instantaneous_db.connect()
    integrated_db.connect()
    temperature_db.connect()



connect_to_db()

logger = logging.getLogger('Logging')
logname = "/var/log/tools/bottle_server.log"
fmt = "%(asctime)s %(levelname)s %(name)s :%(message)s"
logging.basicConfig(level=10, format=fmt)



@route('/instantaneous_list')
def instantaneous_list():
    request_number = request.query.num or 100
    cursor = mysql.connector.cursor()

    if request.query.date :
        cursor = instantaneous_db.query("select `id`, `power`, `created_at` from instantaneous_value WHERE created_at<='" + urllib.parse.unquote(request.query.date)+"' order by created_at DESC limit " + str(request_number))
    else:
        cursor = instantaneous_db.query("select `id`, `power`, `created_at` from instantaneous_value order by created_at DESC limit " + str(request_number))

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

    cursor = mysql.connector.cursor()

    if request.query.date :
        cursor = integrated_db.query("select `integrated_power`, `power_delta`,`power_charge`, `created_at` from integrated_value WHERE created_at<='" + urllib.parse.unquote(request.query.date)+"' order by created_at DESC limit " + str(request_number))
    else:
        cursor = integrated_db.query("select `integrated_power`, `power_delta`,`power_charge`, `created_at` from integrated_value order by created_at DESC limit " + str(request_number))

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
    cursor = mysql.connector.cursor()

    if request.query.date :
        cursor = temperature_db.query("select `id`, `temperature`, `created_at` from temperature_value WHERE created_at<='" + urllib.parse.unquote(request.query.date)+"' order by created_at DESC limit " + str(request_number))
    else:
        cursor = temperature_db.query("select `id`, `temperature`, `created_at` from temperature_value order by created_at DESC limit " + str(request_number))

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
    cursor = instantaneous_db.query("INSERT INTO `instantaneous_value` (`server_id`, `power`, `created_at`, `created_user`, `updated_at`, `updated_user`) VALUES (" + request.query.server_id + ", " + request.query.power + ", '" + date_str + "', " + request.query.user_id + ", '" + date_str + "', " + request.query.user_id + ")")

    # コミット
    instantaneous_db.commit()

    cursor.close

    return "OK"


@route('/input_temperature')
def input_temperature():
    logger.info(request.query)

    date_str = urllib.parse.unquote(request.query.date)

    # 瞬時値を入力
    cursor = temperature_db.query("INSERT INTO `temperature_value` (`server_id`, `temperature`, `created_at`, `created_user`, `updated_at`, `updated_user`) VALUES (" + request.query.server_id + ", " + request.query.temperature + ", '" + date_str + "', " + request.query.user_id + ", '" + date_str + "', " + request.query.user_id + ")")

    # コミット
    temperature_db.commit()

    cursor.close

    return "OK"
    


@route('/input_integrated')
def input_integrated_power():
    logger.info(request.query)

    # 積算値を入力   
    date_str = urllib.parse.unquote(request.query.date)
    d = datetime.datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
    logger.info(date_str)
    logger.info(d)
    
    # 30分前
    _30min_before = d + datetime.timedelta(minutes=-30)
    _30min_before_str = _30min_before.strftime("%Y/%m/%d %H:%M:%S")
    logger.info(_30min_before_str)

    # 30分前の積算値を取得
    cursor = integrated_db.query("SELECT `integrated_power`, `created_at` from integrated_value WHERE created_at='" + _30min_before_str+"'")
    
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

    cursor = integrated_db.query("INSERT INTO `integrated_value` (`server_id`, `integrated_power`, `power_delta`, `power_charge`, `created_at`, `created_user`, `updated_at`, `updated_user`) VALUES (" + request.query.server_id + ", " + request.query.integrated_power + ", " + str(_30min_power) + ", " + str(charge)+ ",'" + date_str + "'," + request.query.user_id + ", NOW(), " + request.query.user_id + ") on duplicate key update created_at='" + date_str + "', updated_at=NOW()")

    # コミット
    integrated_db.commit()   

    cursor.close

    return "OK"
    

# コネクターをクローズ
instantaneous_db.close()
integrated_db.close()
temperature_db.close()
# サーバ起動
run(host='0.0.0.0', port=8080, debug=True, reloader=True)