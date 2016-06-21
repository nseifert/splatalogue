import MySQLdb as sqldb
import pandas as pd
import numpy as np
import time
from tqdm import tqdm

def initiate_sql_db():
    def rd_pass():
        return open('pass.pass').read()

    print '\nLogging into MySQL database...'

    HOST = "127.0.0.1"
    LOGIN = "nseifert"
    PASS = rd_pass()
    db = sqldb.connect(host=HOST, user=LOGIN, passwd=PASS.strip(), port=3307)
    db.autocommit(False)
    print 'MySQL Login Successful.'
    return db

if __name__ == "__main__":

    OLD_VERSION = {'tag': '2', 'main': '\"v2.0\"', 'meta': 'v2_0'}
    NEW_VERSION = {'tag': '3', 'main': '\"v3.0\"', 'meta': 'v3_0'}

    db_cur = initiate_sql_db()
    db_cur_cursor = db_cur.cursor()
    db_cur_cursor.execute("USE splat")

    db_old = initiate_sql_db()
    db_old_cursor = db_old.cursor()
    db_old_cursor.execute("USE splattest")

    # print 'Finding entries to modify...'
    # db_old_cursor.execute("SELECT DISTINCT species_id, ll_id FROM main WHERE `v2.0` = 2")
    # backup_meta_entries_raw = db_old_cursor.fetchall()
    #
    #
    # db_cur_cursor.execute("SELECT DISTINCT species_id, ll_id FROM main WHERE `v3.0` = 3")
    # cur_meta_entries = db_cur_cursor.fetchall()
    #
    # matches = []
    # new_entries = []
    # for entry in cur_meta_entries:
    #     if entry in backup_meta_entries_raw:
    #         matches.append(entry)
    #     else:
    #         new_entries.append(entry)
    #
    # # Set new entries to v3.0 only in metadata and main
    # print 'Fixing new entries...'
    # for entry in tqdm(new_entries):
    #     main_cmd = "UPDATE main SET `v2.0` = 0, `v1.0` = 0 WHERE species_id = %s AND ll_id = %s AND `v3.0` = 3"
    #     args = (entry[0], entry[1])
    #     db_cur_cursor.execute(main_cmd, args)
    #
    #     meta_cmd = "UPDATE species_metadata SET v2_0 = 0, v1_0 = 0 WHERE species_id = %s AND LineList = %s AND v3_0 = 3"
    #     db_cur_cursor.execute(meta_cmd, args)
    # print 'Finished fixing %s new entries.' %len(new_entries)
    #
    # # Set entries with backup entries to v3.0 only and readd v2.0 versions from backup db
    # print 'Readding old entries...'
    # for entry in tqdm(matches):
    #     main_cmd = "UPDATE main SET `v2.0` = 0, `v1.0` = 0 WHERE species_id = %s AND ll_id = %s AND `v3.0` = 3"
    #     meta_cmd = "UPDATE species_metadata SET v2_0 = 0, v1_0 = 0 WHERE species_id = %s AND LineList = %s AND v3_0 = 3"
    #     args = (entry[0], entry[1])
    #     db_cur_cursor.execute(main_cmd, args)
    #     db_cur_cursor.execute(meta_cmd, args)
    #
    #     # Copy old linelist over to current table
    #     append_cmd = "INSERT IGNORE INTO splat.main SELECT * FROM splattest.main WHERE species_id = %s and ll_id = %s and `v2.0` = 2"
    #     db_old_cursor.execute(append_cmd, args)
    #
    #     # Copy old metadata over to current table
    #     meta_append = "INSERT IGNORE INTO splat.species_metadata SELECT * FROM splattest.species_metadata WHERE species_id = %s and LineList = %s AND v2_0 = 2"
    #     db_cur_cursor.execute(meta_append, args)
    #
    # print 'Finished reappending old versions of and correcting %s entries.' %len(matches)

    print 'Setting data without new versions to appear in current version search.'
    # Set all other entries in main to 3 and 2 so they show up in any version 3 search
    # db_cur_cursor.execute("SELECT DISTINCT species_id, ll_id FROM main WHERE `v3.0` != 3 AND (`v2.0` = 2 OR `v1.0` = 1)")
    # leftovers = db_cur_cursor.fetchall()
    #
    # for entry in tqdm(leftovers):
    #     args = (entry[0], entry[1])
    #     cmd = "UPDATE main SET `v3.0` = 3, `v2.0` = 2, `v1.0` = 1 WHERE species_id = %s AND ll_id = %s AND `v3.0` != 3"
    #     db_cur_cursor.execute(cmd, args)
    #
    #     meta_cmd = "UPDATE species_metadata SET v3_0 = 3, v2_0 = 2, v2_0 = 1 WHERE species_id = %s AND LineList = %s and v3_0 != 3"
    #     db_cur_cursor.execute(meta_cmd, args)
    #
    # print 'Done.'

    db_cur_cursor.execute("SELECT DISTINCT species_id, ll_id FROM main WHERE `v3.0` = 3 AND (`v2.0` != 0 or `v1.0` != 0)")
    old_entries = db_cur_cursor.fetchall()

    db_cur_cursor.execute("SELECT DISTINCT species_id, ll_id FROM main WHERE `v3.0` = 3 AND (`v2.0` = 0 or `v1.0` = 0)")
    new_entries = db_cur_cursor.fetchall()

    for entry in tqdm(new_entries):
        if entry in old_entries:
            args = (entry[0], entry[1])
            cmd = "UPDATE main SET `v3.0` = 0 WHERE species_id = %s AND ll_id = %s " \
                  "AND `v3.0` = 3 AND (`v2.0` != 0 or `v1.0` != 0)"
            db_cur_cursor.execute(cmd, args)

            cmd = "UPDATE species_metadata SET v3_0 = 0 WHERE species_id = %s AND LineList = %s " \
                  "AND v3_0 = 3 AND (v2_0 != 0 or v1_0 != 0)"
            db_cur_cursor.execute(cmd, args)




