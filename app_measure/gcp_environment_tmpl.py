#!/usr/bin/env python
# -*- coding: utf-8 -*-

sa_email=''
audience=''
auth_api='https://www.googleapis.com/oauth2/v4/token'
key = ""
algorithm = 'RS256'
app_path = '/home/bottle/app/'
remo_local_addr = ''

temp_mapping = { "**:**:**:**:**:**":"HOGE",
                 "**:**:**:**:**:**":"FOO",
                 "**:**:**:**:**:**":"BAR" }

plug_mapping = [{"label":"hoge", "dev_id":"hogehoge", "address":"*.*.*.*", "local_key":"hogehoge"}]
google_home_list = [ "*.*.*.*", "*.*.*.*" ]

miner_stat = ''
miner_set_electricity_price = ''