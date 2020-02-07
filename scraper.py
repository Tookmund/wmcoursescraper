#!/usr/bin/python3
import sys
import os
import re
import bs4
import requests
import sqlite3
import json
from datetime import datetime

session = requests.Session()
cs = session.get("https://courselist.wm.edu/courselist/")
if cs.status_code != 200:
    print("Course List", cs.status_code)
    sys.exit(1)

csp = bs4.BeautifulSoup(cs.text, 'lxml')


def selectvalues(select):
    vals = []
    for opt in select.children:
        if isinstance(opt, bs4.element.Tag):
            v = opt['value']
            if v != '0':
                vals.append(opt['value'])
    return vals

tc = csp.find(id='term_code')
termdict = {}
termdict['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
terms = []
for opt in tc.children:
    if isinstance(opt, bs4.element.Tag):
        termdict[opt['value']] = opt.string.strip()
        terms.append(opt['value'])
with open("terms.json", 'w') as f:
    json.dump(termdict, f)

subjs = []
subjc = csp.find(id='term_subj')
subjdict = {}
for opt in subjc.children:
    if isinstance(opt, bs4.element.Tag):
        v = opt['value']
        if v != '0':
            subjdict[opt['value']] = opt.string.strip()
            subjs.append(opt['value'])

coll = re.compile(r'C\d{2}.')
def parserow(row, c):
    course = ["" for i in range(17)]
    course[0] = row[0].a.string
    row[1] = row[1].string.strip()
    ident = row[1].split(" ")
    course[1] = subjdict[ident[0]]
    course[2] = row[1]
    attr = row[2].string.split(',')
    course[3] = row[2].string
    course[4] = row[3].string.strip()
    course[4] = re.sub(r'\s+', ' ', course[4])
    print(course[4])
    course[5] = row[4].string.strip()
    course[6] = row[5].string
    dt = row[6].string.split(":")
    if len(dt) == 2:
        course[7] = dt[0]
        se = dt[1].split('-')
        course[8] = se[0]
        course[9] = se[1]
    # row[7] is projected
    course[10] = row[8].string
    course[11] = row[9].string
    if course[11].endswith('*'):
        course[11] = course[11][:-1]
    if row[10].string == "OPEN":
        course[12] = 1
    else:
        course[12] = 0

    course[13], course[14], course[15], course[16]  = getreqs(term, course[0])
    v = " ?,"*len(course)
    v = v[:-1]
    sql = "INSERT INTO courses VALUES ("+v+")"
    c.execute(sql, course)

def getreqs(term, crn):
    reqs = session.get("https://courselist.wm.edu/courselist/courseinfo/addInfo?fterm="+term+"&fcrn="+crn)
    if reqs.status_code != 200:
        print(reqs.status_code)
        sys.exit(reqs.status_code)
    reqbs = bs4.BeautifulSoup(reqs.text, 'lxml')
    tr = reqbs.find_all('tr')
    if (len(tr) < 4):
        return ('', '', '', '')
    prereq = tr[3].td.string.strip()
    prereq = re.sub(r"\s+", " ", prereq)
    print(prereq)
    if (len(tr) < 6):
        return (prereq, '', '', '')
    coreq = tr[5].td.string.strip()
    coreq = re.sub(r"\s+", " ", coreq)
    print(coreq)
    if (len(tr) < 8):
        return (prereq, coreq, '', '')
    restrict = next(tr[7].strings).strip()
    restrict = re.sub(r"(:|,)(\S)", r"\1 \2", restrict)
    restrict = re.sub(r"\s+", " ", restrict)
    print(restrict)
    if (len(tr) < 13):
        return (prereq, coreq, restrict, '')
    placegen = tr[12].strings
    next(placegen)
    next(placegen)
    place = next(placegen).strip()
    place = re.sub("--|:", " ", place)
    print(place)
    return (prereq, coreq, restrict, place)

for term in terms:
    # term = terms[2]
    # finals = {}
    # finals[term] = None
    # finalreq = session.get("https://www.wm.edu/offices/registrar/calendarsandexams/examschedules/fall19exam/index.php")
    # if finalreq.status_code == 200:
    #     finals[term] = {}
    #     finalp = bs4.BeautifulSoup(finalreq.text, 'lxml')
    #     t = finalp.find(id='class').find_next('table')
    #     for r in t.find_all('tr'):

    os.rename(term+'.db', term+'.db.bak')
    db = sqlite3.connect(term+'.db')
    c = db.cursor()
    c.execute('''
            CREATE TABLE courses
            (
            CRN int,
            Subject text,
            ID  text,
            Attributes text,
            Title text,
            Instructor text,
            Credits int,
            Days text,
            Start int,
            End int,
            Enrolled int,
            Seats int,
            Status int,
            Prerequisites text,
            Corequisites text,
            Restrictions text,
            Place text
            )
            ''')

    for subj in subjs:
        r = session.get("https://courselist.wm.edu/courselist/courseinfo/searchresults?term_code="+term+"&term_subj="+subj+"&attr=0&attr2=0&levl=0&status=0&ptrm=0&search=Search")
        if r.status_code != 200:
            print(term_code, subj, r.status_code)
            sys.exit(2)
        parse = bs4.BeautifulSoup(r.text, 'lxml')
        t = parse.find('table')
        rowsize = 11
        row = []
        i = 0
        for data in t.find_all('td'):
            if i == rowsize:
                parserow(row, c)
                row = []
                i = 0
                pass
            row.append(data)
            i += 1
    db.commit()
    db.close()
