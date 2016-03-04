import pandas as pd
import MySQLdb as mysqldb
from MySQLdb import cursors
from tqdm import tqdm

def init_sql_db():
    def rd_pass():
        return open('pass.pass').read()

    HOST = "127.0.0.1"
    LOGIN = "nseifert"
    PASS = rd_pass()
    db = mysqldb.connect(host=HOST, user=LOGIN, passwd=PASS.strip(), port=3307, cursorclass = cursors.SSCursor)
    db.autocommit(False)
    print 'MySQL Login Successful.'

    return db

def read_vizier_file(inp, fmt, delimiter):

    # Construct linelist result dictionary
    linelist = {}
    for key in fmt:
        linelist[key] = []

    atLineList = False

    for line in inp:

        if not line.strip():  # Blank line
            continue

        if line[0] == "#":  # Comment
            continue

        if '--' in line:  # Last line before linelist starts
            atLineList = True
            continue

        if atLineList:
            try:
                for i, key in enumerate(fmt):
                    linelist[key].append(line.strip().split(delimiter)[i])
            except IndexError:
                print "\"" + line + "\""
                raise

    linelist['Freq'] = [float(x) for x in linelist['Freq']]  # Convert from str to float
    
    return pd.DataFrame.from_dict(linelist)




if __name__ == "__main__":

    path = "/home/nate/Downloads/asu.tsv"
    fmt = ['El', 'qNu', 'qNl', 'Freq']
    TOLERANCE = 1.0  # In units of linelist frequency, typically MHz.

    astro_ll = read_vizier_file(open(path, 'r'), fmt, '\t')
    # for row in astro_ll:
    #     print row

    db = init_sql_db()

    cursor = db.cursor()
    cursor.execute("USE splat")


    occurences = {}
    for idx, row in astro_ll.iterrows():
        curs2 = db.cursor()

        cmd = "SELECT line_id, frequency, measfreq FROM main WHERE Lovas_NRAO = 1 AND" \
              " (orderedfreq <= %s AND orderedfreq >= %s)" % (row['Freq'] + TOLERANCE, row['Freq'] - TOLERANCE)
        print cmd

        curs2.execute(cmd)

        num_results = 0
        for res in curs2:
            num_results += 1
        print row['Freq'], idx, num_results

        if str(num_results) not in occurences:
            occurences[str(num_results)] = 1
        else:
            occurences[str(num_results)] += 1
        curs2.close()

    occurences_quants = sorted([int(x) for x in occurences.keys()])
    for val in occurences_quants:
        print 'Number of transitions with %i matches: %i' %(val, occurences_quants[str(val)])






