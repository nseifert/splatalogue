from easygui import *
import scrapers.jpl as jpl
import scrapers.cdms as cdms
import scrapers.slaim as slaim
import scrapers.toyama as toyama
import MySQLdb as sqldb
import sys


def read_sql_inp(path):
    inp_data = {}
    for line in open(path,'r').read().split('\n'):
        try:
	        if not line.strip():
	            continue
	        if line.strip()[0] == "!":
	        	continue
	        inp_data[line.split(':')[0].strip().lower()] = line.split(':')[1].strip()
        except:
        	print 'There is an error in your SQL input file. Line contains: %s' %line
        	raise

    return inp_data


def initiate_sql_db(user_dict):
    print '\nLogging into MySQL database...'

    db = sqldb.connect(host=user_dict['ip'], user=user_dict['user'],
                       passwd=user_dict['pass'], port=int(user_dict['port']))
    db.autocommit(False)
    print 'MySQL Login Successful.'
    return db


if __name__ == '__main__':

    MainLoop = True
    while MainLoop:

        sql_ques = buttonbox(msg='Would you like to use a predefined input file to connect to the SQL server?',
                  choices=['Yes', 'No', 'Cancel'])

        trans_fields = {'username': 'user', 'ip address': 'ip', 'port': 'port', 'password (optional)': 'pass'}
        sql_user_fields = ['Username', 'IP Address', 'Port', 'Password (optional)']
        user_info = {}

        if sql_ques == 'Yes':
            path_to_sql_user = fileopenbox(msg='Please select your mySQL server input file.')
            user_info = read_sql_inp(path_to_sql_user)

        elif sql_ques == 'No':
            temp_info = multenterbox(msg='Please enter your mySQL server login info.',
                         fields=sql_user_fields)
            for i, val in enumerate(temp_info):
                if not val:
                    continue
                else:
                    user_info[trans_fields[sql_user_fields[i].lower()]] = val

        else:
            sys.exit()

        if 'pass' not in user_info.keys():
            user_info['pass'] = passwordbox(msg='Enter your mySQL server password.', title='Password?')

        db = initiate_sql_db(user_info)

        cursor = db.cursor()
        if 'db' in user_info.keys():
            cursor.execute("USE %s" % user_info['db'])
        else:
            cursor.execute("USE splat")
        cursor.close()

        ActivityLoop = True
        while ActivityLoop:

            activity_choices = ['Add or update molecule via JPL. (Stable)', 'Add or update molecule via CDMS. (Stable)',
                                'Add or update molecule via Toyama (Works pretty well).',
                                'Add or update molecule with custom CAT file into SLAIM database. (Not 100pct bug-free)',
                                'Append observational information to transitions in database. (Not yet implemented)', 'Quit.']
            the_choice = choicebox(msg='Please choose an activity.', title='Main Screen', choices=activity_choices)
            if not the_choice:
            	break
         
            choice_idx = activity_choices.index(the_choice)
            if choice_idx == len(activity_choices) - 1:
                choice_idx = -1

            if choice_idx == 0:
                # DO JPL shit
                jpl.main(db)
            elif choice_idx == 1:
                # DO CDMS shit
                cdms.main(db)
            elif choice_idx == 2:
                toyama.main(db)
            elif choice_idx == 3:
                slaim.main(db)
                pass
            elif choice_idx == 4:
                print 'Sorry, this is not yet implemented!'
                pass

            elif the_choice == activity_choices[-1]:
                print 'You chose to quit. See you later!'
                sys.exit()

            # End of activity loop -- retry??
            retry_ques = buttonbox(msg='Would you like to do something else?',
                      choices=['Yes', 'No'])

            if retry_ques == 'No':
                ActivityLoop = False

        MainLoop = False
        db.close()
