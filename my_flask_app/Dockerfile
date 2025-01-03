FROM python:3.9-slim

WORKDIR /app

COPY my_flask_app.py /app

RUN pip install redis flask

CMD ["python", "my_flask_app.py"]
