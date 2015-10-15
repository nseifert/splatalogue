__author__ = 'nseifert'
""" MySQL connection/interfacing test """
import MySQLdb as sqldb
import pandas as pd


def rd_pass():
    return open('pass.txt').read()

def parse_table_main(res):
    i = 0
    print print

if __name__ == "__main__":

    HOST = "sql.cv.nrao.edu"
    LOGIN = "nseifert"
    PASS = rd_pass()

    db = sqldb.connect(host=HOST, user=LOGIN, passwd=PASS)

    cursor = db.cursor()

    cursor.execute("SHOW DATABASES")
    cursor.execute("USE splat")

    cmd = "SELECT * FROM main " \
          "WHERE species_id=194 AND " \
          "frequency < 100000.0"

    cursor.execute(cmd)

    parse_table_main(cursor.fetchall())


    db.close()