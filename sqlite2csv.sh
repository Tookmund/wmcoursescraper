#!/bin/sh
set -e
for t in $(sqlite3 "$1" "SELECT name FROM sqlite_master where type='table';")
do

sqlite3 "$1" << EOF
.headers on
.mode csv
.output $t.csv
SELECT * FROM $t;
EOF

done
