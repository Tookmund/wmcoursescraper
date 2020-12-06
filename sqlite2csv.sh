#!/bin/sh
set -eu

for ID in $(sqlite3 "$1" "SELECT ID FROM semesters;")
do

NAME=$(sqlite3 "$1" "SELECT Name FROM semesters WHERE ID == $ID" | tr -d ' ')

sqlite3 "$1" << EOF
.headers on
.mode csv
.output "$NAME.csv"
SELECT * FROM courses where Semester = $ID
EOF

done
