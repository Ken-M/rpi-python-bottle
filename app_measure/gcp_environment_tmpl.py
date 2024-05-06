#!/usr/bin/env python
# -*- coding: utf-8 -*-

sa_email=''
audience=''
auth_api='https://www.googleapis.com/oauth2/v4/token'
key = ""
algorithm = 'RS256'
app_path = '/home/bottle/app/'
remo_local_addr = ''

hub_mapping =  [ {"label":"a" ,"deviceId":"DUMMY_______"},
                 {"label":"b" ,"deviceId":"DUMMY_______"},
                 {"label":"c" ,"deviceId":"DUMMY_______"},
                 {"label":"d" ,"deviceId":"DUMMY_______"}]

plug_mapping = [{"label":"a"  ,"deviceId":"DUMMY_______"},
                {"label":"b"  ,"deviceId":"DUMMY_______"},
                {"label":"c"  ,"deviceId":"DUMMY_______"}]

google_home_list = [ "*.*.*.*", "*.*.*.*" ]

miner_stat = ''
miner_set_electricity_price = ''