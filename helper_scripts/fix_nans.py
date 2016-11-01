import MySQLdb as sqldb
from tqdm import tqdm

def initiate_sql_db(user_dict):
    print '\nLogging into MySQL database...'

    db = sqldb.connect(host=user_dict['ip'], user=user_dict['user'],
                       passwd=user_dict['pass'], port=int(user_dict['port']))
    db.autocommit(False)
    print 'MySQL Login Successful.'
    return db

if __name__ == "__main__":

	db = initiate_sql_db({'ip': '127.0.0.1', 'user': 'nseifert', 'pass': 'lolz', 'port': 3307})

	cur = db.cursor()
	cur.execute("USE splat")

	cur.execute("SELECT line_id, resolved_QNs from main where resolved_QNs like \"%%nan%%\" and species_id = 664 ")

	lines_to_fix = cur.fetchall()
	print lines_to_fix

	for line in tqdm(lines_to_fix):
		line_id, qn = line 
		fixed_qn = ",".join(qn.split(',')[:-1])
		
		cur.execute("UPDATE main SET resolved_QNs = \"%s\" WHERE line_id = %s" %(fixed_qn, line_id))

	cur.close()
