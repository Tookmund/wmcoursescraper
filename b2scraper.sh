#!/bin/sh
set -e

cd "$HOME/courses.db.d" 
../wmcoursescraper/scraper.py
TODAY=$(date -I)
mv courses.db "$TODAY.db"
find . -name '*.db' -mtime +29 -exec rm {} \;
ln -sf "$TODAY.db" courses.db
backblaze-b2 sync --delete . b2://wmcoursescraper
