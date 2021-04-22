#!/bin/sh
set -e

cd /home/scraper
time wmcoursescraper/scraper.py
cd /var/www/html
find . -name '*.db' -mtime +29 -exec rm {} \;
TODAY=$(date -I)
mv /home/scraper/courses.db "$TODAY.db"
chown scraper:www-data "$TODAY.db"
ln -sf "$TODAY.db" courses.db
