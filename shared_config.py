#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 電力単価・アラート閾値の一元管理ファイル。
# docker-compose.yml で app_measure / my_flask_app 両コンテナの
# アプリディレクトリへ read-only mount して共有する（イメージには含まれない）。

# 電力量料金単価 [円/kWh]（時間帯別）
PRICE_NIGHT_TIME = 22.98   # 夜間
PRICE_DAY_TIME = 20.05     # 昼間（平日 9-16 時 / 休日 8-22 時）
PRICE_LIFE_TIME = 32.65    # 生活時間帯（上記以外）

# アラート閾値
# app_measure: 瞬時電力がこの値を超えると Nest Hub へ音声通知
# my_flask_app: ダッシュボードのアラートバッジ表示に使用
POWER_ALERT_THRESHOLD_W = 4800
CO2_ALERT_THRESHOLD_PPM = 1500
