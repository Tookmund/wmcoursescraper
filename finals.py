#!/usr/bin/env python3
import sys
import os
import re
import sqlite3
import json
from datetime import datetime

import requests
import bs4
from ratelimit import sleep_and_retry, limits


examurl = "https://www.wm.edu/offices/registrar/calendarsandexams/examschedules/"

# Assuming every class that satisfies the foreign language req is a "Modern Language"
# This is probably wrong (Latin? Greek?)
modlang = ["ARAB", "CHIN", "FREN", "GREK", "GRMN", "HBRW", "HISP", "ITAL", "JAPN", "LATN", "RUSN"]

# Remove extra whitespace
extraspace = re.compile(r"\s+")

_session = requests.Session()
@sleep_and_retry
@limits(calls=120, period=30)
def geturl(url):
    r = _session.get(url)
    if r.status_code != 200:
        print(url)
        sys.exit(r.status_code)
    return r.text

def timeparse(times):
    ret = []
    for time in times.split(" - "):
        t = time.split(":")
        h = int(t[0])
        # a/p for am/pm
        m = t[1][3]
        if m == "p" and h != 12:
            h += 12
        elif h == 12 and m == "a":
            h = 0
        ret.append(int(str(h)+t[1][:2]))
    return ret

if __name__ == "__main__":
    coursedb = sqlite3.connect("courses.db")
    course = coursedb.cursor()
    # Setup DB
    dbname = "finals.db"
    if os.path.exists(dbname):
        os.rename(dbname, dbname+'.bak')
    db = sqlite3.connect(dbname)
    c = db.cursor()
    # Get final exam schedule
    r = geturl(examurl+"index.php")
    exambs = bs4.BeautifulSoup(r, 'lxml')
    # https://stackoverflow.com/questions/22726860/beautifulsoup-webscraping-find-all-finding-exact-match
    for schda in exambs.find_all(lambda tag: tag.name == 'a' and
            tag.get('class') == ['content_button']):
        schdreq = geturl(examurl+schda['href'])
        finaltable = schda.text.replace(" ", "")+"final"
        selectstr = "SELECT CRN FROM '{}' WHERE ".format(finaltable[:-5])
        c.execute('''CREATE TABLE {}
            (
            id INTEGER PRIMARY KEY,
            start INTEGER,
            end INTEGER,
            date TEXT
            )'''.format(finaltable))
        i = 0
        schdsp = bs4.BeautifulSoup(schdreq, 'lxml')
        byclass = schdsp.find_all("table")[1]
        for tr in byclass.find_all("tr")[1:]:
            i += 1
            tds = tr("td")
            if len(tds) == 4:
                t = 2
                d = 3
            elif len(tds) == 3:
                t = 1
                d = 2
            times = timeparse(tds[t].text)
            start = times[0]
            end = times[1]
            date = tds[d].text
            c.execute("INSERT INTO {} VALUES (?, ?, ?, ?)".format(finaltable),
                    (i, start, end, date))
            if len(tds) == 4:
                days = tds[1].text.strip()
                days = days.replace(" only", "")
                days = days.replace(" or ", ",")
                days = days.split(",")
                daysselect = "AND ("
                for d in days:
                    daysselect += "(Days == '{}') OR ".format(d.strip())
                daysselect = daysselect[:-4]
                daysselect += ")"
                classtext = tds[0].text
                if "-" in classtext:
                    classtimes = timeparse(classtext)
                    selection = selectstr+"(Start BETWEEN ? AND ?) "+daysselect
                    print(selection)
                    course.execute(selection, (classtimes[0], classtimes[1]))
                else:
                    # "or later"
                    later = classtext.strip().split()
                    start = timeparse(later[0]+" "+later[1])
                    selection = selectstr+"(Start >= ?) "+daysselect
                    print(selection)
                    course.execute(selection, (start[0],))
            elif len(tds) == 3:
                cid = tds[0].text.split()
                if cid[0] == "Modern":
                    subjwhere = "("
                    for s in modlang:
                        subjwhere += "(Subject == '{}') OR ".format(s)
                    subjwhere = subjwhere[:-4]
                    subjwhere += ")"
                    idwhere = " AND ("
                    for di in cid[2:]:
                        if di[-1] == ",":
                            di = di[:-1]
                        idwhere += "(ID == {}) OR ".format(di)
                    idwhere = idwhere[:-4]
                    idwhere += ")"
                    selection = selectstr+subjwhere+idwhere
                    print(selection)
                    course.execute(selection)
                elif cid[0] == "Classes":
                        course.execute(selectstr+"(Days == '') AND (Start == '') AND (End == '')")
                elif "," in cid[1]:
                    selection = selectstr+"(Subject == '{}') AND (".format(cid[0])
                    for e in cid[1:]:
                        # Handle repetition of subject id
                        if e[:len(cid[0])] == cid[0]:
                            e = e[len(cid[0]):]
                        selection += "(ID == '{}') OR".format(e[:-1])
                    selection = selection[:-3]
                    selection += ")"
                    print(selection)
                    course.execute(selection)
                elif "/" in cid[1]:
                    s = cid[1].split("/")
                    for e in cid[1:]:
                        course.execute(selectstr+"(Subject == ?) AND (ID == ?)",
                                (cid[0], e))
                else:
                    course.execute(selectstr+"(Subject == ?) AND (ID == ?)",
                        (cid[0], cid[1]))
            for crn in course.fetchall():
                course.execute("UPDATE {} SET FinalID = ? WHERE CRN == ?".format(finaltable[:-5]), (i, crn[0]))
            coursedb.commit()
        db.commit()
