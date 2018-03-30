# pg_event_notifier
The utility checks event messages in the most recent PostgreSQL server log file (reads row by row using memory safely), shows output
and sends mail notification if events has been found.

Author: Andrey Klychkov (aaklychkov@mail.ru)

Version: 1.2

Date: 2018-03-16

Licence: Copyleft free software

Maximum event limit for a check: 10 000 000 (you may change it by using the EVENTS_LIMIT constant)

Tested on a server with 4 GB RAM by using a 20GB log file with 18158289 events, EVENTS_LIMIT had been temporarily increased to 100 000 000


**IMPORTANT:** log file name must consist of an YYYY-MM-DD string as a variable part of
its name and be in the csv format.
The actual log file must consist of the current date as a part of its name respectively.

You may use the following postgresql.conf params for the requirements above:
```
log_destination = 'csvlog'
log_directory = 'pg_log'
log_truncate_on_rotation = 'on'
log_rotation_age = '1d'
log_filename = '%Y-%m-%d.somesrv.log'
```

The following values MUST be passed to the utility:

1) Path to a PostgreSQL server log dir (-d PATH).

2) Persistent part of a log file name (-s SUFFIX).

The following values MAY be passed:

3) Continue a check from the last log file offset (-c). By default starts from the beginning
of a log file.

4) Event threshold counter (-t THRESHOLD), default 0. It's a minimal difference between
a number of events gotten after the last and current check. If you desire to get
a notification about events, even though you've gotten it early, set it up to 0 or don't pass it at all.
For example, if you want to get notification only if a number of events increase
after the previous check on 1000, set it up to 1000.

5) Max num of attempts (-r NUM) after which a counter of events and attempts will
be reseted. When a new day will start, it will be reseted automatically.

6) Event level (-l {WARN|ERR|FATAL|PANIC}). For example, if you'll pass ERR, the
utility will count events with all levels except WARNING.

7) Allow notifications (-m), disabled by default.
Important: you must set up desired mail server connection parameters in the section
"Mail notification params" in the header of the utility

8) Show output to a console (-v), disabled by default.

9) Pattern(s) for filtering (-f "PATTERN(,PATTERN1,PATTERN2)"). If you pass a desired pattern(s), utility won't count rows with it.


Output and notification format:
```
LVL, [ip]:dbname:username: "Event message": counter
```
For example:
```
-Started from the last offset of the log file-

FATAL, [local]:testdb: user1: "database ""test"" does not exist" : 13
ERROR, [local]:testdb: user2: "cannot execute ALTER TABLE in a read-only transaction" : 6

filter: test_event, duplicate key
-------
diff with last check: 19
```

### Requirements:

python3+

### Synopsis:
```
pg_event_notifier.py [-h] [-v] [-c] -d PATH -s SUFFIX [-t THRESHOLD] [-r NUM] [-l LVL] [-m] [-f PATTERN]
```
**Options**
```
optional arguments:
  -h, --help            show this help message and exit
  -c, --continue        continue parsing from the last offset
  -d PATH, --log-dir PATH
                        path to a Postgresql log dir
  -v, --verbose         print output
  -s SUFFIX, --log-suffix SUFFIX
                        persistent part of a log file name
  -t THRESHOLD, --threshold THRESHOLD
                        event threshold
  -r NUM, --reset-after NUM
                        max num of checks before a tmp file will be cleared
  -l LVL, --level LVL   event level {WARN|ERR|FATAL|PANIC}
  -f PATTERN, --filter PATTERN
                        filter pattern(s comma separated)
  -m, --mail		allow mail notifications (disabled by default)
                        important: you must set up desired mail server
                        connection parameters in the section "Mail
                        notification params" in the header of the utility
```

### Examples:
Start parsing from the last log file offset and show all events to a console without a notification:
```
./pg_event_notifier.py -v -d /var/lib/pgsql/9.6/data/pg_log -s .somesrv.csv -t 0 -c
```
Check from the last offset and send a notification about events with the ERROR/FATAL/PANIC level, if
a difference between the previous number of events and the current number is more than 1000:
```
./pg_event_notifier.py -d /var/lib/pgsql/9.6/data/pg_log -s .somesrv.csv -t 1000 -m -c -l ERR
```
The same as above but doesn't count rows that content the 'test_event' and 'duplicate key' patterns:
```
./pg_event_notifier.py -d /var/lib/pgsql/9.6/data/pg_log -s .somesrv.csv -t 1000 -m -c -l ERR -f "test_event,duplicate key"
```
