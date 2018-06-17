#!/usr/bin/env python
# -*- coding: utf-8 -*-

# オリジナルは、@puma_46 さんが https://qiita.com/puma_46/items/1d1589583a0c6bef796c で公開しているコード

from __future__ import print_function
from echonet import *
from secret import *

import sys
import serial
import time
import logging
import logging.handlers
import datetime
import locale
import urllib

coeff = 1
unit = 0.1

def writeFile(filename,msg) :
    f = open(filename,'w')
    f.write(msg)
    f.close()

def parthE7(EDT) :
    # 内容が瞬時電力計測値(E7)だったら
    hexPower = EDT[-8:]    # 最後の4バイト（16進数で8文字）が瞬時電力計測値
    intPower = int(hexPower, 16)
    d = datetime.datetime.today()

    body = "瞬時電力:"+str(intPower)+"[W]"
    body = body + "(" +d.strftime("%H:%M:%S") + ")"
    
    response = urllib.request.urlopen('http://172.17.0.4:8080/input_instantaneous?server_id=1&power=' + str(intPower) + '&date=' + urllib.parse.quote(d.strftime("%Y/%m/%d %H:%M:%S", '')) + '&user_id=1')
    data = response.read()
    
    print ( "サーバレスポンス : ", data )	
    
    logger.info(body)

def parthEA(EDT) :
    hexYear    = EDT[-22:-22+4]
    hexMonth   = EDT[-18:-18+2]
    hexDay     = EDT[-16:-16+2]
    hexHour    = EDT[-14:-14+2]
    hexMinutes = EDT[-12:-12+2]
    hexSeconds = EDT[-10:-10+2]
    hexPower   = EDT[-8:]

    d = datetime.datetime(int(hexYear,16),
                          int(hexMonth,16),
                          int(hexDay,16),
                          int(hexHour,16),
                          int(hexMinutes,16),
                          int(hexSeconds,16))    

    intPower = int(hexPower,16) * coeff * unit

    body = "積算電力:"+str(intPower)+"[kWh]"
    body = body + "(" +d.strftime("%Y/%m/%d %H:%M:%S") + ")"
	
    response = urllib.request.urlopen('http://172.17.0.4:8080/input_integrated?server_id=1&integrated_power=' + str(intPower) + '&date=' + urllib.parse.quote(d.strftime("%Y/%m/%d %H:%M:%S", '')) + '&user_id=1')
    data = response.read()
    
    print ( "サーバレスポンス : ", data )	
	
    logger.info(body)

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
    logger.info(command)
    # コマンド送信
    ser.write(command)

    #print(ser.readline(), end="") # エコーバック
    #print(ser.readline(), end="") # EVENT 21 が来るはず（チェック無し）
    #print(ser.readline(), end="") # OKが来るはず（チェック無し）
    logger.info(str(ser.readline()))
    logger.info(str(ser.readline()))
    logger.info(str(ser.readline()))
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


#ファイル出力設定
POWER_FILE_NAME = "power.log"
WRITE_PATH="/home/pi/p_data/"

#ロガー取得
logger = logging.getLogger('Logging')

logname = "/var/log/tools/b-route.log"
fmt = "%(asctime)s %(levelname)s %(name)s :%(message)s"
#以下のどちらかを選んで コメントアウトしてください
#こちらのコメントを外すとログ標準出力になります。
#ログレベルもデバック用になります
logging.basicConfig(level=10, format=fmt)
#こちらのコメントを外すとログがファイル出力になります。
#logging.basicConfig(level=30, filename=logname, format=fmt)

# シリアルポートデバイス名
#serialPortDev = 'COM3'  # Windows の場合
serialPortDev = '/dev/ttyUSB0'  # Linux(ラズパイなど）の場合
#serialPortDev = '/dev/cu.usbserial-A103BTPR'    # Mac の場合

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
while True :
	sendCommand(GET_NOW_POWER)
	time.sleep(10)
	sendCommand(GET_LATEST30)
	time.sleep(20)

# 無限ループだからここには来ないけどな
ser.close()