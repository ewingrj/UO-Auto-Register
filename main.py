__author__ = 'rjewing'

import requests
from BeautifulSoup import BeautifulSoup
from email.mime.text import MIMEText
import smtplib
import os
import time

# key is new crn, value is crn to drop
DROP_CRNS = {}

TERM_IN = 201302
ID = os.environ['UO_ID']
PASS = os.environ['DUCKWEB_PASS']
SEND_TO = os.environ['GMAIL']

LOGIN_POST_URL = "https://duckweb.uoregon.edu/pls/prod/twbkwbis.P_ValLogin"
LOGIN_URL = "https://duckweb.uoregon.edu/pls/prod/twbkwbis.P_WWWLogin"
TERM_POST_URL = "https://duckweb.uoregon.edu/pls/prod/bwskfreg.P_AltPin"
REGISTRATION_POST_URL = "https://duckweb.uoregon.edu/pls/prod/bwckcoms.P_Regs"

CRN_URL_TEMPLATE = "http://classes.uoregon.edu/pls/prod/hwskdhnt.p_viewdetl?term=201302&crn={}"

CRNS_FILE = "/Users/rjewing/PycharmProjects/uo_class_signup/crns.txt"


def login(session):
    login_data = {'sid': ID, 'PIN': PASS}

    session.get(LOGIN_URL)
    r = session.post(LOGIN_POST_URL, params=login_data)

    # if login failed for some reason, send email with failure page in body
    if r.status_code != 200 or 'Authorization Failure' in r.text:
        subject = 'UO Login Failure'
        send_email(subject, r.text.encode('utf-8'))
        return False

    return True

def register_waitlist(session, response, post_params):
    #post_params = parse_post_data(response.text)
    return False

def register(session, open_crns):
    term_data = {'term_in': TERM_IN}

    r = session.post(TERM_POST_URL, params=term_data)

    # get the data we need to send along with our POST request
    post_data = parse_post_data(r.text, open_crns)
    r = session.post(REGISTRATION_POST_URL, params=post_data)

    if not 'Registration Add Errors' in r.text:
        # if DuckWeb is down, don't do anythin
        if 'DuckWeb is currently unavailable' in r.text:
            return False
        else:
            return r
    # if registration error, send email with the registration webpage content
    # in the body
    else:
        send_email('Registration Error', r.text.encode('utf-8'))
        return False

def parse_post_data(page, open_crns):
    soup = BeautifulSoup(page)
    inputs = soup.findAll(['input', 'select'])
    post_data = ""
    i = 0

    # The registration page is a mess of a form, need to submit every input with
    # POST, even unused inputs

    for input in inputs:
        # need to include RSTS_IN= in post_data so we can drop classes if needed
        if input.name == 'select':
            post_data = post_data + '&RSTS_IN='

        elif input.get('type') == 'text' or input.get('type') == 'hidden':

            # If first input, don't include '&' at begining
            if input == inputs[0]:
                post_data = post_data + '{}={}'.format(input['name'],
                                                       input.get('value'), '')

            else:
                # The CRN_IN's without a value is where we add the crn for the
                # class we want to add
                if input['name'] == 'CRN_IN' and not input.get('value'):

                    if open_crns and i < len(open_crns):
                        post_data = post_data + '&{}={}'.format(input['name'],
                                                                open_crns[i])

                        #drop class if needed
                        if open_crns[i] in DROP_CRNS:
                            post_data = post_data.replace('RSTS_IN=&assoc_term_in={}&CRN_IN={}'.format(TERM_IN, DROP_CRNS[open_crns[i]]),
                                                          'RSTS_IN=DC&assoc_term_in={}&CRN_IN={}'.format(TERM_IN, DROP_CRNS[open_crns[i]]))

                        i = i + 1
                    else:
                        post_data = post_data + '&{}='.format(input['name'])

                # Everything else, just copy the input name and value
                else:
                    post_data = post_data + '&{}={}'.format(input['name'],
                                                            input.get('value'))

    post_data = post_data + '&REG_BTN=Submit+Changes'

    return post_data

def fetch_crns():
    """crn's are written one per line in the file"""
    crns = []
    with open(CRNS_FILE, 'r') as f:
        contents = f.readlines()

    for l in contents:
        crns.append(l.rstrip('\n'))
    return crns

def write_crns(crns):
    """write the crns to file 1 per line"""
    with open(CRNS_FILE, 'w') as f:
        f.write('\n'.join(i for i in crns))

def send_email(subject, body):
    msg = MIMEText(body, 'html')

    msg['Subject'] = subject
    msg['From'] = os.environ['GMAIL']
    msg['To'] = SEND_TO

    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login(os.environ['GMAIL'], os.environ['GMAIL_PASS'])
    s.sendmail(os.environ['GMAIL'], SEND_TO, msg.as_string())
    s.quit()

def check_class_open(crns):
    open_crns = []

    for crn in crns:
        url = CRN_URL_TEMPLATE.format(crn)

        r = requests.get(url)

        soup = BeautifulSoup(r.text)
        # find available table column from the given attrs. the first returned is the available seats, the 2nd returned is the max seats
        available = soup.fetch(attrs={'class': 'dddefault', 'width': 30})[0]

        if available.text != u'0':
            open_crns.append(crn)

    return open_crns

def main():
    crns = fetch_crns()
    open_crns = check_class_open(crns)
    s = requests.Session()

    if open_crns and login(s):
        response = register(s, open_crns)
        if response:
            for crn in open_crns:
                crns.remove(crn)

            write_crns(crns)
            subject = "You've Added Classes"
            send_email(subject, response.text.encode('utf-8'))

    time.sleep(10)

if __name__ == '__main__':
    main()