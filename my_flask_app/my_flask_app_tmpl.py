# Template for basic authentication information

# USER_DATA の値は平文パスワードではなく werkzeug のハッシュ文字列を設定する。
# ハッシュは以下のコマンドで生成できる:
#   python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your_password'))"
USER_DATA = {
    "your_username": "scrypt:32768:8:1$...(generate_password_hash の出力)..."
}
