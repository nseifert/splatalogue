import urllib2
from bs4 import BeautifulSoup
import time
import numpy as np
import pandas as pd
from itertools import izip_longest
from collections import OrderedDict
import re
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

        dtypes = [('frequency', 'f8'), ('uncertainty', 'f8'), ('intintensity', 'f8'), ('degree_freedom', 'i4'),
                  ('lower_state_energy', 'f8'),('upper_state_degeneracy', 'i4'), ('molecule_tag', 'i4'), ('qn_code', 'i4')]
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

        metadata['Ref1'] = str(soup.find_all('p')[0]).replace('\n', ' ')
        #print metadata


        return formula, metadata

    def calc_derived_params(self, cat, metadata):
        Q_spinrot = float(metadata['Q_300_0'])
        kt_300_cm1 = 208.50908

        cat['sijmu2'] = 2.40251E4 * 10**(cat['intintensity']) * Q_spinrot * (1./cat['frequency']) * (1./(np.exp(-1.0*cat['lower_state_energy']/kt_300_cm1) - np.exp(-1.0*(cat['frequency']/29979.2458+cat['lower_state_energy'])/kt_300_cm1)))
        cat['aij'] = np.log10(1.16395E-20*cat['frequency']**3*cat['sijmu2']/cat['upper_state_degeneracy'])
        cat['lower_state_energy_K'] = cat['lower_state_energy']*1.4387863
        cat['upper_state_energy'] = cat['lower_state_energy'] + cat['frequency']/29979.2458
        cat['upper_state_energy_K'] = cat['upper_state_energy']*1.4387863
        cat['error'] = cat['uncertainty']
        cat['roundedfreq'] = np.round(cat['frequency'], 0)


        qn_cols = cat.filter(regex=re.compile('(qn_)'+'.*?'+'(_)'+'(\\d+)')).columns.values.tolist()
        cat['quantum_numbers'] = cat[qn_cols].apply(lambda x: ' '.join([str(e) for e in x]), axis=1)

        # Add measured freqs and then ordered frequencies
        cat['measfreq'] = np.nan
        cat['orderedfreq'] = np.nan
        cat['measerrfreq'] = np.nan
        mask_meas = (cat['molecule_tag'] < 0)
        mask_pred = (cat['molecule_tag'] > 0)
        cat['measfreq'][mask_meas] = cat['frequency'][mask_meas]
        cat['frequency'][mask_meas] = np.nan
        cat['orderedfreq'][mask_meas] = cat['measfreq'][mask_meas]
        cat['measerrfreq'][mask_meas] = cat['uncertainty'][mask_meas]
        cat['orderedfreq'][mask_pred] = cat['frequency'][mask_pred]

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
    sql_cur.execute("SELECT * from species_metadata WHERE species_id=%s", (int(entry[0]),))

    results = sql_cur.fetchall()
    if len(results) == 1:
        db_meta = results[0]
    else:  # There's more than one linelist associated with the chosen species_id
        chc = ['date: %s \t list: %s \t v1: %s \t v2: %s' %(a[3], a[52], a[53], a[54]) for a in results]
        user_chc = eg.choicebox("Choose an entry to update", "Entry list", chc)
        idx = 0
        for i, entry in enumerate(chc):
            if user_chc == entry:
                idx = i
                break
        db_meta = results[idx]
    print db_meta

    # Check to see first column to place reference info
    ref_idx = 23
    while True:
        if db_meta[ref_idx] == None:
            break
        ref_idx += 1

    mol.metadata[db_meta_cols[ref_idx]] = mol.metadata.pop('Ref1')
    mol.metadata['Name'] = db_meta[2]
    mol.metadata['Ref20'] = "http://www.astro.uni-koeln.de"+mol.meta_url
    # meta_fields = ['%s \t %s' %(a[0],a[1]) for a in zip(db_meta_cols, db_meta) if 'Ref' not in a[0]]

    sql_cur.execute("SHOW columns FROM species")

    db_species_cols = [tup[0] for tup in sql_cur.fetchall()]
    sql_cur.execute("SELECT * from species WHERE species_id=%s", (db_meta[0],))
    db_species = sql_cur.fetchall()[0]

    # for row in zip(db_meta_cols, db_meta):
    #     print row[0],'\t',row[1]

    sql_cur.execute("SELECT * from species_metadata WHERE species_id=%s and v1_0=%s and v2_0=%s", (db_meta[0], db_meta[53], db_meta[54]))
    print '----\n',sql_cur.fetchall()

    metadata_to_push = {}
    for i,col_name in enumerate(db_meta_cols):
        if col_name in mol.metadata.keys():
            metadata_to_push[col_name] = mol.metadata[col_name]
        elif db_meta[i] is not None:
            metadata_to_push[col_name] = db_meta[i]
        else:
            continue

    # for key in metadata_to_push:
    #     print '%s: %s' %(key, metadata_to_push[key])

    # QN formatting --- let's just do it on a case-by-case basis
    qn_fmt = mol.cat['qn_code'][0]

    fmtted_QNs = []

    # Iterate through rows and add formatted QN
    for idx, row in mol.cat.iterrows():
        fmtted_QNs.append(format_it(qn_fmt, row.filter(regex=re.compile('(qn_)'+'.*?'+'(_)'+'(\\d+)'))))

    mol.cat['resolved_QNs'] = pd.Series(fmtted_QNs, index=mol.cat.index)

    # Prep linelist for submission to database
    sql_cur.execute("SHOW columns FROM main")
    ll_splat_col_list = [tup[0] for tup in sql_cur.fetchall()]
    ll_col_list = mol.cat.columns.values.tolist()
    final_cat = mol.cat[[col for col in ll_splat_col_list if col in ll_col_list]]

    return final_cat, metadata_to_push

def new_molecule(mol, sql_conn=None):

    sql_cur = sql_conn.cursor()
    sql_cur.execute("USE splattest")

    # ----------------------------
    # METADATA ADD
    # ----------------------------

    sql_cur.execute("SHOW columns FROM species_metadata")
    db_meta_cols = [tup[0] for tup in sql_cur.fetchall()]
    metadata_to_push = {}

    for i, col_name in enumerate(db_meta_cols):
        if col_name in mol.metadata.keys():
            metadata_to_push[col_name] = mol.metadata[col_name]
        else:
            continue

    # Generate new species_id
    sql_cur.execute('SELECT MAX(species_id) FROM species')
    metadata_to_push['species_id'] = str(int(sql_cur.fetchall()[0][0])+1)
    metadata_to_push['v1_0'] = '1'
    metadata_to_push['v2_0'] = '2'
    # metadata_to_push['v3_0'] = '3'
    metadata_to_push['Ref20'] = "http://www.astro.uni-koeln.de"+mol.meta_url
    metadata_to_push['LineList'] = '10'

    # Generate new splat_id
    cmd = "SELECT SPLAT_ID FROM species " \
        "WHERE SPLAT_ID LIKE '%s%%'" % str(mol.tag[:3])
    sql_cur.execute(cmd)
    splat_id_list = sql_cur.fetchall()
    if len(splat_id_list) > 0:
        splat_id = mol.tag[:3]+ str(max([int(x[0][3:]) for x in splat_id_list]) + 1)
    else:
        splat_id = mol.tag[:3] + '01'

    species_to_push = OrderedDict([('species_id', metadata_to_push['species_id']),
                                   ('name', mol.formula), ('chemical_name', None), ('s_name', mol.formula),
                                   ('s_name_noparens', mol.formula.replace('(','').replace(')','')), ('SPLAT_ID', splat_id),
                                   ('atmos', '0'), ('potential', '1'), ('probable', '0'), ('known_ast_molecules', '0'),
                                   ('planet', '0'), ('ism_hotcore', '0'), ('ism_diffusecloud', '0'), ('comet', '0'),
                                   ('extragalactic', '0'), ('AGB_PPN_PN', '0'), ('SLiSE_IT', '0'), ('Top20', '0')])

    species_choices_fieldnames = ['%s (%s)'%(key, value) for key, value in species_to_push.items()]
    species_choices = eg.multenterbox('Set species entries','species entry', species_choices_fieldnames)

    idx = 0
    for key in species_to_push:
        if species_choices[idx] == '':
            continue
        else:
            species_to_push[key] = species_choices[idx]
        idx +=1

    ism_overlap_tags = ['ism_hotcore', 'comet', 'planet', 'AGB_PPN_PN', 'extragalactic']
    for tag in ism_overlap_tags:
        metadata_to_push[tag] = species_to_push[tag]

    # Format quantum numbers
    qn_fmt = mol.cat['qn_code'][0]
    fmtted_QNs = []

    # Iterate through rows and add formatted QN
    for idx, row in mol.cat.iterrows():
        fmtted_QNs.append(format_it(qn_fmt, row.filter(regex=re.compile('(qn_)'+'.*?'+'(_)'+'(\\d+)'))))

    mol.cat['resolved_QNs'] = pd.Series(fmtted_QNs, index=mol.cat.index)

    # Prep linelist for submission to database
    sql_cur.execute("SHOW columns FROM main")
    ll_splat_col_list = [tup[0] for tup in sql_cur.fetchall()]
    ll_col_list = mol.cat.columns.values.tolist()
    final_cat = mol.cat[[col for col in ll_splat_col_list if col in ll_col_list]]

    return final_cat, species_to_push, metadata_to_push

def main():

    # ------------------
    # POPULATE CDMS LIST
    # ------------------
    pd.options.mode.chained_assignment = None
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
    db.autocommit(False)
    print 'MySQL Login Successful.'
    cursor = db.cursor()
    cursor.execute("USE splattest")

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
                linelist, species_final, metadata_final = new_molecule(cat_entry, db)
                linelist.to_excel('test.xlsx')

            else:  # Molecule already exists in Splatalogue database
                linelist, metadata_final = process_update(cat_entry, res[int(choice2[0:5])], db)

                """ TO DO:
                Implement SQL commands to delete old content and push new data into database.
                """

 
        else:  # Open custom molecule
            cat_path = eg.fileopenbox()

        ProgramLoopFinished = True

    db.close()


if __name__ == "__main__":
    main()


