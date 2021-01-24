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
import threading
import os
import csv

import tinytuya

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
_BACKOFF_DURATION = 10
_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
_DATETIME_FORMAT_TZ =  '%Y-%m-%dT%H:%M:%S+%z'
_DATE_FORMAT = '%Y-%m-%d' 

coeff = 1
unit = 0.1
failure_count = 0
_MAX_FAILURE_COUNT = 5

jwt_token = ""
jwt_iat = datetime.datetime.utcnow()
jwt_exp_mins = 15

lock = threading.Lock()

resending_status = False 

class ResendThread(threading.Thread):

    def __init__(self):
        super(ResendThread, self).__init__()
        
    def run(self):
        logger.info('resend thread')

        global resending_status
        if resending_status:
            logger.info('already running')
            return

        resending_status = True

        global lock
        lock.acquire()       

        if os.path.isfile(app_path+'failed_message.txt') : 

            os.rename(app_path+'failed_message.txt', app_path+'failed_message_back.txt')
            lock.release()

            with open(app_path+'failed_message_back.txt', 'r') as file:
                reader = csv.reader(file, delimiter='#')

                self.jwt_token = create_jwt()
                self.jwt_iat = datetime.datetime.utcnow()
                self.jwt_exp_mins = jwt_exp_mins

                for message in reader:
                    seconds_since_issue = (datetime.datetime.utcnow() - self.jwt_iat).seconds

                    if seconds_since_issue > 60 * self.jwt_exp_mins:
                        logger.info('Refreshing token after {}s').format(seconds_since_issue)
                        self.jwt_token = create_jwt(
                                self.args.project_id, self.args.private_key_file, self.args.algorithm)
                        self.jwt_iat = datetime.datetime.utcnow()

                    try: 
                        logger.info('RePublishing message : \'{}\''.format(message))
                        resp = publish_message(message[0], message[1], self.jwt_token)

                        #On HTTP error , write message to file.
                        if resp.status_code != requests.codes.ok:
                            lock.acquire()       
                            with open(app_path+'failed_message.txt', 'a') as f:
                                writer = csv.writer(f, delimiter='#')
                                writer.writerow([message[0], message[1]])
                            lock.release()
                    except:
                        logger.error('Resend timeout')
                        lock.acquire()       
                        with open(app_path+'failed_message.txt', 'a') as f:
                            writer = csv.writer(f, delimiter='#')
                            writer.writerow([message[0], message[1]])
                        lock.release()                        

                    logger.info( 'サーバレスポンス :{}'.format(resp) )	
                    time.sleep(1) 

            os.remove(app_path+'failed_message_back.txt')
        else :
            lock.release()
            logger.info('no failed file')

        logger.info('fin resend thread')
        resending_status = False


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

    return jwt.encode(token, private_key, algorithm=algorithm)
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
            publish_url, data=json.dumps(body), headers=headers, timeout=3.5)

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

    resp = requests.get(config_url, headers=headers, timeout=3.5)

    if (resp.status_code != 200):
        logger.warning('Error getting config: {}, retrying'.format(resp.status_code))
        raise AssertionError('Not OK response: {}'.format(resp.status_code))

    return resp
# [END iot_http_getconfig]

def send_message(data_type, message_data, jwt_token, jwt_iat):
    seconds_since_issue = (datetime.datetime.utcnow() - jwt_iat).seconds
    resp = requests.Response()

    if seconds_since_issue > 60 * jwt_exp_mins:
        jwt_token = create_jwt()
        jwt_iat = datetime.datetime.utcnow()
    
    try: 
        resp = publish_message(message_data, data_type, jwt_token)

        resend_thread = ResendThread()
        resend_thread.start()
    except:
        logger.error('Message send error')
        jwt_token = create_jwt()
        jwt_iat = datetime.datetime.utcnow()
        global lock
        lock.acquire()       
        with open(app_path+'failed_message.txt', 'a') as f:
            writer = csv.writer(f, delimiter='#')
            writer.writerow([message_data, data_type])
        lock.release()

    return resp, jwt_token, jwt_iat


def get_plug_power() :
    plug_status_body = {}

    for item in plug_mapping :
        logger.info('getting plug data from {}'.format(item['label']))

        d = tinytuya.OutletDevice(item['dev_id'], item['address'], item['local_key'])
        d.set_version(3.3)
        data = d.status() 

        # Show status of first controlled switch on device
        logger.info('Dictionary {}'.format(data))
        logger.info('State (bool, true is ON) {}'.format(data['dps']['1']))  
        logger.info('Power {}'.format(float(data['dps']['19'])/10.0))

        plug_status_body[item['label']] = (float(data['dps']['19'])/10.0)

    return plug_status_body


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
    JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
    logger.info(check_date)
    check_time = check_date - datetime.timedelta(minutes=15)
    logger.info(check_time)
    logger.info(check_date.weekday())
    logger.info(jpholiday.is_holiday(check_date.date()))

    if( (datetime.time(hour=22,minute=00,second=00, tzinfo=JST) <= check_time.timetz()) or (check_time.timetz() < datetime.time(hour=8,minute=00,second=00, tzinfo=JST)) ) :
        return 20.98, "night time", check_time

    if( isHoliday(check_time) == False ) :
        if((datetime.time(hour=9,minute=00,second=00, tzinfo=JST) <= check_time.timetz()) and (check_time.timetz() < datetime.time(hour=18,minute=00,second=00, tzinfo=JST))) :
            return 21.05, "day time", check_time

    return 26.09, "life time", check_time

def get_tempoerature():
    url = "https://api.nature.global/1/devices"
    headers = {"Content-Type": "application/json", "X-Requested-With":"python", "accept": "application/json", "Expect":"",
    "Authorization": 'Bearer {}'.format(remo_token)}

    temp_data_body = {}

    try :
        resp = requests.get(url, headers=headers, timeout=3.5)
        logger.info(resp)
        if(resp.status_code == 200) :
            data_list = resp.json()
            logger.info(json.dumps(data_list, indent=4))
            for item in data_list :
                mac_address = item["mac_address"]
                label = ""
                try :
                    label = temp_mapping[mac_address]
                    temp_data_body['TEMPERATURE_{}'.format(label)] = item["newest_events"]["te"]["val"]
                except:
                    logger.warning('{} is not in temp mapping.'.format(mac_address))
    except :
        logger.warning("temperature timeout")

    logger.info(temp_data_body)
    return temp_data_body

def get_mining_status() :

    mining_status_body = {}

    total_hash_rate = 0
    total_revenue_par_day = 0
    total_profilt_par_day = 0
    total_power_usage = 0

    try :
        resp = requests.get(miner_stat, timeout=3.5)
        logger.info(resp)

        if(resp.status_code == 200) :
            data_list = resp.json()
            logger.info(json.dumps(data_list, indent=4))
            
            for group in data_list["groupList"] :
                for miner in group["minerList"] :
                    name = miner["name"].upper() 

                    mining_status_body[name+"_"+"POOL"] = miner["pool"]
                    mining_status_body[name+"_"+"SOFTWARE"] = miner["softwareType"]

                    if( miner["speedInfo"].get("hashrateValue") is not None) :
                        mining_status_body[name+"_"+"HASHRATE"] = miner["speedInfo"]["hashrateValue"]
                        total_hash_rate = total_hash_rate + miner["speedInfo"]["hashrateValue"]

                    if( miner["coinInfo"].get("revenuePerDayValueDisplayCurrency") is not None) :
                        mining_status_body[name+"_"+"REVENUE_PAR_DAY"] = miner["coinInfo"]["revenuePerDayValueDisplayCurrency"]
                        total_revenue_par_day = total_revenue_par_day + miner["coinInfo"]["revenuePerDayValueDisplayCurrency"]
                    elif( miner["coinInfo"].get("revenuePerDayValue") is not None) :
                        mining_status_body[name+"_"+"REVENUE_PAR_DAY"] = miner["coinInfo"]["revenuePerDayValue"]
                        total_revenue_par_day = total_revenue_par_day + miner["coinInfo"]["revenuePerDayValue"]

                    mining_status_body[name+"_"+"PROFIT_PAR_DAY"] = miner["coinInfo"]["profitPerDayValue"]
                    total_profilt_par_day = total_profilt_par_day + miner["coinInfo"]["profitPerDayValue"]

                    if( miner["coinInfo"].get("isActualPowerUsage") is not None) :
                        mining_status_body[name+"_"+"POWER_USAGE"] = miner["coinInfo"]["powerUsageValue"]
                        total_power_usage = total_power_usage + miner["coinInfo"]["powerUsageValue"]

                    if(miner["coinInfo"].get("algorithm") is not None) :
                        mining_status_body[name+"_"+"ALGORITHM"] = miner["coinInfo"]["algorithm"]

                    mining_status_body[name+"_"+"GPU_TEMPERATURE"] = miner["maxTemperatureValue"]
            
            mining_status_body["TOTAL_HASHRATE"] = total_hash_rate
            mining_status_body["TOTAL_REVENUE_PAR_DAY"] = total_revenue_par_day
            mining_status_body["TOTAL_PROFIT_PAR_DAY"] = total_profilt_par_day
            mining_status_body["TOTAL_POWER_USAGE"] = total_power_usage
                   
    except :
        logger.warning("mining status timeout")

    logger.info(mining_status_body)
    return mining_status_body


def setCurrentElectricityPrice(timestamp) :
    current_electricity_price = get_price_unit(timestamp)
    logger.info("Current electricity price: {}".format(current_electricity_price[0]))
    query_string = "&value="+str(current_electricity_price[0])
    resp = requests.post(miner_set_electricity_price+query_string, timeout=3.5)
    logger.info(resp)  


def parthE7(EDT) :
    # 内容が瞬時電力計測値(E7)だったら
    hexPower = EDT[-8:]    # 最後の4バイト（16進数で8文字）が瞬時電力計測値
    intPower = int(hexPower, 16)

    JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
    time_stamp = datetime.datetime.now(JST)
    datetime_str = time_stamp.strftime(_DATETIME_FORMAT)
    date_str = time_stamp.strftime(_DATE_FORMAT)

    body = "瞬時電力:"+str(intPower)+"[W]"
    body = body + "(" + datetime_str + ")"

    data_body = {}
    data_body["TYPE"] = "INSTANTANEOUS"
    data_body["POWER"] = intPower
    data_body["TIMESTAMP"] = str(time_stamp.timestamp())
    data_body["DATETIME"] = datetime_str
    data_body["DATE"] = date_str


    temp_body = get_tempoerature()
    data_body.update(temp_body)

    temp_body = get_mining_status()
    data_body.update(temp_body)

    temp_body = get_plug_power()
    data_body.update(temp_body)

    json_body = json.dumps(data_body)
   
    logger.info(body)
    logger.info(json_body)

    global jwt_iat
    global jwt_token
    data = send_message("instantaneous_topic", json_body, jwt_token, jwt_iat)
    jwt_token = data[1]
    jwt_iat = data[2]
    
    logger.info( 'サーバレスポンス :{}'.format(data) )	
    


def parthEA(EDT) :
    hexYear    = EDT[-22:-22+4]
    hexMonth   = EDT[-18:-18+2]
    hexDay     = EDT[-16:-16+2]
    hexHour    = EDT[-14:-14+2]
    hexMinutes = EDT[-12:-12+2]
    hexSeconds = EDT[-10:-10+2]
    hexPower   = EDT[-8:]

    JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
    time_stamp = datetime.datetime(int(hexYear,16),
                          int(hexMonth,16),
                          int(hexDay,16),
                          int(hexHour,16),
                          int(hexMinutes,16),
                          int(hexSeconds,16),
                          tzinfo=JST)    

    intPower = int(hexPower,16) * coeff * unit
    timestamp_str = time_stamp.strftime(_DATETIME_FORMAT)
    datetime_str = time_stamp.strftime(_DATETIME_FORMAT)
    date_str = time_stamp.strftime(_DATE_FORMAT)
    

    body = "積算電力:"+str(intPower)+"[kWh]"
    body = body + "(" + timestamp_str + ")"
    logger.info(body)

    last_json_data = {"TIMESTAMP":"0"}

    try:
        with open(app_path+'last_integral.json', 'r') as f:
            last_json_data = json.load(f)
        logger.info('last data:{}'.format(last_json_data))
    except Exception as e:
        logger.info('first data:{}'.format(e))

    _30min_power = float(0.0)
    _30min_before = time_stamp + datetime.timedelta(minutes=-30)

    try:
        if(str(time_stamp.timestamp()) == last_json_data["TIMESTAMP"]) :
            logger.info("duplicated")
            return

        if(last_json_data["TIMESTAMP"] == str(_30min_before.timestamp())) :
            _30min_power = float(intPower) - float(last_json_data["INTEGRATED_POWER"])
            logger.info("power delta:"+str(_30min_power))

    except Exception as e:
        logger.info('TIMESTAMP check failed. just ignore.:{}'.format(e))

    unit_price = get_price_unit(time_stamp)
    logger.info(unit_price)
    charge = _30min_power * unit_price[0]

    data_body = {}
    data_body["TYPE"] = "INTEGRATED"
    data_body["INTEGRATED_POWER"] = intPower

    data_body["POWER_DELTA"] = _30min_power
    data_body["CHARGE"] = charge  
    data_body["POWER_CHARGE_TYPE"] = unit_price[1] 

    if( unit_price[1] == "day time") :
        data_body["DAYTIME_POWER_DELTA"] = _30min_power
        data_body["DAYTIME_CHARGE"] = charge
    elif( unit_price[1] == "life time") :
        data_body["LIFETIME_POWER_DELTA"] = _30min_power
        data_body["LIFETIME_CHARGE"] = charge
    elif( unit_price[1] == "night time") :
        data_body["NIGHTTIME_POWER_DELTA"] = _30min_power
        data_body["NIGHTTIME_CHARGE"] = charge
    else :
        logger.warning("unknown charge type")
 
    data_body["TIMESTAMP"] = str(time_stamp.timestamp())
    data_body["DATETIME"] = datetime_str
    data_body["CHECK_DATETIME"] = unit_price[2].strftime(_DATETIME_FORMAT)
    data_body["DATE"] = date_str

    json_body = json.dumps(data_body)
    json_obj = json.loads(json_body)

    logger.info(json_body)

    with open(app_path+'last_integral.json','w') as fw :
        json.dump(json_obj,fw)
    logger.info("json file saved")
    
    global jwt_iat
    global jwt_token
    data = send_message("integrated_topic", json_body, jwt_token, jwt_iat)
    jwt_token = data[1]
    jwt_iat = data[2]

    logger.info( 'サーバレスポンス :{}'.format(data) )	


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
    global failure_count
    wait_ok_count = 0

    while wait_ok_count < _MAX_FAILURE_COUNT :
        chk_ok = str(ser.readline().decode('utf-8'))
        logger.info("checking ok?:{}".format(chk_ok))
        if chk_ok.startswith("OK") :
            logger.info("OK!")
            wait_ok_count = 0
            break
        else :
            logger.info("err...:{}".format(wait_ok_count))
            wait_ok_count += 1

    if wait_ok_count >= _MAX_FAILURE_COUNT :
        failure_count += 1
    else :
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
                failure_count = 0
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
            else :
                failure_count += 1
        else :
            failure_count += 1

    logger.info("failure_count :{}".format(failure_count))

    if failure_count > _MAX_FAILURE_COUNT :
        logger.info("RESTART! :{}".format(failure_count))
        sys.exit(-1)
    else :
        logger.info("end of sendCommand")
        return



if __name__ == '__main__':
    #ロガー取得
    logger = logging.getLogger('Logging')

    logname = "/var/log/tools/b-route.log"
    fmt = "%(asctime)s %(levelname)s %(name)s [%(thread)d][%(filename)s:%(lineno)d]: %(message)s"
    logging.basicConfig(level=10, format=fmt)

    logger.info("STARTING...")

    # シリアルポートデバイス名
    serialPortDev = '/dev/ttyUSB0'  # Linux(ラズパイなど）の場合

    # シリアルポート初期化
    ser = serial.Serial(serialPortDev, 115200, timeout=10)

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
        JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
        cur_timestamp = datetime.datetime.now(JST)
        cur_datetime_str = cur_timestamp.strftime(_DATETIME_FORMAT_TZ)
        logger.info('current jst: {}'.format(cur_datetime_str))
        setCurrentElectricityPrice(cur_timestamp)
        sendCommand(GET_NOW_POWER)
        time.sleep(10)
        if counter > 15 :
            counter = 0 
            sendCommand(GET_LATEST30)     
        counter = counter + 1
        time.sleep(10)

    # 無限ループだからここには来ないけどな
    ser.close()