# Description
IMAP Migrator allows you to migrate a set of mailboxes from one server to another.
Taking place at the IMAP level, it is therefore agnostic of upper layers like which webmail
(and/or desktop client) you use.

# Quickstart
* Clone this repository somewhere on your computer : `git clone https://github.com/ksd-fr/IMAP-Migrator`
* `cd` into the repository.
* Copy `example_mailboxes.csv` to `mailboxes.csv` and fill in `mailboxes.csv` properly.
* Run `./imap_migrator.py`

# Usage
```
usage: imap_migrator.py [-h] [-c CSV] [-l] [--listnew] [-b] [-o OUTPUT] [-r]
                        [-v]
                        mailboxes [mailboxes ...]

Backup & restore IMAP mailboxes

positional arguments:
  mailboxes             List of mailboxes to migrate. Mailboxes must be
                        identified by their "old_username" value from the
                        configured CSV file. Use the "all" keyword to migrate
                        all mailboxes found in the configured CSV file.

optional arguments:
  -h, --help            show this help message and exit
  -c CSV, --csv CSV     Path to CSV file containing mailboxes descriptions.
                        Expected CSV structure: | old mailbox username | old
                        mailbox password | old mailbox host | old mailbox port
                        | old mailbox ssl | new mailbox username | new mailbox
                        password | new mailbox host | new mailbox port | new
                        mailbox ssl |.
  -l, --listold         List folders of "old" mailboxes.
  --listnew             List folders of "new" mailboxes.
  -b, --backup          Backup "old" mailboxes to files.
  -o OUTPUT, --output OUTPUT
                        Path to store mailboxes backup files.
  -r, --restore         Restore backup files to "new" mailboxes.
  -v, --verbosity
```

# Requirements


# Credits
IMAP Migrator is a simple glue script that actually relies on two other tools available
on Github:

* https://github.com/ralbear/IMAPbackup
* https://github.com/rgladwell/imap-upload

Both scripts were updated to Python 3 and some bugs/limitations were fixed.

IMAP Migrator also uses a small IMAP UTF-7 codec which can be found on Github:

* https://github.com/MarechJ/py3_imap_utf7