#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#  Copyright (c) 2019 KSD
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.


__version__ = "1.0.0"


import argparse
import csv
import logging
import logging.handlers
import os
import shlex
import subprocess
from pprint import pformat
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


class Mailbox:
    def __init__(self, type_: str, username: str, password: str, host: str, port: Optional[int] = None,
                 use_ssl: Optional[bool] = False):
        self.type = type_
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.use_ssl = False if use_ssl is None else use_ssl

    def __repr__(self):
        return "Mailbox({username} " \
               "on {server}:{port} " \
               "SSL={use_ssl} " \
               "type={type})".format(username=self.username, server=self.host, port=self.port, use_ssl=self.use_ssl,
                                     type=self.type)

    def __str__(self):
        return "{username} on {server}:{port} ({type})".format(username=self.username, server=self.host, port=self.port,
                                                               type=self.type)


class Migration:
    def __init__(self, old_mailbox: Mailbox, new_mailbox: Mailbox):
        self.old = old_mailbox
        self.new = new_mailbox

    def __repr__(self):
        return "{old} => {new}".format(old=self.old, new=self.new)

    def __str__(self):
        return "{old} => {new}".format(old=self.old, new=self.new)


def parse_args():
    argparser = argparse.ArgumentParser(description="Backup & restore IMAP mailboxes")
    argparser.add_argument("-c", "--csv", type=str, default="mailboxes.csv",
                           help="Path to CSV file containing mailboxes descriptions.\n"
                                "Expected CSV structure:\n"
                                "| old mailbox username | old mailbox password | old mailbox host | old mailbox port "
                                "| old mailbox ssl | new mailbox username | new mailbox password | new mailbox host "
                                "| new mailbox port | new mailbox ssl |.")
    argparser.add_argument("-l", "--listold", action="store_true", help="List folders of \"old\" mailboxes.")
    argparser.add_argument("--listnew", action="store_true", help="List folders of \"new\" mailboxes.")
    argparser.add_argument("-b", "--backup", action="store_true", help="Backup \"old\" mailboxes to files.")
    argparser.add_argument("-o", "--output", type=str, default="backups/", help="Path to store mailboxes backup files.")
    argparser.add_argument("-r", "--restore", action="store_true", help="Restore backup files to \"new\" mailboxes.")
    argparser.add_argument("-v", "--verbosity", action="count", default=0)
    argparser.add_argument("mailboxes", type=str, nargs="+", help="List of mailboxes to migrate. Mailboxes must be "
                                                                  "identified by their \"old_username\" value from the "
                                                                  "configured CSV file. Use the \"all\" keyword to "
                                                                  "migrate all mailboxes found in the configured CSV "
                                                                  "file.")

    return argparser.parse_args()


def init_logger(verbosity: int) -> logging.Logger:
    """
    Setup logger instance.

    :param verbosity: Verbosity level (between 0 and 4).
    :type verbosity: int
    :return: None
    :rtype: None
    """
    loglevel = {
        0: logging.CRITICAL,
        1: logging.ERROR,
        2: logging.WARNING,
        3: logging.INFO,
        4: logging.DEBUG
    }

    logger.setLevel(loglevel[verbosity])

    timed_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    no_timed_formatter = logging.Formatter('%(levelname)s - %(message)s')

    fh = logging.handlers.RotatingFileHandler("imap_migrator.log", 'a', 500000, 3)
    fh.setFormatter(timed_formatter)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(no_timed_formatter)
    logger.addHandler(ch)

    return logger


def parse_mailboxes_csv(csv_path: str, mailboxes_filter: List[str]) -> Iterable[Migration]:
    migrations = []

    try:
        csv_handle = open(csv_path, "r", newline="")
    except FileNotFoundError:
        logger.critical("CSV file \"{}\" not found.".format(csv_path))
        exit(1)
    except PermissionError:
        logger.critical("Access denied to CSV file \"{}\"".format(csv_path))
        exit(1)

    else:
        with csv_handle:
            csv_reader = csv.DictReader(csv_handle, fieldnames=("old_username", "old_pass", "old_host", "old_port",
                                                                "old_ssl", "new_username", "new_pass", "new_host",
                                                                "new_port", "new_ssl"),
                                        quotechar="\"", skipinitialspace=True)
            for row in csv_reader:
                # Translate use_ssl string to bool
                row["old_ssl"] = False if row["old_ssl"] is not None and row["old_ssl"].lower() == "false" else True
                row["new_ssl"] = False if row["new_ssl"] is not None and row["new_ssl"].lower() == "false" else True

                # Default ports
                if not row["old_port"]:
                    if row["old_ssl"]:
                        row["old_port"] = "993"
                    else:
                        row["old_port"] = "143"
                if not row["new_port"]:
                    if row["new_ssl"]:
                        row["new_port"] = "993"
                    else:
                        row["new_port"] = "143"

                old_mailbox = Mailbox("old", row["old_username"], row["old_pass"], row["old_host"], row["old_port"],
                                      row["old_ssl"])
                new_mailbox = Mailbox("new", row["new_username"], row["new_pass"], row["new_host"], row["new_port"],
                                      row["new_ssl"])

                if mailboxes_filter == ["all"] or old_mailbox.username in mailboxes_filter:
                    migrations.append(Migration(old_mailbox=old_mailbox, new_mailbox=new_mailbox))

    return migrations


def list_mailboxes(migrations: Iterable[Migration], type_: str) -> Iterable[Mailbox]:
    success = []
    mailboxes = (getattr(migration, type_) for migration in migrations)

    for mailbox in mailboxes:
        logger.info("Listing mailbox {}".format(mailbox.username))
        cmdl = shlex.split("imapbackup/imapgrab.py -l "
                           "-s {host} -u \"{username}\" -p \"{password}\"".format(host=mailbox.host,
                                                                                  username=mailbox.username,
                                                                                  password=mailbox.password))
        logger.debug(cmdl[:-1] + ["******"])

        return_code = subprocess.call(cmdl)

        if return_code == 0:
            success.append(mailbox)

    return success


def backup_mailboxes(migrations: Iterable[Migration], output_dir: str) -> List[Mailbox]:
    success = []
    os.makedirs(output_dir, exist_ok=True)
    mailboxes = (migration.old for migration in migrations)

    for mailbox in mailboxes:
        logger.info("Backing up mailbox {}".format(mailbox.username))

        user_output_dir = os.path.abspath(os.path.join(output_dir, mailbox.username.replace("@", "_at_")))
        try:
            os.mkdir(user_output_dir)
        except FileExistsError:
            pass

        use_ssl = "-S" if mailbox.use_ssl else ""
        cmdl = shlex.split('imapbackup/imapgrab.py -v -d {ssl} -f "{output_dir}" -s "{host}" -u "{username}" '
                           '-p "{password}" -m "_ALL_"'.format(ssl=use_ssl, output_dir=user_output_dir,
                                                               host=mailbox.host, username=mailbox.username,
                                                               password=mailbox.password))
        cmdl_without_password = cmdl.copy()
        cmdl_without_password[-3] = "******"
        logger.debug(cmdl_without_password)

        return_code = subprocess.call(cmdl)

        if return_code == 0:
            success.append(mailbox)

    return success


def restore_mailboxes(migrations: Iterable[Migration], backup_dir: str) -> List[Migration]:
    success = []

    for migration in migrations:
        if not migration.new.username or not migration.new.host:
            continue

        user_backup_dir = os.path.join(backup_dir, migration.old.username.replace("@", "_at_"))
        if not os.path.exists(user_backup_dir):
            logger.error("Could not find backup directory {}, skipping this mailbox.".format(user_backup_dir))
            continue

        logger.info("Restoring old {old} to new {new}".format(old=migration.old.username, new=migration.new.username))

        return_codes_all_ok = True
        for root, dirs, files in os.walk(user_backup_dir):
            for filename in files:
                # Restore all mboxes to their original path (ie., sub-directories in mailboxes)
                if filename.endswith(".mbox"):
                    box_file_relpath = os.path.join(root, filename)
                    box_file_abspath = os.path.abspath(box_file_relpath)
                    box_imap_path = os.path.relpath(box_file_relpath, user_backup_dir)[:-5]
                    use_ssl = "--ssl" if migration.new.use_ssl else ""

                    cmdl = shlex.split('imap_upload/imap_upload.py --retry 3 {ssl} --host "{host}" --port {port} '
                                       '--user "{username}" --password "{password}" --box "{box_path}" '
                                       '"{mbox_file}"'.format(ssl=use_ssl, host=migration.new.host,
                                                              port=migration.new.port, username=migration.new.username,
                                                              password=migration.new.password, box_path=box_imap_path,
                                                              mbox_file=box_file_abspath))
                    cmdl_without_password = cmdl.copy()
                    cmdl_without_password[-4] = "******"
                    logger.debug(cmdl_without_password)

                    return_code = subprocess.call(cmdl)
                    print(return_code)

                    if return_code != 0:
                        return_codes_all_ok = False

        if return_codes_all_ok:
            success.append(migration)

    return success


def main() -> int:
    args = parse_args()

    # Verbosity 4 is maximum
    if args.verbosity > 4:
        args.verbosity = 4

    init_logger(args.verbosity)

    migrations = parse_mailboxes_csv(args.csv, args.mailboxes)
    logger.info("Operating on following mailboxes:\n{}".format(pformat(migrations)))

    if args.listold:
        success = list_mailboxes(migrations, "old")
        logger.debug("Listing succeeded for following mailboxes:\n{}".format(pformat(success)))

    if args.listnew:
        success = list_mailboxes(migrations, "new")
        logger.debug("Listing succeeded for following mailboxes:\n{}".format(pformat(success)))

    if args.backup:
        success = backup_mailboxes(migrations, args.output)
        logger.debug("Successfully backed up following mailboxes:\n{}".format(pformat(success)))

    if args.restore:
        success = restore_mailboxes(migrations, args.output)
        logger.debug("Successfully ran following mailbox migrations:\n{}".format(pformat(success)))

    return 0


if __name__ == "__main__":
    main()
