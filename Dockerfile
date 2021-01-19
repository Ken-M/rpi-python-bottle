# Pythonは公式イメージ
FROM balenalib/rpi-raspbian:stretch

# 各ライブラリインストール
# Pythonがパッケージ依存するものもインストール
# Pythonプロフェッショナルプログラミング第2版P9より
USER root

RUN apt-get update
RUN apt-get upgrade -y
# よく使うコマンド
RUN apt-get install -y 	vim \
						sudo \
                        wget \
                        net-tools \
                        git

# Python3インストールに必要
RUN apt-get install -y build-essential \
                       libncursesw5-dev \
                       libgdbm-dev \
                       libc6-dev \
                       zlib1g-dev \
                       libsqlite3-dev \
                       tk-dev \
                       libssl-dev \
                       openssl \
                       libbz2-dev \
                       libreadline-dev \
                       libffi-dev

# Python3をインストール
RUN wget https://www.python.org/ftp/python/3.9.1/Python-3.9.1.tgz
RUN tar xvf Python-3.9.1.tgz 
WORKDIR Python-3.9.1
RUN ./configure && make && make install

# pip3をインストール
RUN apt-get install -y python-crypto python3-pip 
RUN pip3 install --upgrade pip

# pipでインストール
# virtualenv Pythonの仮想環境構築コマンド
# bottle Pytrhonの軽量フレームワーク
# flake8 コーディングスタイル/シンタックスのチェック
# ipython Pythonのインタラクティブモード拡張
RUN pip3 install --upgrade pip
RUN pip3 install virtualenv \
				ipython \
				flake8 \
                pyserial \
                retry \
                jpholiday \
                cryptography
RUN wget https://files.pythonhosted.org/packages/eb/db/5c2d42e65add65ded08a2b0d1f27a9c7bbfff74e5c8007c79b5aefb03c32/grpcio-1.34.1-cp36-cp36m-linux_armv7l.whl
RUN pip3 install grpcio-1.34.1-cp36-cp36m-linux_armv7l.whl
RUN pip3 install google-api-python-client \
                google-auth-httplib2 \
                google-auth \
                google-cloud-pubsub \
                pyjwt \
                requests
RUN pip3 install pycryptodome \
                tinytuya \
                tuyapower

# ユーザ作成
RUN groupadd web
RUN useradd -d /home/bottle -m bottle

# ドングルからデータを読むための権限を追加
RUN usermod -a -G tty bottle
RUN usermod -a -G dialout bottle
# RUN chmod 0666 /dev/ttyUSB0
USER bottle

# vim の設定ファイル
ADD ./vim/.vimrc /home/bottle/
RUN mkdir /home/bottle/.vim
RUN mkdir /home/bottle/.vim/ftplugin
ADD ./vim/python.vim /home/bottle/.vim/ftplugin/
RUN mkdir /home/bottle/.vim/bundle
RUN git clone https://github.com/Shougo/neobundle.vim /home/bottle/.vim/bundle/neobundle.vim
