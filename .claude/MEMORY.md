# rpi-python-bottle — プロジェクトメモリインデックス

このファイルは Claude がこのリポジトリを扱う際の記憶インデックスです。

---

## インフラ情報

- **デプロイ先**: Raspberry Pi 5
- **Trivy スキャン**: 毎日 00:00 cron で自動実行済み

---

## app_measure（電力計測サービス）

- ベースイメージ: `debian:trixie`、Python **3.14.4 ソースビルド**
- ビルド時間: 30〜60 分（キャッシュが効く場合を除く）
- **Rust 不要**: `cryptography` / `grpcio` は linux/arm64 の pre-built wheel が存在するため `rustup` は不要
- **クロスビルド時の注意**: `ca-certificates` を必ずインストールすること。ないと `wget` が python.org の TLS 証明書検証で失敗する

---

## get-power.py の修正済み問題（Nest Hub ブロードキャスト）

以下の不具合はすべて修正済み（master 反映済み）：

1. `has_played` の初期値バグ（`True` → `False`）→ 無限ループが解消
2. `socket_client.is_connected` の廃止 API → `googlehome.wait(timeout=5)` の戻り値確認に変更
3. Google TTS URL を HTTPS 化（`http://` → `https://`）
4. Chromecast デバイス接続キャッシュ（`_cast_cache`）を追加して再スキャンコストを削減

---

## my_flask_app（ホームダッシュボード）

- ダークテーマ固定（CSS 変数）。`prefers-color-scheme` 対応は未実装
- 30 秒ごと自動リロード
- POWER > 4800 W / CO2 > 1500 ppm でアラート表示

---

## git リポジトリの注意

- OneDrive 同期競合による **pack オブジェクト破損**の可能性あり
- 症状が出たら GitHub からクリーンにクローンし直すこと

---

## Docker Hub イメージ

| サービス | イメージ名 |
|---|---|
| app_measure | `kenonemorita/rpi-python-bottle-app-measure` |
| my_flask_app | `kenonemorita/rpi-python-bottle-my-flask-app` |
