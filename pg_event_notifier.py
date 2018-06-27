#!/usr/bin/python3
# Name: pg_event_notifier.py
# Author: Andrey Klychkov (aaklychkov@mail.ru)
# Version: 1.2
# Licence: Copyleft free software
# Date: 2018-03-16
#
# **IMPORTANT** Log files must consist of an YYYY-MM-DD string
# as a variable part of its names and be in the csv format.
# The actual log file must consist of the current date as
# a part of its name respectively.
#
# You may use the following postgresql.conf params
# for the requirements above:
#   log_destination = 'csvlog'
#   log_directory = 'pg_log'
#   log_truncate_on_rotation = 'on'
#   log_rotation_age = '1d'
#   log_filename = '%Y-%m-%d.somesrv.log'
#
# See README file on the https://github.com/Andersson007
# for more information.

import argparse
import datetime
import os
import re
import smtplib
import socket
import sys

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

##################################
#    Mail notification params    #
##################################
HOSTNAME = socket.gethostname()
SEND_MAIL = False
SENDER = 'report.mycompany@gmail.com'
RECIPIENT = ['andrey.klychkov@ediweb.com', 'stanislav.vdovin@ediweb.com']
SMTP_SRV = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_PASS = 'MyPassHere'
MAIL_SBJ = '%s: Too many errors in the database' % HOSTNAME

###########################################
#    Parsing of command-line arguments    #
###########################################
descr = "Checks of PostgreSQL warning messages and " \
    "sends mail notifications"
parser = argparse.ArgumentParser(description=descr)
parser.add_argument("-d", "--log-dir", dest="LOG_DIR", required=True,
                    help="path to a Postgresql log dir", metavar="PATH")
parser.add_argument("-v", "--verbose", dest="VERB", action='store_true',
                    help="print output")
parser.add_argument("-c", "--continue", dest="CONTIN", action='store_true',
                    help="continue parsing from the last offset")
parser.add_argument("-f", "--filter", dest="FILTER",
                    metavar="PATTERN",
                    help="filter pattern(s comma separated)")
parser.add_argument("-s", "--log-suffix", dest="LOG_SUFFIX",
                    metavar="SUFFIX", required=True,
                    help="persistent part of a log file name")
parser.add_argument("-t", "--threshold", dest="THRESHOLD",
                    help="event threshold",
                    metavar="THRESHOLD")
parser.add_argument("-r", "--reset-after", dest="RESET_AFTER",
                    help="max num of checks before a tmp file will be cleared",
                    metavar="NUM")
levels = ['WARN', 'ERR', 'FATAL', 'PANIC']
parser.add_argument("-l", "--level", dest="LEVEL",
                    help="event level {WARN|ERR|FATAL|PANIC}",
                    choices=['WARN', 'ERR', 'FATAL', 'PANIC'],
                    metavar="LVL")
descr_mail = "allow mail notifications (disabled by defauld)\n" \
    "important: you must set up desired mail server\n" \
    "connection parameters in the section\n" \
    '"Mail notification params" in the header of the utility'
parser.add_argument("-m", "--mail", dest="SEND_MAIL", action='store_true',
                    help=descr_mail)

args = parser.parse_args()


#######################
#    Common params    #
#######################
TMP_FILE = '/tmp/pg_event_notifier.tmp'
EVENTS_LIMIT = 10000000
NOW = datetime.datetime.now()
F_TIME = NOW.strftime('%Y-%m-%d')
LOG_PATH = args.LOG_DIR+'/'+F_TIME+args.LOG_SUFFIX
if args.SEND_MAIL:
    SEND_MAIL = True

if not args.THRESHOLD:
    args.THRESHOLD = 0

if not args.RESET_AFTER:
    args.RESET_AFTER = 1000000


###############################
#    FUNCTIONS AND CLASSES    #
###############################
def send_mail(sbj, ms):
    if SEND_MAIL:
        msg = MIMEMultipart()
        msg['Subject'] = (sbj)
        msg['From'] = 'root@%s' % HOSTNAME
        msg['To'] = RECIPIENT[0]
        body = MIMEText(ms, 'plain')
        msg.attach(body)
        smtpconnect = smtplib.SMTP(SMTP_SRV, SMTP_PORT)
        smtpconnect.starttls()
        smtpconnect.login(SENDER, SMTP_PASS)
        smtpconnect.sendmail(SENDER, RECIPIENT, msg.as_string())
        smtpconnect.quit()
    else:
        pass


######################
#   MAIN FUNCTION    #
######################
if __name__ == '__main__':

    #
    # Check passed paths
    #
    if not os.path.isdir(args.LOG_DIR):
        print('Error, %s does not exist' % args.LOG_DIR)
        sys.exit(1)

    if not os.path.isfile(LOG_PATH):
        print('Error, %s does not exits' % LOG_PATH)
        sys.exit(1)

    # If a tmp file does not exist
    # or it's empty, create it or
    # write to it basic values (0,0) of the last
    # event num and an attemt's
    # counter respectively:
    if os.path.isfile(TMP_FILE):
        if not os.stat(TMP_FILE).st_size:
            f = open(TMP_FILE, 'w')
            f.write('0,0,%s,0' % F_TIME)
            f.close()
    else:
        f = open(TMP_FILE, 'w')
        f.write('0,0,%s,0' % F_TIME)
        f.close()

    # Get the last num of events and
    # an attempt counter from a tmp file:
    for line in open(TMP_FILE, 'r'):
        t = line.split(',')
        last_err_num = int(t[0])
        attempts = int(t[1])
        date = t[2]
        last_offset = int(t[3])
        break

    if not args.CONTIN:
        last_offset = 0

    # Declare dicts for storing events:
    FATAL = {}
    ERROR = {}
    WARN = {}
    PANIC = {}
    event_counter = 0

    #
    # Determine event level
    #
    if args.LEVEL == 'ERR':
        regexp = ',ERROR,|,FATAL,|,PANIC,'

    elif args.LEVEL == 'FATAL':
        regexp = ',FATAL,|,PANIC,'

    elif args.LEVEL == 'PANIC':
        regexp = ',PANIC,'
    else:
        regexp = ',ERROR,|,WARNING,|,FATAL,|,PANIC,'

    events = re.compile(regexp)

    #
    # Parse a log file.
    # Fill event dicts for suitable events
    #
    f = open(LOG_PATH, 'r')
    f.seek(last_offset, 0)

    if args.FILTER:
        t = args.FILTER.split(',')
        filters = re.compile('|'.join(t))
    else:
        filters = 0

    for line in f:
        if event_counter > EVENTS_LIMIT:
            break

        if filters:
            if filters.search(line):
                continue

        if events.search(line):
            out = line.split(',')
            level = out[11]
            msg = out[13]
            host = out[4].strip('"')
            user = out[1].strip('"')
            db = out[2].strip('"')
            text = '%s:%s:%s: %s' % (
                host.split(":")[0], db, user, msg)
 

            if level == 'ERROR':
                if text in ERROR:
                    ERROR[text] += 1
                else:
                    ERROR[text] = 1

            elif level == 'WARNING':
                if text in WARN:
                    WARN[text] += 1
                else:
                    WARN[text] = 1

            elif level == 'FATAL':
                if text in FATAL:
                    FATAL[text] += 1
                else:
                    FATAL[text] = 1

            elif level == 'PANIC':
                if text in PANIC:
                    PANIC[text] += 1
                else:
                    PANIC[text] = 1

            event_counter += 1

    offset = f.tell()
    f.close()

    # If new day has come, reset a tmp file
    # because a new log file will be parsed:
    if date != F_TIME:
        f = open(TMP_FILE, 'w')
        f.write('0,0,%s,0' % F_TIME)
        f.close()
        last_err_num = 0
        attempts = 0

    if not event_counter:
        sys.exit(0)

    #
    # Compute the difference between the previous
    # number of events and the current number of it.
    # If it's less then the value of the passed
    # threshold '-t NUM', just exit
    #
    if args.CONTIN:
        event_counter += last_err_num

    err_diff = event_counter - last_err_num
    if err_diff < int(args.THRESHOLD):
        sys.exit(0)

    #
    # Generating a mail report:
    #
    report = []

    if args.CONTIN:
        report.append(
            "-Started from the last offset of the log file-\n")

    if PANIC:
        report.append('\n'.join(
            ['PANIC, %s : %s' % (k, v) for k, v in PANIC.items()]))

    if FATAL:
        report.append('\n'.join(
            ['FATAL, %s : %s' % (k, v) for k, v in FATAL.items()]))

    if ERROR:
        report.append('\n'.join(
            ['ERROR, %s : %s' % (k, v) for k, v in ERROR.items()]))

    if WARN:
        report.append('\n'.join(
            ['WARN, %s : %s' % (k, v) for k, v in WARN.items()]))

    if filters:
        report.append('\nfilter: '+', '.join(t))

    report.append('\n-------\ndiff with last check: %s' % err_diff)

    send_mail(MAIL_SBJ, '\n'.join(report))

    #
    # Print output if needed
    #
    if args.VERB:
        for i in report:
            print(i)

    #
    # Write event counter and a number of attempts
    # to a tmp file.
    #
    f = open(TMP_FILE, 'w')
    # if a number of attempts is less than
    # the passed -r NUM param:
    if attempts < int(args.RESET_AFTER):
        # Compute the current attempt number
        # and write it with the event counter to the tmp file:
        current_attempt = attempts + 1
        s = '%s,%s,' % (str(event_counter), str(current_attempt))
        s += '%s,%s' % (F_TIME, str(offset))
        f.write(s)
    else:
        # reset the event counter and
        # the number of attempts:
        f.write('0,0,%s,%s' % (F_TIME, str(offset)))

    f.close()

    sys.exit(0)
