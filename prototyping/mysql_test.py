__author__ = 'nseifert'
""" MySQL connection/interfacing test """
import MySQLdb as sqldb
import pandas as pd


def rd_pass():
    return open('pass.pass').read()


def get_main_cols():
    cols_dict = {}
    list = open("main_columns.csv").read().split('\n')
    for entry in list:
        try:
            splitted = entry.strip().split(',')
            cols_dict[splitted[0]] = splitted[1]
        except IndexError:
            continue

    return cols_dict


def parse_table_main(res, cols=get_main_cols()):

    struct = {}

    for col_key in cols:
        struct[cols[col_key]] = pd.Series([row[int(col_key)] for row in res])

    column_keys = sorted([int(key) for key in cols.keys()])

    return pd.DataFrame(struct, columns=[cols[str(i)] for i in column_keys])


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

    listing = parse_table_main(cursor.fetchall())

    listing.to_excel('test.xlsx', sheet_name="Output test")

    db.close()
