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

csurl = "https://courselist.wm.edu/courselist/"

subjurl = "https://courselist.wm.edu/courselist/courseinfo/searchresults?term_code={}&term_subj={}&attr=0&attr2=0&levl=0&status=0&ptrm=0&search=Search"

reqsurl = "https://courselist.wm.edu/courselist/courseinfo/addInfo?fterm={}&fcrn={}"

# Find COLL requirements
coll = re.compile(r'C\d{2}.')

# Remove extra whitespace
extraspace = re.compile(r"\s+")

# Clean up restrictions
cleanrestrict = re.compile(r"(:|,)(\S)")

# Clean up Place
cleanplace = re.compile(r"--|:")

def selectvalues(select):
    vals = []
    for opt in select.children:
        if isinstance(opt, bs4.element.Tag):
            v = opt['value']
            if v != '0':
                vals.append(opt['value'])
    return vals

def parserow(row):
    course = ["" for i in range(19)]
    course[0] = row[0].a.string
    row[1] = row[1].string.strip()
    ident = row[1].split(" ")
    course[1] = ident[0]
    course[2] = ident[1]
    course[3] = ident[2]
    attr = row[2].string.split(',')
    course[4] = row[2].string
    course[5] = row[3].string.strip()
    course[5] = extraspace.sub(' ', course[5])
    course[6] = row[4].string.strip()
    course[7] = row[5].string
    dt = row[6].string.split(":")
    if len(dt) == 2:
        course[8] = dt[0]
        se = dt[1].split('-')
        course[9] = se[0]
        course[10] = se[1]
    # row[7] is projected
    course[11] = row[8].string
    course[12] = row[9].string
    if course[12].endswith('*'):
        course[12] = course[12][:-1]
    if row[10].string == "OPEN":
        course[13] = 1
    else:
        course[13] = 0

    course[14], course[15], course[16], course[17], course[18]  = getreqs(term, course[0])
    print(course[0], course[5])
    return course

@sleep_and_retry
@limits(calls=120, period=30)
def getreqs(term, crn):
    r = session.get(reqsurl.format(term, crn))
    if r.status_code != 200:
        print(r.status_code)
        sys.exit(r.status_code)
    reqbs = bs4.BeautifulSoup(r.text, 'lxml')
    tr = reqbs.find_all('tr')
    reqs = ['' for x in range(5)]
    desc = tr[0].td.string.strip()
    reqs[0] = desc.split("--")[2].strip()
    if (len(tr) < 4):
        return reqs
    prereq = tr[3].td.string.strip()
    reqs[1] = extraspace.sub(" ", prereq)
    if (len(tr) < 6):
        return reqs
    coreq = tr[5].td.string.strip()
    reqs[2] = extraspace.sub(" ", coreq)
    if (len(tr) < 8):
        return reqs
    restrict = next(tr[7].strings).strip()
    restrict = cleanrestrict.sub(r"\1 \2", restrict)
    reqs[3] = extraspace.sub(" ", restrict)
    if (len(tr) < 13):
        return reqs
    placegen = tr[12].strings
    next(placegen)
    next(placegen)
    place = next(placegen).strip()
    reqs[4] = cleanplace.sub(" ", place)
    return reqs

if __name__ == "__main__":
    session = requests.Session()
    cs = session.get(csurl)
    if cs.status_code != 200:
        print("Course List", cs.status_code)
        sys.exit(1)

    csp = bs4.BeautifulSoup(cs.text, 'lxml')
    tc = csp.find(id='term_code')

    # Get all Terms
    terms = {}
    for opt in tc.children:
        if isinstance(opt, bs4.element.Tag):
            terms[opt['value']] = opt.string.strip()

    # Get all subjects
    subjc = csp.find(id='term_subj')
    subjs = {}
    for opt in subjc.children:
        if isinstance(opt, bs4.element.Tag):
            v = opt['value']
            if v != '0':
                subjs[opt['value']] = opt.string.strip()
    # Setup DB
    dbname = "courses.db"
    if os.path.exists(dbname):
        os.rename(dbname, dbname+'.bak')
    db = sqlite3.connect(dbname)
    c = db.cursor()

    c.execute("CREATE TABLE subjects (Short text, Full text)")

    # Create a table for every term
    for term in terms:
        termtable = terms[term].replace(" ", "")
        c.execute('''
                CREATE TABLE {}
                (
                CRN int,
                Subject text,
                ID  text,
                Section text,
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
                Description text,
                Prerequisites text,
                Corequisites text,
                Restrictions text,
                Place text
                )
                '''.format(termtable))

        for subj in subjs:
            c.execute("INSERT INTO subjects VALUES (?, ?)", (subj, subjs[subj]))
            r = session.get(subjurl.format(term, subj))
            if r.status_code != 200:
                print(term, subj, r.status_code)
                sys.exit(2)
            parse = bs4.BeautifulSoup(r.text, 'lxml')
            t = parse.find('table')
            rowsize = 11
            row = []
            i = 0
            for data in t.find_all('td'):
                if i == rowsize:
                    course = parserow(row)
                    v = "?,"*len(course)
                    v = v[:-1]
                    sql = "INSERT INTO {} VALUES ({})".format(termtable, v)
                    c.execute(sql, course)
                    row = []
                    i = 0
                    pass
                row.append(data)
                i += 1
        db.commit()
    db.close()
