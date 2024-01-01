# Pythonは公式イメージ
FROM --platform=$BUILDPLATFORM balenalib/rpi-raspbian:bookworm

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
                       checkinstall \
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
                       liblzma-dev \
                       libffi-dev 
                       # python-dev

RUN apt-get install build-essential libssl-dev libffi-dev \   
   python3-dev pkg-config      
RUN apt-get -qy remove python3 python3-grpcio python3-grpc-tools
RUN apt-get autoremove


#WORKDIR /usr/local/src
#RUN wget https://www.openssl.org/source/openssl-3.0.8.tar.gz && tar -xvzf openssl-3.0.8.tar.gz

#WORKDIR /usr/local/src/openssl-3.0.8
#RUN ./config --prefix=/usr/local/ssl --openssldir=/usr/local/ssl shared zlib -Wl,-Bsymbolic-functions -fPIC shared && make && make install_sw
#RUN echo /usr/local/ssl/lib64 > /etc/ld.so.conf.d/openssl-3.0.8.conf
#RUN ldconfig -v
#RUN apt-get -qy remove openssl
#RUN apt-get autoremove
#ENV PATH "$PATH:/usr/local/ssl/bin"

#WORKDIR /usr/local/src
#RUN rm -rf openssl-3.0.8 openssl-3.0.8.tar.gz

# Python3をインストール
WORKDIR /
RUN wget https://www.python.org/ftp/python/3.12.1/Python-3.12.1.tar.xz
RUN tar xvf Python-3.12.1.tar.xz
WORKDIR Python-3.12.1
#RUN ./configure --enable-optimizations --with-openssl=/usr/local/ssl --with-openssl-rpath=auto && make && make install
RUN ./configure --enable-optimizations && make && make install

# pip3をインストール
RUN pip3 install --upgrade pip
RUN python3 -m pip install --upgrade pip setuptools wheel
RUN pip3 install pip-review
RUN pip-review --auto

# rust

##ENV RUST_VERSION stable
#ENV HOME /home/root
##ENV CARGO_REGISTRIES_CRATES_IO_PROTOCOL sparse
#ENV PATH $PATH:$HOME/.cargo/bin
#RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain ${RUST_VERSION}

#RUN rustup install ${RUST_VERSION}
#RUN rustup update ${RUST_VERSION}
#RUN . $HOME/.cargo/env

ENV RUST_HOME /usr/local/lib/rust
ENV RUSTUP_HOME ${RUST_HOME}/rustup
ENV CARGO_HOME ${RUST_HOME}/cargo
ENV CARGO_REGISTRIES_CRATES_IO_PROTOCOL sparse
RUN mkdir /usr/local/lib/rust && \
    chmod 0755 $RUST_HOME
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs > ${RUST_HOME}/rustup.sh \
    && chmod +x ${RUST_HOME}/rustup.sh \
    && ${RUST_HOME}/rustup.sh -y --default-toolchain stable --no-modify-path
ENV PATH $PATH:$CARGO_HOME/bin

RUN cargo new --bin build-index \
  && cd build-index \
  && cargo add rand_core \
  && cd .. \
  && rm -rf build-index

ENV GRPC_PYTHON_BUILD_SYSTEM_OPENSSL 1
ENV GRPC_PYTHON_BUILD_SYSTEM_ZLIB 1

# ENV OPENSSL_DIR /usr/local/ssl
# RUN pip3 wheel --wheel-dir=/tmp/wh --no-cache-dir --no-binary :all: cryptography grpcio

# RUN pip3 uninstall -y grpcio grpcio-tools
# RUN apt-get install -y python3-grpcio python3-grpc-tools
# RUN apt-get install -y python3-grpc-tools

# pipでインストール
RUN pip3 install wheel
RUN pip3 install pyserial
RUN pip3 install retry2
RUN pip3 install jpholiday
RUN pip3 install pycryptodome
RUN pip3 install tinytuya
RUN pip3 install tuyapower
RUN pip3 install requests
RUN pip3 install pyjwt
RUN pip3 install google-api-python-client
RUN pip3 install google-auth-httplib2
RUN pip3 install google-auth
RUN pip3 install pychromecast
RUN pip3 install gTTS
RUN pip3 install --ignore-installed six
RUN pip3 install grpcio
RUN pip3 install cryptography


               

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
