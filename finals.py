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
            days = tds[1].text.strip()
            start = times[0]
            end = times[1]
            date = tds[d].text
            c.execute("INSERT INTO {} VALUES (?, ?, ?, ?)".format(finaltable),
                    (i, start, end, date))
            if len(tds) == 4:
                classtext = tds[0].text
                if classtext.contains("-")
                    classtimes = timeparse(classtext)
                    course.execute("SELECT CRN FROM '{}' WHERE (Start BETWEEN ? AND ?) AND (Days == ?)".format(finaltable[:-5]),
                            (classtimes[0], classtimes[1], days))
                else:
                    # "or later"
                    start = timeparse(classtext.strip.split()[0])
                    course.execute("SELECT CRN FROM '{}' WHERE (Start >= ?) AND (Days == ?)".format(finaltable[:-5]),
                            (start[0], days))
            elif len(tds) == 3:
                cid = tds[0].text.split()
                if cid[0] == "Modern":
                    #IDK What to do with this
                    pass
                elif cid[0] == "Classes":
                        course.execute("SELECT CRN FROM '{}' WHERE (Days == '') AND (Start == '') AND (End == '')".format(finaltable[:-5]))
                if "," in cid[1]:
                    for e in cid[1:]:
                        course.execute("SELECT CRN FROM '{}' WHERE (Subject == ?) AND (ID == ?)".format(finaltable[:-5]),
                                (cid[0], e[:-1]))
                elif "/" in cid[1]:
                    s = cid[1].split("/")
                    for e in cid[1:]:
                        course.execute("SELECT CRN FROM '{}' WHERE (Subject == ?) AND (ID == ?)".format(finaltable[:-5]),
                                (cid[0], e))
                else:
                    course.execute("SELECT CRN FROM '{}' WHERE (Subject == ?) AND (ID == ?)".format(finaltable[:-5]),
                        (cid[0], cid[1]))
            for crn in course.fetchall():
                course.execute("UPDATE {} SET FinalID = ? WHERE CRN == ?".format(finaltable[:-5]), (i, crn[0]))
            coursedb.commit()
        db.commit()
