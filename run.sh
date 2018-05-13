docker build . -t broadlink-rest
docker run -ti -p 8080:8080 -v `pwd`/settings.ini:/usr/src/app/settings.ini broadlink-rest python server.py
