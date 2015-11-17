import urllib2
from bs4 import BeautifulSoup
import time
import numpy as np
import pandas as pd
from itertools import izip_longest
import re
import random
import MySQLdb as sqldb
import easygui as eg
from QNFormat import *

__author__ = 'Nathan Seifert'


class CustomMolecule:  # With loaded CAT file from disk
    pass


class CDMSMolecule:

    def parse_cat(self, cat_url=None, local=0):

        def l_to_idx(letter):  # For when a QN > 99
                _abet = 'abcdefghijklmnopqrstuvwxyz'
                return next((z for z, _letter in enumerate(_abet) if _letter == letter.lower()), None)

        def make_parser(fieldwidths):
            def accumulate(iterable):
                total = next(iterable)
                yield total
                for value in iterable:
                    total += value
                    yield total

            cuts = tuple(cut for cut in accumulate(abs(fw) for fw in fieldwidths))
            pads = tuple(fw < 0 for fw in fieldwidths) # bool for padding
            flds = tuple(izip_longest(pads, (0,)+cuts, cuts))[:-1] # don't need final one
            parse = lambda line: tuple(line[i:j] for pad, i, j in flds if not pad)

            parse.size = sum(abs(fw) for fw in fieldwidths)
            parse.fmtstring = ' '.join('{}{}'.format(abs(fw), 'x' if fw < 0 else 's') for fw in fieldwidths)

            return parse

        widths = [13, 8, 8, 2, 10, 3, 7, 4]  # Not including quantum numbers
        w_sum = sum(widths)
        parser = make_parser(tuple(widths))

        if local == 0:
            cat_inp = urllib2.urlopen(cat_url).read().split('\n')
        else:
            cat_inp = cat_url.read().split('\n')

        initial_list = []

        j = 0
        for line in cat_inp:  # Parses the CAT file into chunks

            if j == 0:
                qn_len = len(line)-w_sum
                widths.append(qn_len)
                parser = make_parser(widths)

            initial_list.append(parser(line))
            j += 1

        # Let's put everything together to put into a dataframe
        parsed_list = []
        for row in initial_list:

            qns = re.findall('..', row[-1])  # splits QN entry into pairs
            up_done = False
            qns_up = []
            qns_down = []
            for val in qns:
                if val.strip() == '':
                    up_done = True
                    continue
                if not up_done:
                    try:
                        qns_up.append(int(val))
                    except ValueError:  # QN > 99
                        temp = list(val)
                        qns_up.append((100 + (l_to_idx(temp[0]))*10) + int(temp[1]))
                else:
                    try:
                        qns_down.append(int(val))
                    except:
                        temp = list(val)
                        qns_up.append((100 + (l_to_idx(temp[0]))*10) + int(temp[1]))

            try:
                parsed_list.append([float(s.strip()) for s in row[:-1]] + [qns_up, qns_down])
            except ValueError:  # Get blank line
                continue

        dtypes = [('freq', 'f8'), ('err', 'f8'), ('int', 'f8'), ('dof', 'i4'),
                  ('Elow', 'f8'),('g_up', 'i4'), ('tag', 'i4'), ('qn_fmt', 'i4')]
        dtypes.extend([('qn_up_%s' %i,'i4') for i in range(len(parsed_list[0][-2]))])
        dtypes.extend([('qn_dwn_%s' %i,'i4') for i in range(len(parsed_list[0][-2]))])

        final_list = []
        for row in parsed_list:
            final_list.append(tuple(row[:-2]+row[-2]+row[-1]))

        nplist = np.zeros((len(final_list),), dtype=dtypes)
        nplist[:] = final_list

        return pd.DataFrame(nplist)

    def get_metadata(self, meta_url):
        print self.name
        metadata = {}  # Dictionary for metadata, keys are consistent with columns in SQL

        # Dictionaries to connect string values in CDMS metadata to SQL columns
        Q_temps = {'2000.': 'Q_2000_', '1000.': 'Q_1000_', '500.0': 'Q_500_0', '300.0': 'Q_300_0',
                     '225.0': 'Q_225_0', '150.0': 'Q_150_0', '75.00': 'Q_75_00', '37.50': 'Q_37_50',
                     '18.75': 'Q_9_375'}
        dipoles = {'a / D': 'MU_A', 'b / D': 'MU_B', 'c / D': 'MU_C'}

        # Initialize scraper
        meta_page = urllib2.urlopen(meta_url)
        soup = BeautifulSoup(meta_page.read(), 'lxml')

        # Grab formula
        formula = soup.find_all('caption')[0].get_text().split('\n')[0].encode('utf-8')

        # Need to add lit data / dipoles etc

        meta_page.close()

        table = soup.find_all('tr')
        for entry in table:  # Right now it seems the best way is to brute force this
            temp = entry.get_text()

            metadata['Name'] = self.name
            metadata['Date'] = time.strftime('%b. %Y',self.date)
            if 'Contributor' in temp:
                metadata['Contributor'] = temp.split('Contributor')[1].encode('utf-8')

            # Pull out spin-rotation partiton function values
            for key in Q_temps:
                if 'Q(%s)' % key in temp:
                    metadata[Q_temps[key].encode('utf-8')] = temp.split('Q(%s)' % key)[1].encode('utf-8')

            value_check = lambda x: any(i.isdigit() for i in x)
            pull_float = lambda x: re.findall(r'\d+.\d+', x)

            for key in dipoles:
                if key in temp:
                    if value_check(temp) and 'Q(' not in temp:
                            metadata[dipoles[key]] = pull_float(temp)[0].encode('utf-8')

            if ('/ MHz' in temp or re.findall(r'[A-C]\d.\d+', temp)) and 'Q(' not in temp:
                if value_check(temp):
                    if 'A' in temp:
                        metadata['A'] = pull_float(temp)[0].encode('utf-8')
                    if 'B' in temp:
                        metadata['B'] = pull_float(temp)[0].encode('utf-8')
                    if 'C' in temp:
                        metadata['C'] = pull_float(temp)[0].encode('utf-8')

        metadata['Ref1'] = soup.find_all('p')[0].get_text()


        return formula, metadata

    def calc_derived_params(self, cat, metadata):
        Q_spinrot = float(metadata['Q_300_0'])
        kt_300_cm1 = 208.50908

        cat['sijmu2'] = 2.40251E4 * 10**(cat['int']) * Q_spinrot * (1./cat['freq']) * (1./(np.exp(-1.0*cat['Elow']/kt_300_cm1) - np.exp(-1.0*(cat['freq']/29979.2458+cat['Elow'])/kt_300_cm1)))
        cat['aij'] = np.log10(1.16395E-20*cat['freq']**3*cat['sijmu2']/cat['g_up'])

        return cat

    def __init__(self, cdms_inp):
        BASE_URL = "http://www.astro.uni-koeln.de"

        self.tag = cdms_inp[0]
        self.name = cdms_inp[1]
        self.date = cdms_inp[2]
        self.cat_url = cdms_inp[3]
        self.meta_url = cdms_inp[4]

        self.cat = self.parse_cat(BASE_URL+self.cat_url)
        self.formula, self.metadata = self.get_metadata(BASE_URL+self.meta_url)

        self.cat = self.calc_derived_params(self.cat, self.metadata)

class SplatSpeciesResultList(list):
    def __new__(cls, data=None):
        obj = super(SplatSpeciesResultList, cls).__new__(cls, data)
        return obj

    def __str__(self):
        it = list(self)
        it[0] = "0"*(4-len(str(it[0])))+str(it[0])
        return "{:5} {:10} {:10} {:>25} {:>15}".format(it[0], it[1], it[5], it[3], it[4])


class CDMSChoiceList(list):
    def __new__(cls, data=None):
        obj = super(CDMSChoiceList, cls).__new__(cls, data)
        return obj

    def __str__(self):
        it = list(self)
        it[0] = "0"*(4-len(it[0]))+it[0]
        return "{:5} {:10} {:>25} {:>25}".format(it[0], it[1], it[2], time.strftime("%B %Y",it[3]))


def unidrop(x): # Strips any non-ASCII unicode text from string
    return re.sub(r'[^\x00-\x7F]+',' ', x)


def pretty_print(comp):
    form = "{:5}\t{:45}\t{:15}\t{:40} {:40}"
    output = form.format(*('Tag', 'Molecule', 'Date','Cat Link', 'Metadata Link'))+'\n'
    for row in comp:
        output += form.format(*(row[0], row[1], time.strftime("%B %Y", row[2]), row[3], row[4]))+'\n'
    return output


def pull_updates():

    BASE_URL = "http://www.astro.uni-koeln.de"
    page = urllib2.urlopen(BASE_URL+"/cdms/entries")
    soup = BeautifulSoup(page.read(), "lxml")

    urls = []  # URLs to CAT and Documentation (metadata) files
    des = []  # Text from table entries
    for tr in soup.find_all('tr')[1:]:
        des.append([col.text for col in tr.find_all('td')])
        urls.append([a['href'] for a in tr.find_all('a')])

    page.close()  # Close HTML sock

    compiled = []  # 0 --> tag, 1 --> Molecule, 2 --> struct_time obj, 3 --> cat file, 4 --> metadata
    for i, entry in enumerate(urls):
        date = des[i][6].strip()

        try:  # Because Holger isn't consistent with his date formatting
            formatted_date = time.strptime(date, "%b. %Y")
        except ValueError:
            try:
                formatted_date = time.strptime(date, "%B %Y")
            except ValueError:
                formatted_date = time.strptime(date, "%b %Y")

        compiled.append([unidrop(des[i][0]).encode('utf-8'), unidrop(des[i][1]).encode('utf-8'),
                         formatted_date, urls[i][1], urls[i][2]])

    compiled.sort(key=lambda x: x[2], reverse=True)
    return compiled


def process_update(mol, entry=None, sql_conn=None):
    """
    Flow for process_update:
    1) Check metadata, update if needed
    2) Set QN formatting (????)
    3) Delete CDMS-related linelist from Splatalogue
    4) Push new linelist and metadata to Splatalogue
    """
    sql_cur = sql_conn.cursor()
    sql_cur.execute("USE splat")

    # ----------------------------
    # METADATA PULL CHECK & UPDATE
    # ----------------------------
    #meta_cmd = "SELECT * from species_metadata " \
    #      "WHERE species_id=%s" %str(entry[0])
    #print meta_cmd

    sql_cur.execute("SHOW columns FROM species_metadata")
    db_meta_cols = [tup[0] for tup in sql_cur.fetchall()]
    sql_cur.execute("SELECT * from species_metadata WHERE (species_id=%s", (int(entry[0]),))

    with sql_cur.fetchall() as results:
        if len(results) == 1:
            db_meta = results[0]
        else:  # There's more than one linelist associated with the chosen species_id
            chc = ['date: %s \t list: %s \t v1: %s \t v2: %s' %(a[3], a[52], a[53], a[55]) for a in results]
            user_chc = eg.choicebox("Choose an entry to update", "Entry list", chc)
            idx = 0
            for i, entry in chc:
                if user_chc == entry:
                    idx = i
                    break
            db_meta = results[idx]

    meta_fields = ['%s \t %s' %(a[0],a[1]) for a in zip(db_meta_cols, db_meta) if 'Ref' not in a[0]]
    meta_vals = eg.multenterbox('Enter stuff', 'Metadata', meta_fields)

    sql_cur.execute("SHOW columns FROM species")
    db_species_cols = [tup[0] for tup in sql_cur.fetchall()]
    sql_cur.execute("SELECT * from species WHERE species_id=%s", (int(entry[0]),))
    db_species = sql_cur.fetchall()

    # TO DO: Process metadata and get it ready


    # QN formatting --- let's just do it on a case-by-case basis
    qn_fmt = mol.cat['qn_fmt'][0]

    fmtted_QNs = []

    # Iterate through rows and add formatted QN
    for idx, row in mol.cat.iterrows():
        fmtted_QNs.append(format_it(qn_fmt, row[8:]))

    mol.cat['resolved_QNs'] = pd.Series(fmtted_QNs, index=mol.cat.index)

    print mol.cat


def main():

    # ------------------
    # POPULATE CDMS LIST
    # ------------------
    print 'Pulling updates from CDMS...'
    update_list = pull_updates()
    choice_list = [CDMSChoiceList([str(i)]+update_list[i]) for i in range(len(update_list))]
    print 'CDMS Update Completed.'

    # ---------
    # SQL LOGIN
    # ---------
    print '\nLogging into MySQL database...'

    def rd_pass():
        return open('pass.pass').read()

    HOST = "127.0.0.1"
    LOGIN = "nseifert"
    PASS = rd_pass()
    db = sqldb.connect(host=HOST, user=LOGIN, passwd=PASS.strip(), port=3306)
    db.autocommit(True)
    print 'MySQL Login Successful.'
    cursor = db.cursor()
    cursor.execute("USE splat")

    # ------------
    # GUI RUN LOOP
    # ------------
    ProgramLoopFinished = False

    while not ProgramLoopFinished:

        up_or_down = eg.buttonbox(msg='Do you want to pull a molecule from CDMS or load custom cat file?',
                                  title='Initialize', choices=['CDMS List', 'Custom File'])

        if up_or_down == 'CDMS List':

            choice = eg.choicebox("Choose a Molecule to Update", "Choice", choice_list)
            cat_entry = CDMSMolecule(update_list[int(choice[0:5])])

            cmd = "SELECT * FROM species " \
                "WHERE SPLAT_ID LIKE '%s%%'" % str(cat_entry.tag[:3])

            cursor.execute(cmd)
            res = cursor.fetchall()
            SplatMolResults = [SplatSpeciesResultList([i]+list(x)) for i, x in enumerate(res)]
            SplatMolResults += [SplatSpeciesResultList([len(SplatMolResults),999999999,0,'NEW MOLECULE',
                                                        'X','','','','','',''])]
            choice2 = eg.choicebox("Pick molecule from Splatalogue to update, or create a new molecule.\n "
                                   "Current choice is:\n %s" %choice, "Splatalogue Search Results",
                                   SplatMolResults)
            cursor.close()

            if choice2[68] == 'X':
                print 'Its a new molecule!'
            else:  # Molecule already exists in Splatalogue database
                process_update(cat_entry, res[int(choice2[0:5])], db)

        else:  # Open custom molecule
            cat_path = eg.fileopenbox()

        ProgramLoopFinished = True

    db.close()


if __name__ == "__main__":
    main()


