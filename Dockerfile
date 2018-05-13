FROM python:2.7
RUN mkdir /usr/src/app
WORKDIR /usr/src/app
RUN pip install broadlink configparser netaddr
COPY *.py ./
