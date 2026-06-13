# rpi-python-bottle — CLAUDE.md

## プロジェクト概要

Raspberry Pi 5 上で稼働する**電力計測・スマートホーム連携サーバー**。

- ECHONET Lite（Bルート）対応スマートメーターから電力データを収集
- SwitchBot Hub 2 / プラグの温湿度・CO2・照度・消費電力を取得
- Google Home（Nest Hub）に音声通知（瞬時電力 > 4800 W 時）
- 収集データを GCP Cloud Functions 経由でクラウドへ送信
- Flask ダッシュボード（:5000）でリアルタイム表示
- Redis でサービス間データ共有

---

## ディレクトリ構成

```
.
├── docker-compose.yml          # 全サービス定義（redis / app_measure / my_flask_app / ngrok）
├── build-and-push.bat          # Windows 向け Docker Hub クロスビルド・プッシュスクリプト
├── README.md                   # 旧メモ（Python 3.5 時代。現在は本ファイルを参照）
├── .gitignore
├── app_measure/                # 電力計測・GCP 送信サービス
│   ├── Dockerfile              # debian:trixie + Python 3.14.4 ソースビルド
│   ├── get-power.py            # メインループ（スマートメーター通信・Redis 書き込み）
│   ├── echonet.py              # ECHONET Lite コマンド定数（GET_NOW_POWER, GET_LATEST30）
│   ├── gcp_environment_tmpl.py # GCP 設定テンプレート → gcp_environment.py を Pi 上に配置
│   └── secret_tmpl.py          # 認証情報テンプレート → secret.py を Pi 上に配置
├── my_flask_app/               # ホームダッシュボード Flask アプリ
│   ├── Dockerfile              # python:3.14-slim ベース
│   ├── my_flask_app.py         # Flask 本体（Redis 読み取り・HTML レンダリング）
│   └── my_flask_app_tmpl.py    # 認証情報テンプレート → my_flask_app_secret.py を Pi 上に配置
├── cloudfunctions/             # GCP Cloud Functions（Node.js）
│   ├── index.js
│   └── package.json
└── ngrok/
    └── ngrok_tmpl.yml          # ngrok 設定テンプレート → ngrok.yml を Pi 上に配置
```

`*_tmpl.py` / `*_tmpl.yml` は機密情報を含む実ファイルのひな型。  
実ファイル（`secret.py`, `gcp_environment.py`, `my_flask_app_secret.py`, `ngrok.yml`）は `.gitignore` 対象でデプロイ先に手動配置。

---

## サービス構成（docker-compose.yml）

| サービス | コンテナ名 | IP | ポート | 役割 |
|---|---|---|---|---|
| redis | redis | 172.19.0.5 | 6379 | サービス間 KV ストア |
| measure-application | rpi-python-bottle-app-measure | 172.19.0.10 | — | スマートメーター通信・GCP 送信 |
| my_flask_app | my_flask_app | 172.19.0.15 | 5000 | ホームダッシュボード |
| ngrok | — | 172.19.0.20 | 4040 | 外部公開トンネル |

ネットワーク: `app_net`（172.19.0.0/16 bridge）

`app_measure` は `/dev/ttyUSB0`（BP35A1 スマートメータードングル）をデバイスマウントし、  
`dialout` グループ（GID 20）でアクセスする。`privileged: true` / `SYS_RAWIO` が必要。

ngrok（172.19.0.20）からの `/get_data` リクエストには HTTP Basic 認証が要求される（`ip_based_authentication` デコレーター）。

---

## Docker Hub イメージ名

| サービス | イメージ名 |
|---|---|
| app_measure | `kenonemorita/rpi-python-bottle-app-measure` |
| my_flask_app | `kenonemorita/rpi-python-bottle-my-flask-app` |

---

## ビルド方法

### Windows（通常運用）

プロジェクトルートで実行：

```bat
build-and-push.bat
```

処理内容：
1. `docker login`（Docker Hub 認証）
2. buildx ビルダー `rpi-builder` を作成または再利用
3. `app_measure` を `linux/arm64` でビルド＆プッシュ（**30〜60 分**）
4. `my_flask_app` を `linux/arm64` でビルド＆プッシュ

### 個別ビルド

```bash
# app_measure のみ
docker buildx build --platform linux/arm64 --pull --push \
  --secret id=takumi_guard_token,src=takumi_guard_token \
  -t kenonemorita/rpi-python-bottle-app-measure ./app_measure

# my_flask_app のみ
docker buildx build --platform linux/arm64 --pull --push \
  --secret id=takumi_guard_token,src=takumi_guard_token \
  -t kenonemorita/rpi-python-bottle-my-flask-app ./my_flask_app
```

---

## デプロイ

```bash
# Raspberry Pi 上で実行
docker compose pull
docker compose up -d
```

---

## 開発上の注意点

### app_measure: Python ソースビルド（debian:trixie）

- ベースイメージ `debian:trixie` 上で **Python 3.14.4 をソースコンパイル**する
- `ca-certificates` のインストールが**必須**。欠落すると `wget` が python.org の TLS 証明書検証に失敗してビルドが中断する（クロスビルド時も同様）
- ビルド時間は 30〜60 分。Dockerfile を変更していなければ Docker キャッシュが効く

### Rust は不要

`cryptography` と `grpcio` はいずれも `linux/arm64` 向け pre-built wheel が PyPI に存在する。  
`rustup` のインストールは不要。Dockerfile に Rust 関連の記述を追加しないこと。

### シークレットファイルの扱い

`*_tmpl.*` を参考に以下のファイルをデプロイ先に直接配置する：

| ファイル | 内容 |
|---|---|
| `app_measure/secret.py` | Bルート ID/パスワード、GCP SA キー、SwitchBot API キー等 |
| `app_measure/gcp_environment.py` | GCP エンドポイント・対象オーディエンス等 |
| `my_flask_app/my_flask_app_secret.py` | Basic 認証ユーザー辞書（`USER_DATA`） |
| `ngrok/ngrok.yml` | ngrok 認証トークン・トンネル設定 |
| `takumi_guard_token`（プロジェクトルート） | Takumi Guard の PyPI 認証トークン（`tg_anon_…`）。ビルド時に使用 |

### サプライチェーン対策（Takumi Guard / Shisho Guard）

`app_measure` / `my_flask_app` の `pip install` は [Takumi Guard](https://shisho.dev/docs/ja/t/guard/quickstart/) の
PyPI ミラー（`pypi.flatt.tech`）経由で取得し、悪性パッケージをブロックする。

- 認証は **匿名（メール認証）** ティアを利用。`takumi_guard_token.tmpl` を参考に、
  プロジェクトルートへ `takumi_guard_token`（`.gitignore` 済み）を配置しトークンを記載する。
- トークンは Docker の **BuildKit secret**（`--mount=type=secret,id=takumi_guard_token`）として
  ビルド時のみマウントされ、イメージ層・`docker history` には残らない。
- 各 `pip` 系 `RUN` 内で `PIP_INDEX_URL=https://token:<TOKEN>@pypi.flatt.tech/simple/` を組み立てる。
  トークン未設定／空の場合は匿名モード（`https://pypi.flatt.tech/simple/`）にフォールバックする。
- `build-and-push.bat` は両ビルドに `--secret id=takumi_guard_token,src=takumi_guard_token` を渡す。
  個別ビルド時も同じ `--secret` フラグを付けること。
- Dockerfile 冒頭の `# syntax=docker/dockerfile:1.7` は secret マウントに必要なため削除しない。

### my_flask_app ダッシュボード

- `/get_data` — Redis から最新センサーデータを取得して HTML テーブルを返す
- `/health` — `POWER` データが 1 分以内に更新されていれば 200、古ければ 503
- ダークテーマ固定（CSS 変数 `--bg: #0f1117` ほか）。30 秒ごと自動リロード
- POWER > 4800 W または CO2 > 1500 ppm でアラートバッジ＋点滅アニメーション
- センサーグループ: Power and Plugs / Bedroom / Living Room / Study Room / 1F

### get-power.py の Nest Hub 通知（speak 関数）

`speak()` は `pychromecast` で Nest Hub を検索し、Google TTS（HTTPS）の MP3 を再生する。  
接続再スキャンのコストを避けるため `_cast_cache` にデバイスリストをキャッシュする。  
再生完了の検出は `has_played` フラグ + `player_state` の組み合わせで制御。  
`googlehome.wait(timeout=5)` の戻り値を確認し、タイムアウト時はそのデバイスをスキップする。

### ローカル git の注意

OneDrive 同期競合により pack オブジェクト破損の可能性がある。  
`git log` や `git status` が異常を示した場合は `git gc` を実行すること。  
（解消しない場合は GitHub からクリーンにクローンし直すこと）

---

## 開発ルール

**コード修正時は必ずブランチへの commit・push・PR 作成まで行うこと。**

1. 作業用ブランチを作成: `git checkout -b claude/<説明的な名前>`
2. 変更をコミット: `git add <files> && git commit -m "<type>: <説明>"`
3. プッシュ: `git push origin HEAD`
4. PR 作成: `gh pr create --title "..." --body "..."`
5. `master` ブランチへの直接コミットは禁止

コミットメッセージは Conventional Commits 形式（`fix:`, `feat:`, `docs:`, `refactor:` 等）を使用。
