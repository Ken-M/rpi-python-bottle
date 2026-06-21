# syntax=docker/dockerfile:1.7
# Python は debian:trixie (Debian 13 stable) からソースビルド
FROM --platform=$TARGETPLATFORM debian:trixie

USER root

# ca-certificates を含む必要パッケージを一括インストール
# ca-certificates は wget が python.org の TLS 証明書を検証するために必須
RUN apt-get update && apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        vim sudo wget curl net-tools git \
        build-essential checkinstall \
        libncursesw5-dev libgdbm-dev libc6-dev zlib1g-dev \
        libsqlite3-dev tk-dev libssl-dev openssl \
        libbz2-dev libreadline-dev liblzma-dev libffi-dev \
        python3-dev pkg-config && \
    apt-get -qy remove python3 python3-grpcio python3-grpc-tools && \
    apt-get -qy autoremove && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python 3.14.6 をソースからビルド・インストール後、ソースを削除
WORKDIR /usr/local/src
RUN wget https://www.python.org/ftp/python/3.14.6/Python-3.14.6.tar.xz && \
    tar xvf Python-3.14.6.tar.xz && \
    cd Python-3.14.6 && \
    ./configure --enable-optimizations && \
    make && make install && \
    cd / && rm -rf /usr/local/src/Python-3.14.6 /usr/local/src/Python-3.14.6.tar.xz

# pip をアップグレード
# Takumi Guard (Shisho Guard) 経由で PyPI を取得しサプライチェーン攻撃を防ぐ。
# トークンは BuildKit secret (takumi_guard_token) でマウントし、イメージ層へは焼き込まない。
# トークン未設定時は匿名モード (registry のみ) でフォールバックする。
RUN --mount=type=secret,id=takumi_guard_token \
    TG_TOKEN="$(grep -oE 'tg_[A-Za-z0-9_]+' /run/secrets/takumi_guard_token 2>/dev/null | head -n1)"; \
    export PIP_INDEX_URL="https://${TG_TOKEN:+token:${TG_TOKEN}@}pypi.flatt.tech/simple/"; \
    pip3 install --upgrade pip setuptools wheel

# Python パッケージをインストール
# cryptography・grpcio はいずれも linux/arm64 の pre-built wheel が PyPI に存在するため
# Rust コンパイルは不要（Rustup インストール不要）
# こちらも Takumi Guard 経由で取得する（secret マウントは RUN ごとに必要）。
RUN --mount=type=secret,id=takumi_guard_token \
    TG_TOKEN="$(grep -oE 'tg_[A-Za-z0-9_]+' /run/secrets/takumi_guard_token 2>/dev/null | head -n1)"; \
    export PIP_INDEX_URL="https://${TG_TOKEN:+token:${TG_TOKEN}@}pypi.flatt.tech/simple/"; \
    pip3 install --no-cache-dir \
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
