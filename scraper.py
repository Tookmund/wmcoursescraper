#!/usr/bin/env python3
import sys
import os
import re
import sqlite3
import json
from datetime import datetime

import requests

from requests.adapters import HTTPAdapter, Retry
import bs4
from ratelimit import sleep_and_retry, limits

csurl = "https://courselist.wm.edu/courselist/"

subjurl = "https://courselist.wm.edu/courselist/courseinfo/searchresults?term_code={}&term_subj={}&attr=0&attr2=0&levl=0&status=0&ptrm=0&search=Search"

reqsurl = "https://courselist.wm.edu/courselist/courseinfo/addInfo?fterm={}&fcrn={}"

examurl = "https://www.wm.edu/offices/registrar/calendarsandexams/examschedules/"

calendarurl = "https://www.wm.edu/offices/registrar/calendarsandexams/ugcalendars/index.php"

# Assuming every class that satisfies the foreign language req is a "Modern Language"
# This is probably wrong (Latin? Greek?)
modlang = ["ARAB", "CHIN", "FREN", "GREK", "GRMN", "HBRW", "HISP", "ITAL", "JAPN", "LATN", "RUSN"]

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

_session = requests.Session()

_retries = Retry(total=30, backoff_factor=60)
_session.mount("https://", HTTPAdapter(max_retries=_retries))


@sleep_and_retry
@limits(calls=60, period=120)
def geturl(url):
    r = _session.get(url)
    if r.status_code != 200:
        print(r.status_code, url)
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

def parserow(row):
    course = ["" for i in range(20)]
    course[19] = 0
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

    course[14], course[15], course[16], course[17], course[18] = getreqs(term, course[0])
    if sys.stdout.isatty():
        print(course[0], course[5])
    return course

def getreqs(term, crn):
    r = geturl(reqsurl.format(term, crn))
    reqbs = bs4.BeautifulSoup(r, 'lxml')
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


# Datetime strings in ISO 8601 with timezone
def currentutc():
    return datetime.utcnow().isoformat()+"Z"

if __name__ == "__main__":
    cs = geturl(csurl)
    csp = bs4.BeautifulSoup(cs, 'lxml')
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
    c.execute("CREATE TABLE semesters (ID int, Name text, Start text, End text)")
    c.execute('''
        CREATE TABLE courses
        (
        CRN int,
        Semester int,
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
        Place text,
        Final int
	)
	''')
    c.execute('''CREATE TABLE finals
        (
        id INTEGER PRIMARY KEY,
        start INTEGER,
        end INTEGER,
        date TEXT
        )''')
    c.execute("CREATE TABLE runtime (start TEXT, end TEXT)")

    # Start your engines!
    c.execute("INSERT INTO runtime (start) VALUES (?)", (currentutc(),))

    # Find dates of course start and end
    tdr = geturl(calendarurl)
    tdp = bs4.BeautifulSoup(tdr, 'lxml')

    def finddateheaders(tag):
        if tag.name in ["h5", "h6"]:
            a = tag.find("a")
            if a is not None and a.has_attr("id"):
                if a['id'] in ("fall", "spring", "summer"):
                    return True
        return False

    dateheaders = tdp.find_all(finddateheaders)
    for term in terms:
        for header in dateheaders:
            if header.contents[1] == terms[term]:
                table = header.findNextSibling("table")
                startelem = table.find(text="First day of classes")
                start = ""
                if startelem is not None:
                    for p in startelem.parents:
                        if p.name == "tr":
                            start = p.td.string
                            break
                endelem = table.find(text="Last day of classes")
                end = ""
                if endelem is not None:
                    for p in endelem.parents:
                        if p.name == "tr":
                            end = p.td.string
                            break
                c.execute("INSERT INTO semesters VALUES (?,?,?,?)",
                    (term, terms[term], start, end))

        for subj in subjs:
            print(subj)
            c.execute("INSERT INTO subjects VALUES (?, ?)", (subj, subjs[subj]))
            r = geturl(subjurl.format(term, subj))
            parse = bs4.BeautifulSoup(r, 'lxml')
            t = parse.find('table')
            rowsize = 11
            row = []
            i = 0
            for data in t.find_all('td'):
                if i == rowsize:
                    course = parserow(row)
                    v = "?,{},".format(term)
                    v += "?,"*(len(course)-1)
                    v = v[:-1]
                    sql = "INSERT INTO courses VALUES ({})".format(v)
                    c.execute(sql, course)
                    row = []
                    i = 0
                    pass
                row.append(data)
                i += 1
            db.commit()
    # Get final exam schedule
    r = geturl(examurl)
    exambs = bs4.BeautifulSoup(r, 'lxml')
    # https://stackoverflow.com/questions/22726860/beautifulsoup-webscraping-find-all-finding-exact-match
    i = 0
    for schda in exambs.find_all(lambda tag: tag.name == 'a' and
            tag.parent.get('class') == ['content_button']):
        schdreq = geturl(examurl+schda['href'])
        selectstr = "SELECT CRN FROM courses WHERE "
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
            c.execute("INSERT INTO finals VALUES (?, ?, ?, ?)",
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
                    c.execute(selection, (classtimes[0], classtimes[1]))
                else:
                    # "or later"
                    later = classtext.strip().split()
                    start = timeparse(later[0]+" "+later[1])
                    selection = selectstr+"(Start >= ?) "+daysselect
                    c.execute(selection, (start[0],))
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
                    c.execute(selection)
                elif cid[0] == "Classes":
                    c.execute(selectstr+"(Days == '') AND (Start == '') AND (End == '')")
                elif "," in cid[1]:
                    selection = selectstr+"(Subject == '{}') AND (".format(cid[0])
                    for e in cid[1:]:
                        # Handle repetition of subject id
                        if e[:len(cid[0])] == cid[0]:
                            e = e[len(cid[0]):]
                        selection += "(ID == '{}') OR ".format(e[:-1])
                    selection = selection[:-4]
                    selection += ")"
                    c.execute(selection)
                elif "/" in cid[1]:
                    s = cid[1].split("/")
                    for e in cid[1:]:
                        c.execute(selectstr+"(Subject == ?) AND (ID == ?)",
                                (cid[0], e))
                else:
                    c.execute(selectstr+"(Subject == ?) AND (ID == ?)",
                        (cid[0], cid[1]))
            for crn in c.fetchall():
                c.execute("UPDATE courses SET Final = ? WHERE CRN == ?", (i, crn[0]))
        db.commit()
    c.execute("UPDATE runtime SET end = ?", (currentutc(),))
    db.commit()
    db.close()
