#!/usr/bin/env python
# -*- coding: utf-8 -*-

# オリジナルは、@puma_46 さんが https://qiita.com/puma_46/items/1d1589583a0c6bef796c で公開しているコード
# さらに下記を参照して変更しています.
# https://github.com/Shuichiro-T/gijutsushoten5_hyakuyoubako/blob/master/hyakuyoubako_data_sender.py
# https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/iot/api-client/http_example/cloudiot_http_example.py

from __future__ import print_function
from echonet import *
from secret import *
from gcp_environment import *

import sys
import serial
import logging
import logging.handlers
import locale
import urllib.request
import urllib.parse
import jpholiday

# [START iot_http_includes]
import base64
import datetime
import json
import time

from google.api_core import retry
import jwt
import requests
# [END iot_http_includes]


# global variables.
_BASE_URL = 'https://cloudiotdevice.googleapis.com/v1'
_BACKOFF_DURATION = 60

coeff = 1
unit = 0.1

jwt_token = ""
jwt_iat = datetime.datetime.utcnow()
jwt_exp_mins = 20


# [START iot_http_jwt]
def create_jwt():
    token = {
            # The time the token was issued.
            'iat': datetime.datetime.utcnow(),
            # Token expiration time.
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60),
            # The audience field should always be set to the GCP project id.
            'aud': project_id
    }

    # Read the private key file.
    with open(private_key_file, 'r') as f:
        private_key = f.read()

    logger.info('Creating JWT using {} from private key file {}'.format(
            algorithm, private_key_file))

    return jwt.encode(token, private_key, algorithm=algorithm).decode('ascii')
# [END iot_http_jwt]

@retry.Retry(
    predicate=retry.if_exception_type(AssertionError),
    deadline=_BACKOFF_DURATION)
# [START iot_http_publish]
def publish_message(
        message, data_type, jwt_token):
    headers = {
            'authorization': 'Bearer {}'.format(jwt_token),
            'content-type': 'application/json',
            'cache-control': 'no-cache'
    }

    # Publish to the events or state topic based on the flag.
    url_suffix = 'publishEvent' if message_type == 'event' else 'setState'

    publish_url = (
        '{}/projects/{}/locations/{}/registries/{}/devices/{}:{}').format(
            _BASE_URL, project_id, cloud_region, registry_id, device_id,
            url_suffix)

    body = None
    msg_bytes = base64.urlsafe_b64encode(message.encode('utf-8'))

    if message_type == 'event':
        body = {'binary_data': msg_bytes.decode('ascii'), 'sub_folder': data_type}
    else:
        body = {
          'state': {'binary_data': msg_bytes.decode('ascii')}
        }

    logger.info(body)

    resp = requests.post(
            publish_url, data=json.dumps(body), headers=headers)

    if (resp.status_code != 200):
        logger.warning('Response came back {}, retrying'.format(resp.status_code))
        raise AssertionError('Not OK response: {}'.format(resp.status_code))

    return resp
# [END iot_http_publish]

@retry.Retry(
    predicate=retry.if_exception_type(AssertionError),
    deadline=_BACKOFF_DURATION)
# [START iot_http_getconfig]
def get_config(
        version, jwt_token):
    headers = {
            'authorization': 'Bearer {}'.format(jwt_token),
            'content-type': 'application/json',
            'cache-control': 'no-cache'
    }

    basepath = '{}/projects/{}/locations/{}/registries/{}/devices/{}/'
    template = basepath + 'config?local_version={}'
    config_url = template.format(
        _BASE_URL, project_id, cloud_region, registry_id, device_id, version)

    resp = requests.get(config_url, headers=headers)

    if (resp.status_code != 200):
        logger.warning('Error getting config: {}, retrying'.format(resp.status_code))
        raise AssertionError('Not OK response: {}'.format(resp.status_code))

    return resp
# [END iot_http_getconfig]

def send_message(data_type, message_data, jwt_token, jwt_iat):
    seconds_since_issue = (datetime.datetime.utcnow() - jwt_iat).seconds

    if seconds_since_issue > 60 * jwt_exp_mins:
        jwt_token = create_jwt()
        jwt_iat = datetime.datetime.utcnow()
    
    try: 
        resp = publish_message(message_data, data_type, jwt_token)
    except:
        logger.error('Message send error')

    return resp


def isHoliday(check_date):
    if(check_date.weekday() >= 5) :
        return True
    if( jpholiday.is_holiday(check_date.date()) == True) :
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
    logger.info(check_date.weekday())
    logger.info(jpholiday.is_holiday(check_date.date()))

    if( (22 <= check_time.hour) or (check_time.hour <= 8) ) :
        return 17.65, "night time"

    if( isHoliday(check_time) == False ) :
        if((9<= check_time.hour) and (check_time.hour <= 18)) :
            return 32.45, "day time"

    return 25.62, "life time"


def parthE7(EDT) :
    # 内容が瞬時電力計測値(E7)だったら
    hexPower = EDT[-8:]    # 最後の4バイト（16進数で8文字）が瞬時電力計測値
    intPower = int(hexPower, 16)

    JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
    time_stamp = datetime.datetime.now(JST)
    datetime_str = time_stamp.strftime("%Y/%m/%d %H:%M:%S")

    body = "瞬時電力:"+str(intPower)+"[W]"
    body = body + "(" + datetime_str + ")"

    data_body = {}
    data_body["power"] = intPower
    data_body["created_at"] = datetime_str
    data_body["updated_at"] = datetime_str
    data_body["timestamp"] = str(time_stamp.timestamp())

    json_body = json.dumps(data_body)
   
    logger.info(body)
    logger.info(json_body)

    data = send_message("instantaneous_topic", json_body, jwt_token, jwt_iat)
    
    print ( "サーバレスポンス : ", data )	
    


def parthEA(EDT) :
    hexYear    = EDT[-22:-22+4]
    hexMonth   = EDT[-18:-18+2]
    hexDay     = EDT[-16:-16+2]
    hexHour    = EDT[-14:-14+2]
    hexMinutes = EDT[-12:-12+2]
    hexSeconds = EDT[-10:-10+2]
    hexPower   = EDT[-8:]

    time_stamp = datetime.datetime(int(hexYear,16),
                          int(hexMonth,16),
                          int(hexDay,16),
                          int(hexHour,16),
                          int(hexMinutes,16),
                          int(hexSeconds,16))    

    intPower = int(hexPower,16) * coeff * unit
    timestamp_str = time_stamp.strftime("%Y/%m/%d %H:%M:%S")

    body = "積算電力:"+str(intPower)+"[kWh]"
    body = body + "(" + timestamp_str + ")"

    last_json_data = {"created_at":"1999/01/01 01:01:01"}

    try:
        f = open(app_path+'last_integral.json', 'r')
        last_json_data = json.load(f)
        f.close()
    except:
        logger.info("first data")

    if(timestamp_str == last_json_data["created_at"]) :
        logger.info("duplicated")
        return

    _30min_power = float(0.0)
    _30min_before = time_stamp + datetime.timedelta(minutes=-30)
    _30min_before_str = _30min_before.strftime("%Y/%m/%d %H:%M:%S")
    
    if(last_json_data["created_at"] == _30min_before_str) :
        _30min_power = float(intPower) - float(last_json_data["integrated_power"])
        logger.info("delta:"+str(_30min_power))

    unit_price = get_price_unit(time_stamp)
    logger.info(unit_price)
    charge = _30min_power * unit_price[0]

    data_body = {}
    data_body["integrated_power"] = intPower
    data_body["power_delta"] = _30min_power
    data_body["power_type"] = unit_price[1] 
    data_body["power_charge"] = charge   
    data_body["created_at"] = timestamp_str
    data_body["updated_at"] = timestamp_str
    data_body["timestamp"] = time_stamp.timestamp()

    json_body = json.dumps(data_body)
    json_obj = json.loads(json_body)

    logger.info(body)
    logger.info(json_body)

    data = send_message("integrated_topic", json_body, jwt_token, jwt_iat)

    if( data.status_code == 200) :
        fw = open(app_path+'last_integral.json','w')
        json.dump(json_obj,fw)
        fw.close()

    print ( "サーバレスポンス : ", data )	


def parthD3(EDT) :
	# 係数
	hexCoeff = EDT[-8:]    # 最後の4バイト（16進数で8文字）が係数
	global coeff    
	coeff = int(hexCoeff , 16)
	message = "係数:" + str(coeff)
	logger.info(message)

def parthE1(EDT) :
	# 単位
	hexUnit = EDT[-2:]    # 最後の1バイト（16進数で2文字）が単位
	global unit
	if hexUnit == "00" :
		unit = 1
	if hexUnit == "01" :
		unit = 0.1
	if hexUnit == "02" :
		unit = 0.01
	if hexUnit == "03" :
		unit = 0.001
	if hexUnit == "04" :
		unit = 0.0001
	if hexUnit == "0A" :
		unit = 10
	if hexUnit == "0B" :
		unit = 100
	if hexUnit == "0C" :
		unit = 1000
	if hexUnit == "0D" :
		unit = 10000

	message = "単位:" + hexUnit + ":" + str(unit)
	logger.info(message)


def sendCommand(command_str) :
    command_base = "SKSENDTO 1 {0} 0E1A 1 {1:04X} ".format(ipv6Addr, len(command_str))
    command = command_base.encode() + command_str 
    logger.info(b"SEND: " + command)
    # コマンド送信
    ser.write(command)

    #print(ser.readline(), end="") # エコーバック
    #print(ser.readline(), end="") # EVENT 21 が来るはず（チェック無し）
    #print(ser.readline(), end="") # OKが来るはず（チェック無し）
    logger.info(str(ser.readline()))
    logger.info(str(ser.readline()))
    
    chk_ok = "none"
    while not chk_ok.startswith("OK") :
        chk_ok = str(ser.readline().decode('utf-8'))
        logger.info(chk_ok)

    line = str(ser.readline().decode('utf-8'))         # ERXUDPが来るはず
    logger.info(line)

    # 受信データはたまに違うデータが来たり、
    # 取りこぼしたりして変なデータを拾うことがあるので
    # チェックを厳しめにしてます。
    if line.startswith("ERXUDP") :
        cols = line.strip().split(' ')
        res = cols[8]   # UDP受信データ部分
        #tid = res[4:4+4];
        seoj = res[8:8+6]
        #deoj = res[14,14+6]
        ESV = res[20:20+2]
        OPC_HEX = res[22:22+2]
        OPC = int(OPC_HEX,16)
        OPC_COUNT = 0
        CUR_POSITION = 24
        
        if seoj == "028801" and ESV == "72" :
            while OPC_COUNT < OPC :
				# スマートメーター(028801)から来た応答(72)なら
                EPC = res[CUR_POSITION:CUR_POSITION+2]
                CUR_POSITION+=2
                EPD_hex = res[CUR_POSITION:CUR_POSITION+2]
                EPD = int(EPD_hex, 16)
                CUR_POSITION+=2
                EDT = ""
                if EPD > 0 :
                    EDT = res[CUR_POSITION:CUR_POSITION+2*EPD]
                    CUR_POSITION+=2*EPD
                if EPC == "E7" :
                    # 内容が瞬時電力計測値(E7)だったら
                    parthE7(EDT)
                if EPC == "EA" :
                    # 内容がEAだったら
                    parthEA(EDT)
                if EPC == "D3" :
                    # 内容がEAだったら
                    parthD3(EDT)
                if EPC == "E1" :
                    # 内容がEAだったら
                    parthE1(EDT)
                OPC_COUNT+=1


#ロガー取得
logger = logging.getLogger('Logging')

logname = "/var/log/tools/b-route.log"
fmt = "%(asctime)s %(levelname)s %(name)s :%(message)s"
logging.basicConfig(level=10, format=fmt)

# シリアルポートデバイス名
serialPortDev = '/dev/ttyUSB0'  # Linux(ラズパイなど）の場合

# シリアルポート初期化
ser = serial.Serial(serialPortDev, 115200)

# Bルート認証パスワード設定
ser.write(("SKSETPWD C " + rbpwd + "\r\n").encode())
ser.readline()
ser.readline()

# Bルート認証ID設定
ser.write(("SKSETRBID " + rbid + "\r\n").encode())
ser.readline()
ser.readline()

scanDuration = 4   # スキャン時間。サンプルでは6なんだけど、4でも行けるので。（ダメなら増やして再試行）
scanRes = {} # スキャン結果の入れ物

# スキャンのリトライループ（何か見つかるまで）
while "Channel" not in scanRes :
    # アクティブスキャン（IE あり）を行う
    # 時間かかります。10秒ぐらい？
    ser.write(("SKSCAN 2 FFFFFFFF " + str(scanDuration) + "\r\n").encode())

    # スキャン1回について、スキャン終了までのループ
    scanEnd = False
    while not scanEnd :
        line = str(ser.readline().decode('utf-8'))
        logger.info(line)

        if line.startswith("EVENT 22") :
            # スキャン終わったよ（見つかったかどうかは関係なく）
            scanEnd = True
        elif line.startswith("  ") :
            # スキャンして見つかったらスペース2個あけてデータがやってくる
            # 例
            #  Channel:39
            #  Channel Page:09
            #  Pan ID:FFFF
            #  Addr:FFFFFFFFFFFFFFFF
            #  LQI:A7
            #  PairID:FFFFFFFF
            cols = line.strip().split(':')
            scanRes[cols[0]] = cols[1]
    scanDuration+=1

    if 14 < scanDuration and "Channel" not in scanRes:
        # 引数としては14まで指定できるが、7で失敗したらそれ以上は無駄っぽい
        logger.error("スキャンリトライオーバー")
        ser.close()
        sys.exit()  #### 糸冬了 ####

# スキャン結果からChannelを設定。
ser.write(("SKSREG S2 " + scanRes["Channel"] + "\r\n").encode())
logger.info(str(ser.readline().decode('utf-8')))
logger.info(str(ser.readline().decode('utf-8')))
#print(ser.readline(), end="") # エコーバック
#print(ser.readline(), end="") # OKが来るはず（チェック無し）

# スキャン結果からPan IDを設定
ser.write(("SKSREG S3 " + scanRes["Pan ID"] + "\r\n").encode())
#print(ser.readline(), end="") # エコーバック
#print(ser.readline(), end="") # OKが来るはず（チェック無し）
logger.info(str(ser.readline().decode('utf-8')))
logger.info(str(ser.readline().decode('utf-8')))

# MACアドレス(64bit)をIPV6リンクローカルアドレスに変換。
# (BP35A1の機能を使って変換しているけど、単に文字列変換すればいいのではという話も？？)
ser.write(("SKLL64 " + scanRes["Addr"] + "\r\n").encode())
#print(ser.readline(), end="") # エコーバック
logger.info(str(ser.readline().decode('utf-8')))
ipv6Addr = str(ser.readline().decode('utf-8')).strip()
#print(ipv6Addr)

# PANA 接続シーケンスを開始します。
ser.write(("SKJOIN " + ipv6Addr + "\r\n").encode())
#print(ser.readline(), end="") # エコーバック
#print(ser.readline(), end="") # OKが来るはず（チェック無し）
logger.info(str(ser.readline().decode('utf-8')))
logger.info(str(ser.readline().decode('utf-8')))

# PANA 接続完了待ち（10行ぐらいなんか返してくる）
bConnected = False
while not bConnected :
    line = str(ser.readline().decode('utf-8'))
    #print(line, end="")
    if line.startswith("EVENT 24") :
        logger.error("PANA 接続失敗")
        ser.close()
        sys.exit()  #### 糸冬了 ####
    elif line.startswith("EVENT 25") :
        # 接続完了！
        bConnected = True

# これ以降、シリアル通信のタイムアウトを設定
ser.timeout = 8

# スマートメーターがインスタンスリスト通知を投げてくる
# (ECHONET-Lite_Ver.1.12_02.pdf p.4-16)
logger.info(str(ser.readline().decode('utf-8')))

GetEnd = True
counter = 30

jwt_token = create_jwt()
jwt_iat = datetime.datetime.utcnow()
jwt_exp_mins = 20
logger.info('Latest configuration: {}'.format(get_config('0', jwt_token).text))

while True :
    sendCommand(GET_NOW_POWER)
    time.sleep(10)
    if counter > 10 :
        counter = 0 
        sendCommand(GET_LATEST30)     
    counter = counter + 1
    time.sleep(20)

# 無限ループだからここには来ないけどな
ser.close()