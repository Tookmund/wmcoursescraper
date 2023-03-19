#!/bin/bash
set -e

cd "$HOME/courses.db.d"
time ../wmcoursescraper/venv/bin/python3 ../wmcoursescraper/scraper.py
TODAY=$(date -I)
mv courses.db "$TODAY.db"
find . -name '*.db' -mtime +90 -exec rm {} \;
ln -sf "$TODAY.db" courses.db
../wmcoursescraper/sqlite2csv.sh "$TODAY.db"
time backblaze-b2 sync --noProgress --delete . b2://wmcoursescraper
