FROM python:3.9-slim

USER root
RUN apt-get update
RUN apt-get upgrade -y
WORKDIR /app

RUN pip3 install redis flask Flask-HTTPAuth
RUN pip3 install pip-review
RUN pip-review --auto
