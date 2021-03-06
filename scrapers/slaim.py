__author__ = 'nate'
import urllib2
from bs4 import BeautifulSoup
import time
import datetime
import numpy as np
import pandas as pd
from itertools import izip_longest
from collections import OrderedDict
import re
import MySQLdb as sqldb
import easygui as eg
from QNFormat import *

class SplatSpeciesResultList(list):
    def __new__(cls, data=None):
        obj = super(SplatSpeciesResultList, cls).__new__(cls, data)
        return obj

    def __str__(self):
        it = list(self)
        it[0] = "0"*(4-len(str(it[0])))+str(it[0])
        return "{:5} {:10} {:10} {:>25} {:>15}".format(it[0], it[1], it[5], it[3], it[4])


class SLAIMMolecule:
    def parse_cat(self, cat_url):
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

    def parse_vizier(self, cat_url, vizier_options):

        # Construct linelist result dictionary
        fmt = vizier_options['fmt']
        delimiter = vizier_options['delimiter']
        linelist = {}
        for key in fmt:
            linelist[key] = []

        atLineList = False

        inp = open(cat_url, 'r')
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
                        if len(line.strip().split(delimiter)) != len(fmt):
                            continue
                        else:
                            linelist[key].append(line.strip().split(delimiter)[i])
                except IndexError:
                    print "\"" + line + "\""
                    raise

        linelist['Freq'] = [float(f) for f in linelist['Freq']]  # Convert from str to float

        return pd.DataFrame.from_dict(linelist)

    def get_metadata(self):

        def inp_metadata(meta_inp_path):
            mdata = {}

            # Dictionaries to connect string values in JPL metadata to SQL columns
            tags = {'TITLE': 'Name', 'CHEMICAL_NAME': 'chemical_name', 'SHORT_NAME': 's_name',
                    'Q(300.0)': 'Q_300_0', 'Q(225.0)': 'Q_225_0', 'Q(150.0)': 'Q_150_0',
                    'Q(75.00)': 'Q_75_00', 'Q(37.50)': 'Q_37_50', 'Q(18.75)': 'Q_18_75', 'Q(9.375)': 'Q_9_375',
                    'A': 'A', 'B': 'B', 'C': 'C', 'MU_A': 'MU_A',  'MU_B': 'MU_B', 'MU_C': 'MU_C',
                    'CONTRIBUTOR': 'Contributor', 'REF': 'REF'}

            for line in open(meta_inp_path, 'r').read().split('\n'):
                if line[0] == '!':
                    continue

                id = line.split(':')[0]
                value = ":".join(line.split(':')[1:])
                try:
                    mdata[tags[id]] = value.strip()
                except KeyError:
                    if id == 'STATE_ID_IDX':
                        self.STATE_ID_IDX = value.strip()
                    elif id == 'STATE_ID_VAL':
                        self.STATE_ID_VAL = value.strip()
                    else:
                        continue

            mdata['Date'] = time.strftime('%b %Y', time.gmtime())
            return mdata

        metadata = {}

        # Dictionaries to connect string values in JPL metadata to SQL columns
        tags = {'Name:': 'Name', 'Q(300.0)=': 'Q_300_0', 'Q(225.0)=': 'Q_225_0', 'Q(150.0)=': 'Q_150_0',
                'Q(75.00)=': 'Q_75_00', 'Q(37.50)=': 'Q_37_50', 'Q(18.75)=': 'Q_18_75', 'Q(9.375)=': 'Q_9_375',
                'A=': 'A', 'B=': 'B', 'C=': 'C', '$\\mu_a$ =': 'MU_A',  '$\\mu_b$ =': 'MU_B', '$\\mu_c$ =': 'MU_C',
                'Contributor:': 'Contributor'}

        gui_order = ['Name', 'Contributor', 'Q(300.0)=', 'Q(225.0)=', 'Q(150.0)=', 'Q(75.00)=', 'Q(37.50)=', 'Q(18.75)=',
                     'Q(9.375)=', 'A', 'B', 'C', 'mu_A', '$\\mu_a$ =', '$\\mu_b$ =', '$\\mu_c$ =', 'Ref1']

        ent = eg.buttonbox(msg='Would you like to use a metadata input file or input it manually?',
                           choices=['Input file', 'Manual entry'])
        if ent == 'Input file':
            meta_path = eg.fileopenbox(msg='Choose a metadata input file.', title='Metadata input.')
            metadata = inp_metadata(meta_path)
        else:
            meta_temp = eg.multenterbox('Enter metadata', 'Metadata entry', gui_order)
            for i, entry in enumerate(gui_order):
                metadata[entry] = meta_temp[i]

        return metadata

    def calc_derived_params(self, cat):
        try:
            Q_spinrot = float(self.metadata['Q_300_0'])
        except ValueError:  # in case there's multiple numbers
            Q_spinrot = float(self.metadata['Q_300_0'].split('(')[0])
        kt_300_cm1 = 208.50908

        cat['sijmu2'] = 2.40251E4 * 10**(cat['intintensity']) * Q_spinrot * (1./cat['frequency']) * (1./(np.exp(-1.0*cat['lower_state_energy']/kt_300_cm1) - np.exp(-1.0*(cat['frequency']/29979.2458+cat['lower_state_energy'])/kt_300_cm1)))
        cat['aij'] = np.log10(1.16395E-20*cat['frequency']**3*cat['sijmu2']/cat['upper_state_degeneracy'])
        cat['lower_state_energy_K'] = cat['lower_state_energy']*1.4387863
        cat['upper_state_energy'] = cat['lower_state_energy'] + cat['frequency']/29979.2458
        cat['upper_state_energy_K'] = cat['upper_state_energy']*1.4387863
        cat['error'] = cat['uncertainty']
        cat['roundedfreq'] = cat['frequency'].apply(lambda x: np.round(x, 0))
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

    def __init__(self, listing_entry, cat_file, type='cat', vizier_options=None):
        self.date = datetime.datetime.now().strftime('%Y/%m/%d')
        self.id = str(listing_entry[1])
        self.name = listing_entry[0]
        self.formula = self.name

        self.ll_id = '14'

        print 'Pulling metadata...'
        self.metadata = self.get_metadata()
        print 'Parsing cat file...'
        if type == 'cat':
            self.cat = self.calc_derived_params(self.parse_cat(cat_file))
        elif type == 'vizier':
            self.cat = self.calc_derived_params(self.parse_vizier(cat_file, vizier_options))

        self.cat['ll_id'] = self.ll_id
        self.cat['`v4.0`'] = 4

def process_update(mol, entry=None, sql_conn=None):
    """
    Flow for process_update:
    1) Check metadata, update if needed
    2) Set QN formatting (????)
    3) Delete CDMS-related linelist from Splatalogue
    4) Push new linelist and metadata to Splatalogue
    """
    sql_cur = sql_conn.cursor()

    # ----------------------------
    # METADATA PULL CHECK & UPDATE
    # ----------------------------
    #meta_cmd = "SELECT * from species_metadata " \
    #      "WHERE species_id=%s" %str(entry[0])
    #print meta_cmd

    sql_cur.execute("SHOW columns FROM species_metadata")
    db_meta_cols = [tup[0] for tup in sql_cur.fetchall()]
    sql_cur.execute("SELECT * from species_metadata WHERE species_id=%s", (entry[0],))

    results = sql_cur.fetchall()
    print results
    if len(results) == 1:
        db_meta = results[0]

    elif len(results) > 1:  # There's more than one linelist associated with the chosen species_id
        chc = ['date: %s \t list: %s \t v1: %s \t v2: %s' %(a[3], a[52], a[53], a[54]) for a in results]
        user_chc = eg.choicebox("Choose an entry to update (JPL linelist = 12)", "Entry list", chc)
        idx = 0
        for i, entry in enumerate(chc):
            if user_chc == entry:
                idx = i
                break
        db_meta = results[idx]

    if db_meta[52] != mol.ll_id:
        # Only entry in database isn't from the linelist of the entry that user wants to update
        ref_idx = 23
        mol.metadata['v1_0'] = '0'
        mol.metadata['v2_0'] = '0'
        mol.metadata['v3_0'] = '0'
        mol.metadata['v4_0'] = '4'
        mol.metadata['LineList'] = mol.ll_id
        new_name = eg.enterbox(msg="Do you want to change the descriptive metadata molecule name? Leave blank otherwise. Current name is %s"
                               % mol.metadata['Name'], title="Metadata Name Change")
        if new_name is not '':
            mol.metadata['Name'] = new_name
    else:
        mol.metadata['Name'] = db_meta[2]
        # Check to see first column to place reference info
        ref_idx = 23
        while True:
            if db_meta[ref_idx] == None:
                break
            ref_idx += 1

    mol.metadata[db_meta_cols[ref_idx]] = mol.metadata.pop('Ref1')

    mol.metadata['Ref20'] = mol.meta_url
    # meta_fields = ['%s \t %s' %(a[0],a[1]) for a in zip(db_meta_cols, db_meta) if 'Ref' not in a[0]]

    sql_cur.execute("SHOW columns FROM species")

    db_species_cols = [tup[0] for tup in sql_cur.fetchall()]
    sql_cur.execute("SELECT * from species WHERE species_id=%s", (db_meta[0],))
    db_species = sql_cur.fetchall()[0]

    if db_meta[52] != mol.ll_id:
        species_entry_dict = {key: value for (key,value) in [(db_species_cols[i], val) for i, val in enumerate(db_species)]}
        ism_set = ('ism_hotcore', 'ism_diffusecloud', 'comet', 'extragalactic', 'known_ast_molecules')
        ism_set_dict = {key: value for (key, value) in [(key, species_entry_dict[key]) for key in ism_set]}
        if any(val == '1' for val in ism_set_dict.values()):
            mol.metadata['ism'] = 1
        else:
            mol.metadata['ism'] = 0

        ism_overlap_tags = ['ism_hotcore', 'comet', 'planet', 'AGB_PPN_PN', 'extragalactic']
        for tag in ism_overlap_tags:
            mol.metadata[tag] = species_entry_dict[tag]
        mol.metadata['ism_diffuse'] = species_entry_dict['ism_diffusecloud']
        mol.metadata['species_id'] = species_entry_dict['species_id']

    # for row in zip(db_meta_cols, db_meta):
    #     print row[0],'\t',row[1]

    # sql_cur.execute("SELECT * from species_metadata WHERE species_id=%s and v1_0=%s and v2_0=%s",
    #                 (db_meta[0], mol.ll_id, db_meta[53], db_meta[54]))

    if db_meta[52] == mol.ll_id:
        metadata_to_push = {}
        for i,col_name in enumerate(db_meta_cols):
            if col_name in mol.metadata.keys():
                metadata_to_push[col_name] = mol.metadata[col_name]
            elif db_meta[i] is not None:
                metadata_to_push[col_name] = db_meta[i]
            else:
                continue
    else:
        metadata_to_push = mol.metadata

    # for key in metadata_to_push:
    #     print '%s: %s' %(key, metadata_to_push[key])

    # QN formatting --- let's just do it on a case-by-case basis
    qn_fmt = mol.cat['qn_code'][0]

    fmtted_QNs = []
    print 'Preparing linelist...'
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
    #sql_cur.execute("USE splattest")

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
    metadata_to_push['v1_0'] = '0'
    metadata_to_push['v2_0'] = '0'
    metadata_to_push['v3_0'] = '0'
    metadata_to_push['v4_0'] = '4'
    metadata_to_push['Ref20'] = mol.meta_url
    metadata_to_push['LineList'] = mol.ll_id

    new_name = eg.enterbox(msg="Do you want to change the descriptive metadata molecule name? Leave blank otherwise. Current name is %s"
                               % metadata_to_push['Name'], title="Metadata Name Change")
    if new_name is not '':
        metadata_to_push['Name'] = new_name

    tag_num = mol.id
    tag_prefix = ''.join(('0',)*(3-len(tag_num)))
    cmd = "SELECT SPLAT_ID FROM species " \
        "WHERE SPLAT_ID LIKE '%s%%'" % tag_prefix
    print 'Tag prefix, '+tag_prefix
    sql_cur.execute(cmd)
    splat_id_list = sql_cur.fetchall()
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

def push_molecule(db, ll, spec_dict, meta_dict, update=0):

    for key in meta_dict:
        print key, '\t', meta_dict[key]

    print 'Converting linelist for SQL insertion...'
    ll['species_id'] = meta_dict['species_id']
    ll_dict = [(None if pd.isnull(y) else y for y in x) for x in ll.values]
    num_entries = len(ll_dict)

    # Create new species entry in database
    placeholders = lambda inp: ', '.join(['%s'] * len(inp))
    placeholders_err = lambda inp: ', '.join(['{}'] * len(inp))
    columns = lambda inp: ', '.join(inp.keys())

    query = lambda table, inp: "INSERT INTO %s ( %s ) VALUES ( %s )" % (table, columns(inp), placeholders(inp))
    query_err = lambda table, inp: "INSERT INTO %s ( %s ) VALUES ( %s )" % \
                                        (table, columns(inp), placeholders_err(inp))

    # Add some last minute entries to dictionaries
    spec_dict['created'] = time.strftime('%Y-%m-%d %H:%M:%S')
    spec_dict['nlines'] = str(len(ll.index))
    spec_dict['version'] = '1'
    spec_dict['resolved'] = '1'

    if update:
        # Update a few things in species column
        print 'Updating species table...'
        cursor = db.cursor()
        cursor.execute('UPDATE species SET created=%s WHERE species_id=%s',
                       (spec_dict['created'], meta_dict['species_id']))
        cursor.execute('UPDATE species SET nlines=%s WHERE species_id=%s',
                       (spec_dict['nlines'], meta_dict['species_id']))
        cursor.close()

    else:
        cursor = db.cursor()
        print 'Creating new entry in species table...'
        try:
            cursor.execute(query("species", spec_dict), spec_dict.values())
        except sqldb.ProgrammingError:
            print "The following query failed: "
            print query_err("species", spec_dict).format(*spec_dict.values())
        print 'Finished successfully. Created entry for %s with species_id %s and SPLAT_ID %s \n' \
              % (spec_dict['name'], spec_dict['species_id'], spec_dict['SPLAT_ID'])
        cursor.close()

    # Replace metadata content if updating an entry
    # if update:
    #     cursor = db.cursor()
    #     print 'Removing original metadata entry for replacing with new data...'
    #     cursor.execute('DELETE from species_metadata WHERE species_id=%s AND v1_0=%s AND v2_0=%s AND LineList=%s',
    #                    (meta_dict['species_id'], meta_dict['v1_0'], meta_dict['v2_0'], meta_dict['LineList']))
    #     print 'Removing original linelist for replacement...'
    #     cursor.execute('DELETE from main WHERE species_id=%s AND ll_id=%s',
    #                    (meta_dict['species_id'], meta_dict['LineList']))
    #     cursor.close()

    cursor = db.cursor()
    # Create new metadata entry in database
    print 'Creating new entry in metadata table...'
    try:
        cursor.execute(query("species_metadata", meta_dict), meta_dict.values())
    except sqldb.ProgrammingError:
        print "The folllowing query failed: "
        print query_err("species_metadata", meta_dict).format(*meta_dict.values())
    print 'Finished successfully.\n'
    cursor.close()

    # Push linelist to database
    col_names = ll.columns.values

    print 'Pushing linelist (%s entries) to database...' %(num_entries)
    cursor = db.cursor()
    query_ll = "INSERT INTO %s ( %s ) VALUES ( %s )" % ("main", ', '.join(ll.columns.values), placeholders(ll.columns.values))

    try:
        cursor.executemany(query_ll, ll_dict)
    except sqldb.ProgrammingError:
        print 'Pushing linelist failed.'

    cursor.close()
    db.commit()

    print 'Finished with linelist push.'

def main(db, type='cat'):
    pd.options.mode.chained_assignment = None

    # Get JPL update listing
    SLAIMLoop = True

    while SLAIMLoop:

        entryValues = eg.multenterbox('Please enter basic information for SLAIM entry', 'SLAIM entry', ['Molecular Formula', 'Mass'])
        cat_path = eg.fileopenbox(msg='Please select input CAT file for SLAIM entry', title='CAT entry')

        cat_entry = SLAIMMolecule(listing_entry=entryValues, cat_file=open(cat_path, 'r'), type='cat')
        tag_num = str(cat_entry.id)

        if 10 <= int(cat_entry.id) < 100:
            splat_id_search = "0"+str(cat_entry.id)
        elif int(cat_entry.id) < 10:
            splat_id_search = "00"+str(cat_entry.id)
        else:
            splat_id_search = cat_entry.id

        print tag_num, ''.join(('0',)*(3-len(tag_num)))
        cmd = "SELECT * FROM species " \
             "WHERE SPLAT_ID LIKE '%s%%'" % (splat_id_search,)

        cursor = db.cursor()
        cursor.execute(cmd)
        res = cursor.fetchall()

        SplatMolResults = [SplatSpeciesResultList([i]+list(x)) for i, x in enumerate(res)]
        SplatMolResults += [SplatSpeciesResultList([len(SplatMolResults),999999999,0,'NEW MOLECULE',
                                                    'X','','','','','',''])]
        choice2 = eg.choicebox("Pick molecule from Splatalogue to update, or create a new molecule.\n "
                               "Current choice is:\n %s" %cat_entry.name, "Splatalogue Search Results",
                               SplatMolResults)
        cursor.close()

        if choice2[68] == 'X':
            linelist, species_final, metadata_final = new_molecule(cat_entry, db)
            push_molecule(db, linelist, species_final, metadata_final, update=0)

        else:  # Molecule already exists in Splatalogue database
            linelist, metadata_final = process_update(cat_entry, res[int(choice2[0:5])], db)
            push_molecule(db, linelist, {}, metadata_final, update=1)

        choice3 = eg.buttonbox(msg='Do you want to update another CDMS entry?', choices=['Yes', 'No'])

        if choice3 == 'No':
            SLAIMLoop = False
