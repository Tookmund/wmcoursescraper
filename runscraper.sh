#!/bin/sh
set -e

cd /home/scraper
wmcoursescraper/scraper.py
cd /var/www/html
find . -mtime +29 -exec rm {} \;
TODAY=$(date -I)
mv /home/scraper/courses.db "$TODAY.db"
ln -sf "$TODAY.db" courses.db
