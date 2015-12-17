# -*- coding: utf-8 -*-
__author__ = 'nate'
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

class SplatSpeciesResultList(list):
    def __new__(cls, data=None):
        obj = super(SplatSpeciesResultList, cls).__new__(cls, data)
        return obj

    def __str__(self):
        it = list(self)
        it[0] = "0"*(4-len(str(it[0])))+str(it[0])
        return "{:5} {:10} {:10} {:>25} {:>15}".format(it[0], it[1], it[5], it[3], it[4])

class JPLMolecule:
    def parse_cat(self, cat_url=None, local=0):
        num_qns = 0

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
        qn_parser = make_parser((2,)*12)
        for row in initial_list:
            if num_qns == 0:  # Get number of quantum numbers per state
                num_qns = int(row[7][-1])

            qns = qn_parser(row[-1])  # splits QN entry into pairs
            up_done = False
            in_middle = False
            down_done = False
            qns_up = []
            qns_down = []
            down_idx = 0
            for i, val in enumerate(qns):


                if i == num_qns:
                    up_done = True
                    in_middle = True

                if up_done and in_middle and val.strip() == '':
                    continue
                if up_done and in_middle and val.strip() != '':
                    in_middle = False

                if down_idx == num_qns:
                    down_done = True

                if not up_done and not in_middle:
                    try:
                        qns_up.append(int(val))
                    except ValueError:
                        try:
                            if val.strip() == '+': # For parity symbols in CH3OH, for instance
                                qns_up.append(1)
                            elif val.strip() == '-':
                                qns_up.append(-1)
                            elif val.strip() == '': # No parity symbol?
                                qns_up.append(0)
                            elif re.search('[a-zA-Z]', val.strip()):  # QN > 99
                                temp = list(val)
                                qns_up.append((100 + (l_to_idx(temp[0]))*10) + int(temp[1]))
                        except TypeError:
                            print i, val, [x.strip() for x in qns]

                if up_done and (not down_done and not in_middle):
                    down_idx += 1
                    try:
                        qns_down.append(int(val))
                    except ValueError:
                        try:
                            if val.strip() == '+':
                                qns_down.append(1)
                            elif val.strip() == '-':
                                qns_down.append(-1)
                            elif val.strip() == '':
                                qns_down.append(0)
                            else:
                                temp = list(val)
                                qns_down.append((100 + (l_to_idx(temp[0]))*10) + int(temp[1]))
                        except TypeError:
                            print i, val, [x.strip() for x in qns]

            try:
                parsed_list.append([float(s.strip()) for s in row[:-1]] + [qns_up, qns_down])
            except ValueError:  # Get blank line
                continue

        dtypes = [('frequency', 'f8'), ('uncertainty', 'f8'), ('intintensity', 'f8'), ('degree_freedom', 'i4'),
                  ('lower_state_energy', 'f8'),('upper_state_degeneracy', 'i4'), ('molecule_tag', 'i4'), ('qn_code', 'i4')]
        dtypes.extend([('qn_up_%s' %i,'i4') for i in range(num_qns)])
        dtypes.extend([('qn_dwn_%s' %i,'i4') for i in range(num_qns)])

        final_list = []
        for row in parsed_list:
            final_list.append(tuple(row[:-2]+row[-2]+row[-1]))

        nplist = np.zeros((len(final_list),), dtype=dtypes)

        nplist[:] = final_list

        return pd.DataFrame(nplist)

    def get_metadata(self, meta_url):
        metadata = {}

        # Dictionaries to connect string values in JPL metadata to SQL columns
        tags = {'Name:': 'Name', 'Q(300.0)=': 'Q_300_0', 'Q(225.0)=': 'Q_225_0', 'Q(150.0)=': 'Q_150_0',
                'Q(75.00)=': 'Q_75_00', 'Q(37.50)=': 'Q_37_50', 'Q(18.75)=': 'Q_18_75', 'Q(9.375)=': 'Q_9_375',
                'A=': 'A', 'B=': 'B', 'C=': 'C', '$\\mu_a$ =': 'MU_A',  '$\\mu_b$ =': 'MU_B', '$\\mu_c$ =': 'MU_C',
                'Contributor:': 'Contributor'}
        ref_data_start = False
        ref_data = ""

        for line in urllib2.urlopen(meta_url).read().split('\n'):
            temp = line.split()
            if not temp:
                continue
            if temp[0] == '\\\\':
                temp2 = ' '.join(temp[1:]).split('&')
                for i, val in enumerate(temp2):
                    if val.strip() in tags.keys():
                        metadata[tags[val.strip()]] = temp2[i+1].strip()
            if temp[0] == '\\headend':
                ref_data_start = True
                continue
            if ref_data_start:
                temp3 = re.sub('[${}^]', '', re.sub('\bf', '', line.split('\n')[0]))
                temp3 = re.sub('\r', '', temp3)
                ref_data += temp3 + ' '

        metadata['Ref1'] = ref_data
        metadata['Name'] = self.name

        return metadata

    def calc_derived_params(self, cat, metadata):
        try:
            Q_spinrot = float(metadata['Q_300_0'])
        except ValueError:  # in case there's multiple numbers
            Q_spinrot = float(metadata['Q_300_0'].split('(')[0])
        kt_300_cm1 = 208.50908

        cat['sijmu2'] = 2.40251E4 * 10**(cat['intintensity']) * Q_spinrot * (1./cat['frequency']) * (1./(np.exp(-1.0*cat['lower_state_energy']/kt_300_cm1) - np.exp(-1.0*(cat['frequency']/29979.2458+cat['lower_state_energy'])/kt_300_cm1)))
        cat['aij'] = np.log10(1.16395E-20*cat['frequency']**3*cat['sijmu2']/cat['upper_state_degeneracy'])
        cat['lower_state_energy_K'] = cat['lower_state_energy']*1.4387863
        cat['upper_state_energy'] = cat['lower_state_energy'] + cat['frequency']/29979.2458
        cat['upper_state_energy_K'] = cat['upper_state_energy']*1.4387863
        cat['error'] = cat['uncertainty']
        cat['roundedfreq'] = np.round(cat['frequency'], 0)
        cat['line_wavelength'] = 299792458./(cat['frequency']*1.0E6)*1000

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
        cat['transition_in_space'] = '0'

        return cat

    def __init__(self, listing_entry):
        self.date = listing_entry[0]
        self.id = str(listing_entry[1])
        self.name = listing_entry[2]
        self.formula = self.name

        self.ll_id = '12'

        if len(self.id) == 5:
            self.cat_url = "http://spec.jpl.nasa.gov/ftp/pub/catalog/c0"+self.id+".cat"
            self.meta_url = "http://spec.jpl.nasa.gov/ftp/pub/catalog/doc/d0"+self.id+".cat"
        elif len(self.id) == 6:
            self.cat_url = "http://spec.jpl.nasa.gov/ftp/pub/catalog/c"+self.id+".cat"
            self.meta_url = "http://spec.jpl.nasa.gov/ftp/pub/catalog/doc/d"+self.id+".cat"
        else:
            self.cat_url = "http://spec.jpl.nasa.gov/ftp/pub/catalog/c00"+self.id+".cat"
            self.meta_url = "http://spec.jpl.nasa.gov/ftp/pub/catalog/doc/d00"+self.id+".cat"

        print 'Pulling metadata...'
        self.metadata = self.get_metadata(self.meta_url)
        print 'Parsing cat file...'
        self.cat = self.parse_cat(self.cat_url)

        self.cat = self.calc_derived_params(self.cat, self.metadata)
        self.cat['ll_id'] = self.ll_id

def initiate_sql_db():
    def rd_pass():
        return open('pass.pass').read()

    print '\nLogging into MySQL database...'

    HOST = "127.0.0.1"
    LOGIN = "nseifert"
    PASS = rd_pass()
    db = sqldb.connect(host=HOST, user=LOGIN, passwd=PASS.strip(), port=3306)
    db.autocommit(False)
    print 'MySQL Login Successful.'
    return db

def process(mol, id_dict, db):
    key = id_dict[0]
    vib_states_ids = id_dict[1][key]

    def qn_format(qn_series, extra):
        fmt = u'{:d}({:d}, {:d}) - {:d}({:d}, {:d})'
        order = [0, 1, 2, 4, 5, 6]
        return fmt.format(*[int(qn_series[j]) for j in order])

    cursor = db.cursor()
    cmd = "SELECT * FROM species WHERE s_name_noparens LIKE 'H2O%%'"
    cursor.execute(cmd)
    res = cursor.fetchall()

    result_choices = ['%s   %s  %s  %s' %(x[0], x[2], x[4], x[5]) for x in res] + ['X   NEW ENTRY']
    choice = eg.choicebox('Pick entry in Splatalogue database for vibrational state %s' %key,
                          "Choice", result_choices)
    try:
        species_id = choice.split()[0]
    except AttributeError:  # User hit cancel
        return 0

    # BUILD METADATA

    cursor.execute("SHOW columns FROM species_metadata")
    db_meta_cols = [tup[0] for tup in cursor.fetchall()]

    metadata_to_push = {}

    if species_id == "X":  # New entry

        for i, col_name in enumerate(db_meta_cols):
            if col_name in mol.metadata.keys():
                metadata_to_push[col_name] = mol.metadata[col_name]
            else:
                pass

        cursor.execute('SELECT MAX(species_id) FROM species')
        metadata_to_push['Name'] = "%s %s %s"%(mol.name, key, ' '.join([str(x) for x in vib_states_ids]))
        metadata_to_push['species_id'] = str(int(cursor.fetchall()[0][0])+1)
        metadata_to_push['v1_0'] = '1'
        metadata_to_push['v2_0'] = '2'
        # metadata_to_push['v3_0'] = '3'
        metadata_to_push['Ref20'] = mol.meta_url
        metadata_to_push['LineList'] = mol.ll_id

        new_name = eg.enterbox(msg="Do you want to change the descriptive metadata molecule name? "
                                   "Leave blank otherwise. Current name is %s" % metadata_to_push['Name'],
                               title="Metadata Name Change")
        if new_name is not '':
            metadata_to_push['Name'] = new_name

        # Generate new splat_id
        tag_num = mol.id
        tag_prefix = ''.join(('0',)*(6-len(tag_num)))+tag_num[:(len(tag_num)-3)]
        cmd = "SELECT SPLAT_ID FROM species " \
            "WHERE SPLAT_ID LIKE '%s%%'" % tag_prefix

        cursor.execute(cmd)
        splat_id_list = cursor.fetchall()
        if len(splat_id_list) > 0:
            splat_id = tag_prefix+ str(max([int(x[0][3:]) for x in splat_id_list]) + 1)
        else:
            splat_id = tag_prefix + '01'

        species_to_push = OrderedDict([('species_id', metadata_to_push['species_id']),
                                       ('name', mol.formula), ('chemical_name', None), ('s_name', mol.formula),
                                       ('s_name_noparens', mol.formula.replace('(','').replace(')','')), ('SPLAT_ID', splat_id),
                                       ('atmos', '0'), ('potential', '1'), ('probable', '0'), ('known_ast_molecules', '0'),
                                       ('planet', '0'), ('ism_hotcore', '0'), ('ism_diffusecloud', '0'), ('comet', '0'),
                                       ('extragalactic', '0'), ('AGB_PPN_PN', '0'), ('SLiSE_IT', '0'), ('Top20', '0')])

        species_choices_fieldnames = ['%s (%s)'%(key, value) for key, value in species_to_push.items()]
        species_choices = eg.multenterbox('Set species entries','species entry', species_choices_fieldnames)

        ism_set = ('ism_hotcore', 'ism_diffusecloud', 'comet', 'extragalactic', 'known_ast_molecules')
        ism_set_dict = {key: value for (key, value) in [(key, species_to_push[key]) for key in ism_set]}
        if any(val == '1' for val in ism_set_dict.values()):
            metadata_to_push['ism'] = 1
        else:
            metadata_to_push['ism'] = 0

        idx = 0
        for key in species_to_push:
            if not species_choices[idx]:
                pass
            else:
                species_to_push[key] = species_choices[idx]
            idx += 1

        ism_overlap_tags = ['ism_hotcore', 'comet', 'planet', 'AGB_PPN_PN', 'extragalactic']
        for tag in ism_overlap_tags:
            metadata_to_push[tag] = species_to_push[tag]

    else:  # Replace entry
        cursor.execute("SELECT * FROM species_metadata WHERE species_id=%s and LineList=12", (species_id,))
        db_meta = cursor.fetchall()[0]

        for i, col_name in enumerate(db_meta_cols):
            if col_name in mol.metadata.keys():
                metadata_to_push[col_name] = mol.metadata[col_name]
            elif db_meta[i] is not None:
                metadata_to_push[col_name] = db_meta[i]
            else:
                continue
        species_to_push = {}  # Create empty species dictionary. For control statement later.

    # FILTER CAT FILE AND PREPARE FOR UPLOAD
    mask = (mol.cat['qn_up_3'].isin(vib_states_ids)) & (mol.cat['qn_dwn_3'].isin(vib_states_ids)) & (mol.cat['qn_up_3'] == mol.cat['qn_dwn_3'])

    qn_fmt = mol.cat['qn_code'][0]
    temp_cat = mol.cat[mask]
    fmtted_QNs = []

    print 'Preparing linelist...'
    # Iterate through rows and add formatted QN
    for idx, row in temp_cat.iterrows():
        fmtted_QNs.append(qn_format(row.filter(regex=re.compile('(qn_)'+'.*?'+'(_)'+'(\\d+)')), vib_states_ids))

    # Prep linelist for submission to database
    cursor.execute("SHOW columns FROM main")
    ll_splat_col_list = [tup[0] for tup in cursor.fetchall()]
    ll_col_list = temp_cat.columns.values.tolist()

    final_cat = temp_cat[[col for col in ll_splat_col_list if col in ll_col_list]]
    final_cat['species_id'] = metadata_to_push['species_id']
    final_cat['resolved_QNs'] = pd.Series(fmtted_QNs, index=final_cat.index)

    # Push stuff
    ll_dict = [(None if pd.isnull(y) else y for y in x) for x in final_cat.values]
    num_entries = len(ll_dict)

    placeholders = lambda inp: ', '.join(['%s'] * len(inp))
    placeholders_err = lambda inp: ', '.join(['{}'] * len(inp))
    columns = lambda inp: ', '.join(inp.keys())

    query = lambda table, inp: "INSERT INTO %s ( %s ) VALUES ( %s )" % (table, columns(inp), placeholders(inp))
    query_err = lambda table, inp: "INSERT INTO %s ( %s ) VALUES ( %s )" % \
                                    (table, columns(inp), placeholders_err(inp))

    # Append final_cat and metadata_to_push here
    if not species_to_push:  # Update molecule
        print 'Updating species table...'
        species_to_push['created'] = time.strftime('%Y-%m-%d %H:%M:%S')
        species_to_push['nlines'] = str(len(final_cat.index))
        species_to_push['version'] = '1'
        species_to_push['resolved'] = '1'

        cursor = db.cursor()
        cursor.execute('UPDATE species SET created=%s WHERE species_id=%s',
                   (species_to_push['created'], metadata_to_push['species_id']))
        cursor.execute('UPDATE species SET nlines=%s WHERE species_id=%s',
                   (species_to_push['nlines'], metadata_to_push['species_id']))
        cursor.close()

        cursor = db.cursor()
        print 'Removing original metadata entry for replacing with new data...'
        cursor.execute('DELETE from species_metadata WHERE species_id=%s AND v1_0=%s AND v2_0=%s AND LineList=%s',
                   (metadata_to_push['species_id'], metadata_to_push['v1_0'], metadata_to_push['v2_0'], metadata_to_push['LineList']))
        print 'Removing original linelist for replacement...'
        cursor.execute('DELETE from main WHERE species_id=%s AND ll_id=%s',
                   (metadata_to_push['species_id'], metadata_to_push['LineList']))
        cursor.close()

    else:   # New molecule
        species_to_push['created'] = time.strftime('%Y-%m-%d %H:%M:%S')
        species_to_push['nlines'] = str(len(final_cat.index))
        species_to_push['version'] = '1'
        species_to_push['resolved'] = '1'

        cursor = db.cursor()
        print 'Creating new entry in species table...'
        try:
            cursor.execute(query("species", species_to_push), species_to_push.values())
        except sqldb.ProgrammingError:
            print "The following query failed: "
            print query_err("species", species_to_push).format(*species_to_push.values())
        print 'Finished successfully. Created entry for %s with species_id %s and SPLAT_ID %s \n' \
          % (species_to_push['name'], species_to_push['species_id'], species_to_push['SPLAT_ID'])
        cursor.close()

    cursor = db.cursor()
    # Create new metadata entry in database
    print 'Creating new entry in metadata table...'
    try:
        cursor.execute(query("species_metadata", metadata_to_push), metadata_to_push.values())
    except sqldb.ProgrammingError:
        print "The folllowing query failed: "
        print query_err("species_metadata", metadata_to_push).format(*metadata_to_push.values())
    print 'Finished successfully.\n'
    cursor.close()

    col_names = final_cat.columns.values
    print 'Pushing linelist (%s entries) to database...' %(num_entries)
    cursor = db.cursor()
    query_ll = "INSERT INTO %s ( %s ) VALUES ( %s )" \
               % ("main", ', '.join(final_cat.columns.values), placeholders(final_cat.columns.values))

    try:
        print query_ll
        cursor.executemany(query_ll, ll_dict)
    except sqldb.ProgrammingError:
        print 'Pushing linelist failed.'

    cursor.close()
    db.commit()

    print 'Finished with linelist push.'

def main():

    print 'Connecting to SQL database...'
    db = initiate_sql_db()
    cursor = db.cursor()
    cursor.execute("USE splat")
    print 'Successfully logged into SQL database.'

    JPL_ID_NUM = 18005
    molecule = JPLMolecule([time.strftime('%Y/%m/%d', time.localtime()), JPL_ID_NUM, 'H2O'])

    """ vib_states is dict, where the key is the state and the values are a list of integers
     which correspond to the state identifying (Q.N. #3) in the CAT file """
    vib_states = {'v1 = 1': [3], 'v2 = 1': [1], 'v2 = 2':[2], 'v3 = 1':[1]}

    for key in vib_states:
        process(molecule, (key, vib_states), db)



if __name__ == "__main__":
    pd.options.mode.chained_assignment = None
    main()



