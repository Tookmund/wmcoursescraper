FROM python:3.10-slim-buster
WORKDIR /app
COPY requirements.txt scraper.py docker.sh sqlite2csv.sh ./
RUN pip3 install -r requirements.txt
VOLUME ["/scraperdata"]
WORKDIR /scraperdata
CMD ["/app/docker.sh"]
