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

import base64
import csv
import datetime
import hashlib
import hmac
import json
import logging
import logging.handlers
import locale
import os
import sys
import time
import threading
import urllib.parse
import urllib.request
import uuid
import zeroconf
from dataclasses import dataclass
from typing import Optional

import jpholiday
import jwt
import pychromecast
import redis
import requests
import serial
from google.api_core import retry


_BACKOFF_DURATION = 10
_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
_DATETIME_FORMAT_TZ = '%Y-%m-%dT%H:%M:%S%z'
_DATE_FORMAT = '%Y-%m-%d'
_MAX_FAILURE_COUNT = 5
_JWT_EXP_MINS = 15


@dataclass
class State:
    coeff: int = 1
    unit: float = 0.1
    failure_count: int = 0
    jwt_token: str = ""
    jwt_iat: Optional[datetime.datetime] = None
    last_instant_sent: Optional[datetime.datetime] = None
    last_switchbot_sent: Optional[datetime.datetime] = None
    latest_instant_val: Optional[dict] = None


state = State()

# Redisクライアントのセットアップ
redis_client = redis.StrictRedis(host='redis', port=6379, decode_responses=True)

# Chromecastデバイス接続キャッシュ（speak()呼び出しごとの再スキャンを避ける）
_cast_cache = None


def _get_chromecasts():
    global _cast_cache
    if _cast_cache is None:
        logger.info("pychromecast: discovering devices")
        casts, browser = pychromecast.get_chromecasts(known_hosts=google_home_list)
        browser.stop_discovery()
        _cast_cache = casts
        logger.info("pychromecast: found {} device(s)".format(len(casts)))
    return _cast_cache


def try_resend():
    logger.info('resend check')

    if not os.path.isfile(app_path + 'failed_message.txt'):
        logger.info('no failed file')
        logger.info('fin resend check')
        return

    os.rename(app_path + 'failed_message.txt', app_path + 'failed_message_back.txt')

    with open(app_path + 'failed_message_back.txt', 'r') as file:
        reader = csv.reader(file, delimiter='#')
        for message in reader:
            try:
                state.jwt_token = create_jwt()
                logger.info("RePublishing message: '{}'".format(message))
                resp = publish_message(json.loads(message[0]), state.jwt_token)
                if resp.status_code != requests.codes.ok:
                    with open(app_path + 'failed_message.txt', 'a') as f:
                        writer = csv.writer(f, delimiter='#')
                        writer.writerow([message[0]])
            except Exception as e:
                logger.error('Resend error: {}'.format(e))
                with open(app_path + 'failed_message.txt', 'a') as f:
                    writer = csv.writer(f, delimiter='#')
                    writer.writerow([message[0]])
            time.sleep(1)

    logger.info('fin resend check')


def create_jwt():
    seconds_since_issue = 60 * _JWT_EXP_MINS

    if state.jwt_iat is not None:
        seconds_since_issue = (datetime.datetime.now(datetime.UTC) - state.jwt_iat).seconds

    if seconds_since_issue < 60 * _JWT_EXP_MINS:
        logger.info('No need to refresh {}s'.format(seconds_since_issue))
        return state.jwt_token

    head = {
        "alg": "RS256",
        "typ": "JWT"
    }

    token = {
        'iat': datetime.datetime.now(datetime.UTC),
        'exp': datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=60),
        'iss': sa_email,
        'aud': 'https://www.googleapis.com/oauth2/v4/token',
        'sub': sa_email,
        'target_audience': audience
    }

    temp_jwt = jwt.encode(token, key, algorithm=algorithm, headers=head)

    headers = {
        'authorization': 'Bearer {}'.format(temp_jwt),
        'content-type': 'application/x-www-form-urlencoded'
    }

    message = 'grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion={}'.format(temp_jwt)

    resp = requests.post(auth_api, data=message, headers=headers, timeout=3.5)
    logger.info("auth_token:")
    logger.info(resp.json())

    if resp.status_code == requests.codes.ok:
        state.jwt_iat = datetime.datetime.now(datetime.UTC)
        logger.info('token refresh {}s'.format(state.jwt_iat))

    return resp.json()['id_token']


@retry.Retry(
    predicate=retry.if_exception_type(AssertionError),
    deadline=_BACKOFF_DURATION)
def publish_message(json_body, jwt_token):
    headers = {
        'authorization': 'Bearer {}'.format(jwt_token),
        'content-type': 'application/json',
        'cache-control': 'no-cache'
    }

    logger.info("trig. cloud function.")
    logger.info(json.dumps(json_body))
    resp = requests.post(audience, json=json_body, headers=headers, timeout=3.5)

    if resp.status_code != 200:
        logger.warning('Response came back {}, retrying'.format(resp.status_code))
        raise AssertionError('Not OK response: {}'.format(resp.status_code))

    return resp


def send_message(json_body):
    resp = requests.Response()

    try:
        state.jwt_token = create_jwt()
        resp = publish_message(json_body, state.jwt_token)
        try_resend()

    except Exception as e:
        logger.exception('Message send error: {}'.format(e))
        with open(app_path + 'failed_message.txt', 'a') as f:
            writer = csv.writer(f, delimiter='#')
            writer.writerow([json.dumps(json_body)])

    return resp


def create_switchbot_token():
    token = sb_clientid
    secret = sb_clientsecret
    nonce = uuid.uuid4()
    t = int(round(time.time() * 1000))
    string_to_sign = bytes('{}{}{}'.format(token, t, nonce), 'utf-8')
    secret_bytes = bytes(secret, 'utf-8')

    sign = base64.b64encode(
        hmac.new(secret_bytes, msg=string_to_sign, digestmod=hashlib.sha256).digest()
    )

    api_header = {
        'Authorization': token,
        'Content-Type': 'application/json',
        'charset': 'utf8',
        't': str(t),
        'sign': str(sign, 'utf-8'),
        'nonce': str(nonce),
    }

    logger.info("apiHeader: {}".format(api_header))
    return api_header


@retry.Retry(
    predicate=retry.if_exception_type(AssertionError),
    deadline=_BACKOFF_DURATION)
def get_request(url, headers):
    response = requests.get(url, headers=headers)
    logger.info(response)
    logger.info(response.json())

    if response.status_code != 200 and response.status_code != 401:
        logger.warning('Response came back {}, retrying'.format(response.status_code))
        raise AssertionError('Not OK response: {}'.format(response.status_code))

    return response


def _get_switchbot_device_body(device_id):
    """SwitchBot API からデバイスステータスの body を取得する共通ヘルパー。"""
    url = "https://api.switch-bot.com/v1.1/devices/{}/status".format(device_id)
    headers = create_switchbot_token()
    response = get_request(url, headers)
    body = response.json()["body"]
    logger.info(json.dumps(body, indent=4))
    return body


def get_plug_power():
    plug_status_body = {}

    for item in plug_mapping:
        logger.info('getting plug data from {}'.format(item['label']))
        try:
            body = _get_switchbot_device_body(item['deviceId'])
            try:
                plug_status_body[item['label']] = float(body['weight'])
            except Exception:
                logger.warning('illegal format')
        except Exception as e:
            logger.error('request failed: {}'.format(e))

    return plug_status_body


def get_sb_device_list():
    logger.info('getting switch bot device list')

    url = "https://api.switch-bot.com/v1.1/devices"
    headers = create_switchbot_token()

    try:
        response = get_request(url, headers)
        body = response.json()["body"]
        logger.info(json.dumps(body, indent=4))
    except Exception as e:
        logger.error('request failed: {}'.format(e))


def isHoliday(check_date):
    if check_date.weekday() >= 5:
        return True
    if jpholiday.is_holiday(check_date.date()):
        return True
    if check_date.month == 1 and check_date.day in (2, 3):
        return True
    if check_date.month == 4 and check_date.day == 30:
        return True
    if check_date.month == 5 and check_date.day in (1, 2):
        return True
    if check_date.month == 12 and check_date.day in (30, 31):
        return True
    return False


def get_price_unit(check_date):
    JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
    logger.info(check_date)
    check_time = check_date - datetime.timedelta(minutes=15)
    logger.info(check_time)
    logger.info(check_date.weekday())
    logger.info(jpholiday.is_holiday(check_date.date()))

    check_time_yesterday = check_time - datetime.timedelta(days=1)

    if isHoliday(check_time):
        if datetime.time(hour=22, minute=0, second=0, tzinfo=JST) <= check_time.timetz():
            return 22.98, "night time", check_time
    if isHoliday(check_time_yesterday):
        if check_time.timetz() < datetime.time(hour=8, minute=0, second=0, tzinfo=JST):
            return 22.98, "night time", check_time

    if not isHoliday(check_time):
        if datetime.time(hour=23, minute=0, second=0, tzinfo=JST) <= check_time.timetz():
            return 22.98, "night time", check_time
    if not isHoliday(check_time_yesterday):
        if check_time.timetz() < datetime.time(hour=6, minute=0, second=0, tzinfo=JST):
            return 22.98, "night time", check_time

    if not isHoliday(check_time):
        if (datetime.time(hour=9, minute=0, second=0, tzinfo=JST) <= check_time.timetz() <
                datetime.time(hour=16, minute=0, second=0, tzinfo=JST)):
            return 20.05, "day time", check_time
    else:
        if (datetime.time(hour=8, minute=0, second=0, tzinfo=JST) <= check_time.timetz() <
                datetime.time(hour=22, minute=0, second=0, tzinfo=JST)):
            return 20.05, "day time", check_time

    return 32.65, "life time", check_time


def get_hub_data():
    hub_data_body = {}

    for item in hub_mapping:
        logger.info('getting hub data from {}'.format(item['label']))
        try:
            body = _get_switchbot_device_body(item['deviceId'])
            try:
                if body["deviceType"] == "Hub 2":
                    hub_data_body['LIGHT_LEVEL_{}'.format(item['label'])] = int(body["lightLevel"])
                else:
                    hub_data_body['TEMPERATURE_{}'.format(item['label'])] = float(body["temperature"])
                    hub_data_body['HUMIDITY_{}'.format(item['label'])] = float(body["humidity"])
                    hub_data_body['CO2_{}'.format(item['label'])] = int(body["CO2"])
            except Exception:
                logger.warning('illegal format')
        except Exception as e:
            logger.error('request failed: {}'.format(e))

    logger.info(hub_data_body)
    return hub_data_body


def get_mining_status():
    mining_status_body = {}

    total_hash_rate = 0
    total_revenue_par_day = 0
    total_profilt_par_day = 0
    total_power_usage = 0

    try:
        resp = requests.get(miner_stat, timeout=3.5)
        logger.info(resp)

        if resp.status_code == 200:
            data_list = resp.json()
            logger.info(json.dumps(data_list, indent=4))

            for group in data_list["groupList"]:
                for miner in group["minerList"]:
                    name = miner["name"].upper()

                    mining_status_body[name + "_POOL"] = miner["pool"]
                    mining_status_body[name + "_SOFTWARE"] = miner["softwareType"]

                    if miner["speedInfo"].get("hashrateValue") is not None:
                        mining_status_body[name + "_HASHRATE"] = miner["speedInfo"]["hashrateValue"]
                        total_hash_rate += miner["speedInfo"]["hashrateValue"]

                    if miner["coinInfo"].get("revenuePerDayValueDisplayCurrency") is not None:
                        mining_status_body[name + "_REVENUE_PAR_DAY"] = miner["coinInfo"]["revenuePerDayValueDisplayCurrency"]
                        total_revenue_par_day += miner["coinInfo"]["revenuePerDayValueDisplayCurrency"]
                    elif miner["coinInfo"].get("revenuePerDayValue") is not None:
                        mining_status_body[name + "_REVENUE_PAR_DAY"] = miner["coinInfo"]["revenuePerDayValue"]
                        total_revenue_par_day += miner["coinInfo"]["revenuePerDayValue"]

                    mining_status_body[name + "_PROFIT_PAR_DAY"] = miner["coinInfo"]["profitPerDayValue"]
                    total_profilt_par_day += miner["coinInfo"]["profitPerDayValue"]

                    if miner["coinInfo"].get("isActualPowerUsage") is not None:
                        mining_status_body[name + "_POWER_USAGE"] = miner["coinInfo"]["powerUsageValue"]
                        total_power_usage += miner["coinInfo"]["powerUsageValue"]

                    if miner["coinInfo"].get("algorithm") is not None:
                        mining_status_body[name + "_ALGORITHM"] = miner["coinInfo"]["algorithm"]

                    mining_status_body[name + "_GPU_TEMPERATURE"] = miner["maxTemperatureValue"]

            mining_status_body["TOTAL_HASHRATE"] = total_hash_rate
            mining_status_body["TOTAL_REVENUE_PAR_DAY"] = total_revenue_par_day
            mining_status_body["TOTAL_PROFIT_PAR_DAY"] = total_profilt_par_day
            mining_status_body["TOTAL_POWER_USAGE"] = total_power_usage

    except Exception as e:
        logger.warning("mining status timeout. {}".format(e))

    logger.info(mining_status_body)
    return mining_status_body


def setCurrentElectricityPrice(timestamp):
    current_electricity_price = get_price_unit(timestamp)
    logger.info("Current electricity price: {}".format(current_electricity_price[0]))
    query_string = "&value=" + str(current_electricity_price[0])
    try:
        resp = requests.post(miner_set_electricity_price + query_string, timeout=3.5)
        logger.info(resp)
    except Exception as e:
        logger.warning("setCurrentElectricityPrice failed. {}".format(e))


def parseE7(EDT):
    # 内容が瞬時電力計測値(E7)だったら
    hexPower = EDT[-8:]    # 最後の4バイト（16進数で8文字）が瞬時電力計測値
    intPower = int(hexPower, 16)

    JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
    time_stamp = datetime.datetime.now(JST)
    datetime_str = time_stamp.strftime(_DATETIME_FORMAT)
    date_str = time_stamp.strftime(_DATE_FORMAT)

    body = "瞬時電力:" + str(intPower) + "[W]"
    body = body + "(" + datetime_str + ")"

    if intPower > 4800:
        speak_string = "瞬時電力が" + str(intPower) + "ワットです。"
        speak(speak_string)

    if (state.last_instant_sent is not None and
            (time_stamp - state.last_instant_sent) < datetime.timedelta(seconds=15)):
        logger.info("check power only")
        return

    data_body = {
        "TYPE": "INSTANTANEOUS",
        "POWER": intPower,
        "TIMESTAMP": str(time_stamp.timestamp()),
        "DATETIME": datetime_str,
        "DATE": date_str,
    }

    data_body.update(get_mining_status())

    if (state.last_switchbot_sent is None or
            (time_stamp - state.last_switchbot_sent) > datetime.timedelta(minutes=2)):
        data_body.update(get_hub_data())
        data_body.update(get_plug_power())
        state.last_switchbot_sent = time_stamp

    logger.info(body)
    logger.info(json.dumps(data_body))

    send_message(data_body)

    if state.latest_instant_val is None:
        state.latest_instant_val = {
            key: {"value": value, "updated_at": datetime_str + "+0900"}
            for key, value in data_body.items()
        }
    else:
        for key, value in data_body.items():
            state.latest_instant_val[key] = {"value": value, "updated_at": datetime_str + "+0900"}

    logger.info("merged json: {}".format(json.dumps(state.latest_instant_val)))
    redis_client.set('my_key', json.dumps(state.latest_instant_val))

    state.last_instant_sent = time_stamp


def parseEA(EDT):
    hexYear    = EDT[-22:-22+4]
    hexMonth   = EDT[-18:-18+2]
    hexDay     = EDT[-16:-16+2]
    hexHour    = EDT[-14:-14+2]
    hexMinutes = EDT[-12:-12+2]
    hexSeconds = EDT[-10:-10+2]
    hexPower   = EDT[-8:]

    JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
    time_stamp = datetime.datetime(
        int(hexYear, 16),
        int(hexMonth, 16),
        int(hexDay, 16),
        int(hexHour, 16),
        int(hexMinutes, 16),
        int(hexSeconds, 16),
        tzinfo=JST)

    intPower = int(hexPower, 16) * state.coeff * state.unit
    timestamp_str = time_stamp.strftime(_DATETIME_FORMAT)
    datetime_str = time_stamp.strftime(_DATETIME_FORMAT)
    date_str = time_stamp.strftime(_DATE_FORMAT)

    body = "積算電力:" + str(intPower) + "[kWh]"
    body = body + "(" + timestamp_str + ")"
    logger.info(body)

    last_json_data = {"TIMESTAMP": "0"}

    try:
        with open(app_path + 'last_integral.json', 'r') as f:
            last_json_data = json.load(f)
        logger.info('last data: {}'.format(last_json_data))
    except Exception as e:
        logger.info('first data: {}'.format(e))

    _30min_power = float(0.0)
    _30min_before = time_stamp + datetime.timedelta(minutes=-30)

    try:
        if str(time_stamp.timestamp()) == last_json_data["TIMESTAMP"]:
            logger.info("duplicated")
            return
        if last_json_data["TIMESTAMP"] == str(_30min_before.timestamp()):
            _30min_power = float(intPower) - float(last_json_data["INTEGRATED_POWER"])
            logger.info("power delta: " + str(_30min_power))
    except Exception as e:
        logger.info('TIMESTAMP check failed. just ignore.: {}'.format(e))

    unit_price = get_price_unit(time_stamp)
    logger.info(unit_price)
    charge = _30min_power * unit_price[0]

    data_body = {
        "TYPE": "INTEGRATED",
        "INTEGRATED_POWER": intPower,
        "POWER_DELTA": _30min_power,
        "CHARGE": charge,
        "POWER_CHARGE_TYPE": unit_price[1],
    }

    if unit_price[1] == "day time":
        data_body["DAYTIME_POWER_DELTA"] = _30min_power
        data_body["DAYTIME_CHARGE"] = charge
    elif unit_price[1] == "life time":
        data_body["LIFETIME_POWER_DELTA"] = _30min_power
        data_body["LIFETIME_CHARGE"] = charge
    elif unit_price[1] == "night time":
        data_body["NIGHTTIME_POWER_DELTA"] = _30min_power
        data_body["NIGHTTIME_CHARGE"] = charge
    else:
        logger.warning("unknown charge type")

    data_body["TIMESTAMP"] = str(time_stamp.timestamp())
    data_body["DATETIME"] = datetime_str
    data_body["CHECK_DATETIME"] = unit_price[2].strftime(_DATETIME_FORMAT)
    data_body["DATE"] = date_str

    logger.info(json.dumps(data_body))

    with open(app_path + 'last_integral.json', 'w') as fw:
        json.dump(data_body, fw)
    logger.info("json file saved")

    send_message(data_body)


def parseD3(EDT):
    # 係数
    hexCoeff = EDT[-8:]    # 最後の4バイト（16進数で8文字）が係数
    state.coeff = int(hexCoeff, 16)
    logger.info("係数:" + str(state.coeff))


def parseE1(EDT):
    # 単位
    hexUnit = EDT[-2:]    # 最後の1バイト（16進数で2文字）が単位
    unit_map = {
        "00": 1,
        "01": 0.1,
        "02": 0.01,
        "03": 0.001,
        "04": 0.0001,
        "0A": 10,
        "0B": 100,
        "0C": 1000,
        "0D": 10000,
    }
    if hexUnit in unit_map:
        state.unit = unit_map[hexUnit]
    else:
        logger.warning("parseE1: unknown unit code: {}".format(hexUnit))
    logger.info("単位:" + hexUnit + ":" + str(state.unit))


def sendCommand(command_str):
    command_base = "SKSENDTO 1 {0} 0E1A 1 {1:04X} ".format(ipv6Addr, len(command_str))
    command = command_base.encode() + command_str
    logger.info(b"SEND: " + command)
    ser.write(command)

    logger.info(str(ser.readline()))
    logger.info(str(ser.readline()))

    wait_ok_count = 0

    while wait_ok_count < _MAX_FAILURE_COUNT:
        chk_ok = str(ser.readline().decode('utf-8'))
        logger.info("checking ok?: {}".format(chk_ok))
        if chk_ok.startswith("OK"):
            logger.info("OK!")
            wait_ok_count = 0
            break
        else:
            logger.info("err...: {}".format(wait_ok_count))
            wait_ok_count += 1

    if wait_ok_count >= _MAX_FAILURE_COUNT:
        state.failure_count += 1
    else:
        line = str(ser.readline().decode('utf-8'))    # ERXUDPが来るはず
        logger.info(line)

        # 受信データはたまに違うデータが来たり、
        # 取りこぼしたりして変なデータを拾うことがあるので
        # チェックを厳しめにしてます。

        if line.startswith("ERXUDP"):
            cols = line.strip().split(' ')
            res = cols[8]   # UDP受信データ部分
            seoj = res[8:8+6]
            ESV = res[20:20+2]
            OPC_HEX = res[22:22+2]
            OPC = int(OPC_HEX, 16)
            OPC_COUNT = 0
            CUR_POSITION = 24

            if seoj == "028801" and ESV == "72":
                state.failure_count = 0
                while OPC_COUNT < OPC:
                    # スマートメーター(028801)から来た応答(72)なら
                    EPC = res[CUR_POSITION:CUR_POSITION+2]
                    CUR_POSITION += 2
                    EPD_hex = res[CUR_POSITION:CUR_POSITION+2]
                    EPD = int(EPD_hex, 16)
                    CUR_POSITION += 2
                    EDT = ""
                    if EPD > 0:
                        EDT = res[CUR_POSITION:CUR_POSITION+2*EPD]
                        CUR_POSITION += 2*EPD
                    if EPC == "E7":
                        parseE7(EDT)
                    if EPC == "EA":
                        parseEA(EDT)
                    if EPC == "D3":
                        parseD3(EDT)
                    if EPC == "E1":
                        parseE1(EDT)
                    OPC_COUNT += 1
            else:
                state.failure_count += 1
        else:
            state.failure_count += 1

    logger.info("failure_count: {}".format(state.failure_count))

    if state.failure_count > _MAX_FAILURE_COUNT:
        logger.info("RESTART!: {}".format(state.failure_count))
        for i in range(10):
            time.sleep(1)
            logger.info('sleep_count: {}'.format(i + 1))
        sys.exit(-1)
    else:
        logger.info("end of sendCommand")


def speak(speech_text):
    global _cast_cache
    logger.info("pychromecast start")

    try:
        casts = _get_chromecasts()
    except Exception as e:
        logger.exception("Chromecast discovery failed: {}".format(e))
        return

    speak_enc = urllib.parse.quote(speech_text)
    mp3url = "https://translate.google.com/translate_tts?ie=UTF-8&q=" + speak_enc + "&tl=ja&client=tw-ob"
    logger.info(mp3url)

    for googlehome in casts:
        try:
            if not googlehome.wait(timeout=5):
                logger.warning("Chromecast did not connect within 5s, skipping")
                continue
            mc = googlehome.media_controller
            mc.play_media(mp3url, 'audio/mp3')

            # 再生開始を待ち、完了まで監視する
            # has_played=False: まだ再生していない状態からスタート（Nest Hub 対応）
            player_state = None
            has_played = False
            t = 10.0
            while t > 0:
                current_state = googlehome.media_controller.status.player_state
                if current_state != player_state:
                    player_state = current_state
                    logger.info("Player state: {}".format(googlehome.media_controller.status))
                if player_state == "PLAYING":
                    has_played = True
                elif has_played and player_state in ("IDLE", "UNKNOWN", None):
                    # 一度再生が始まり、その後停止したら終了
                    break
                time.sleep(0.1)
                t -= 0.1

        except Exception as e:
            logger.exception("error in speak: {}".format(e))
            _cast_cache = None  # 接続エラー時はキャッシュをリセットして次回再スキャン

    logger.info("google home notifier end")


if __name__ == '__main__':
    logger = logging.getLogger('Logging')

    logname = "/var/log/tools/b-route.log"
    fmt = "%(asctime)s %(levelname)s %(name)s [%(thread)d][%(filename)s:%(lineno)d]: %(message)s"
    logging.basicConfig(level=10, format=fmt)

    logger.info("STARTING...")
    get_sb_device_list()

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
    scanRes = {}

    # スキャンのリトライループ（何か見つかるまで）
    while "Channel" not in scanRes:
        # アクティブスキャン（IE あり）を行う
        # 時間かかります。10秒ぐらい？
        ser.write(("SKSCAN 2 FFFFFFFF " + str(scanDuration) + "\r\n").encode())

        # スキャン1回について、スキャン終了までのループ
        scanEnd = False
        scan_counter = 0
        while not scanEnd:
            line = str(ser.readline().decode('utf-8'))
            scan_counter += 1
            logger.info("counter: {}, {}".format(scan_counter, line))

            if scan_counter > _MAX_FAILURE_COUNT * 10:
                logger.error("scanning error!!")
                ser.close()
                sys.exit()

            if line.startswith("EVENT 22"):
                # スキャン終わったよ（見つかったかどうかは関係なく）
                scanEnd = True
            elif line.startswith("  "):
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
        scanDuration += 1

        if 14 < scanDuration and "Channel" not in scanRes:
            # 引数としては14まで指定できるが、7で失敗したらそれ以上は無駄っぽい
            logger.error("スキャンリトライオーバー")
            ser.close()
            sys.exit()  #### 糸冬了 ####

    # スキャン結果からChannelを設定。
    ser.write(("SKSREG S2 " + scanRes["Channel"] + "\r\n").encode())
    logger.info(str(ser.readline().decode('utf-8')))
    logger.info(str(ser.readline().decode('utf-8')))

    # スキャン結果からPan IDを設定
    ser.write(("SKSREG S3 " + scanRes["Pan ID"] + "\r\n").encode())
    logger.info(str(ser.readline().decode('utf-8')))
    logger.info(str(ser.readline().decode('utf-8')))

    # MACアドレス(64bit)をIPV6リンクローカルアドレスに変換。
    # (BP35A1の機能を使って変換しているけど、単に文字列変換すればいいのではという話も？？)
    ser.write(("SKLL64 " + scanRes["Addr"] + "\r\n").encode())
    logger.info(str(ser.readline().decode('utf-8')))
    ipv6Addr = str(ser.readline().decode('utf-8')).strip()

    # PANA 接続シーケンスを開始します。
    ser.write(("SKJOIN " + ipv6Addr + "\r\n").encode())
    logger.info(str(ser.readline().decode('utf-8')))
    logger.info(str(ser.readline().decode('utf-8')))

    # PANA 接続完了待ち（10行ぐらいなんか返してくる）
    bConnected = False
    while not bConnected:
        line = str(ser.readline().decode('utf-8'))
        if line.startswith("EVENT 24"):
            logger.error("PANA 接続失敗")
            ser.close()
            sys.exit()  #### 糸冬了 ####
        elif line.startswith("EVENT 25"):
            # 接続完了！
            bConnected = True

    # これ以降、シリアル通信のタイムアウトを設定
    ser.timeout = 8

    # スマートメーターがインスタンスリスト通知を投げてくる
    # (ECHONET-Lite_Ver.1.12_02.pdf p.4-16)
    logger.info(str(ser.readline().decode('utf-8')))

    counter = 30

    while True:
        JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
        cur_timestamp = datetime.datetime.now(JST)
        cur_datetime_str = cur_timestamp.strftime(_DATETIME_FORMAT_TZ)

        logger.info('current jst: {}'.format(cur_datetime_str))
        setCurrentElectricityPrice(cur_timestamp)

        logger.info('before GET_NEW_POWER')
        sendCommand(GET_NOW_POWER)
        logger.info('after GET_NEW_POWER')

        time.sleep(1)

        if counter > 15:
            counter = 0
            logger.info('before GET_LATEST30')
            sendCommand(GET_LATEST30)
            logger.info('after GET_LATEST30')
            time.sleep(1)

        counter += 1
        logger.info('loop counter: {}'.format(counter))

    # 無限ループだからここには来ないけどな
    ser.close()
