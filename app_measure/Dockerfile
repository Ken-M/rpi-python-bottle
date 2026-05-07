# Python は debian:trixie (Debian 13 stable) からソースビルド
FROM --platform=$TARGETPLATFORM debian:trixie

USER root

# ca-certificates を含む必要パッケージを一括インストール
# ca-certificates は wget が python.org の TLS 証明書を検証するために必須
# libgnutls30t64: CVE-2026-33845 (CRITICAL) DoS via DTLS zero-length の修正を確実に適用
RUN apt-get update && apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        libgnutls30t64 \
        vim sudo wget curl net-tools git \
        build-essential checkinstall \
        libncursesw5-dev libgdbm-dev libc6-dev zlib1g-dev \
        libsqlite3-dev tk-dev libssl-dev openssl \
        libbz2-dev libreadline-dev liblzma-dev libffi-dev \
        python3-dev pkg-config && \
    apt-get -qy remove python3 python3-grpcio python3-grpc-tools && \
    apt-get -qy autoremove && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python 3.14.4 をソースからビルド・インストール後、ソースを削除
WORKDIR /usr/local/src
RUN wget https://www.python.org/ftp/python/3.14.4/Python-3.14.4.tar.xz && \
    tar xvf Python-3.14.4.tar.xz && \
    cd Python-3.14.4 && \
    ./configure --enable-optimizations && \
    make && make install && \
    cd / && rm -rf /usr/local/src/Python-3.14.4 /usr/local/src/Python-3.14.4.tar.xz

# pip をアップグレード
RUN pip3 install --upgrade pip setuptools wheel

# Python パッケージをインストール
# cryptography・grpcio はいずれも linux/arm64 の pre-built wheel が PyPI に存在するため
# Rust コンパイルは不要（Rustup インストール不要）
RUN pip3 install --no-cache-dir \
        wheel \
        pyserial \
        retry2 \
        jpholiday \
        pycryptodome \
        requests \
        pyjwt \
        google-api-python-client \
        google-auth-httplib2 \
        google-auth \
        pychromecast \
        six \
        grpcio \
        cryptography \
        pip-review \
        redis && \
    pip-review --auto

# ユーザ作成 + ドングル読み取り権限付与
RUN groupadd web && \
    useradd -d /home/bottle -m bottle && \
    usermod -a -G tty bottle && \
    usermod -a -G dialout bottle

USER bottle
