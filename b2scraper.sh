#!/bin/sh
set -e

cd "$HOME/courses.db.d"
../wmcoursescraper/scraper.py
TODAY=$(date -I)
mv courses.db "$TODAY.db"
find . -name '*.db' -mtime +29 -exec rm {} \;
ln -sf "$TODAY.db" courses.db
for t in $(sqlite3 "$TODAY.db" "SELECT name FROM sqlite_master where type='table' and name != 'subjects' and name != 'semesterdates';")
do

sqlite3 "$TODAY.db" << EOF
.headers on
.mode csv
.output $t.csv
SELECT * FROM $t;
EOF

done
backblaze-b2 sync --delete . b2://wmcoursescraper
