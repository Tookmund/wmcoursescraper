#!/bin/sh
TODAY="$(date -I)"
DIR="$(dirname "$0")"
"$DIR/scraper.py"
mv courses.db "$TODAY.db"
"$DIR/sqlite2csv.sh" "$TODAY.db"
