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
import os
from QNFormat import *


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
        max_qn_length = 0 # For fitting strings into  temporary numpy array

        for row in initial_list:
            raw_qn = row[-1].rstrip()

            if len(raw_qn) > max_qn_length:
                max_qn_length = len(raw_qn)

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
                            elif re.search('[a-z]', val.strip()): # QN < -9, e.g. CDMS CD3CN entry
                                temp = list(val)
                                qns_up.append((-10 - l_to_idx(temp[0])*10) - int(temp[1]))
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
                            elif re.search('[a-zA-Z]', val.strip()):  # QN > 99
                                temp = list(val)
                                qns_down.append((100 + (l_to_idx(temp[0]))*10) + int(temp[1]))
                            elif re.search('[a-z]', val.strip()): # QN < -9, e.g. CDMS CD3CN entry
                                temp = list(val)
                                qns_down.append((-10 - l_to_idx(temp[0])*10) - int(temp[1]))
                        except TypeError:
                            print i, val, [x.strip() for x in qns]
            try:
                parsed_list.append([float(s.strip()) for s in row[:-1]] + [raw_qn] + [qns_up, qns_down])
            except ValueError:  # Get blank line or other issue?
                line = [s.strip() for s in row[:-1]]
                if not line[0]: # Blank line
                    continue
                elif any([char.isalpha() for char in line[5]]): # Upper state degeneracy > 99:
                    line[5] = 1000 + l_to_idx(line[5][0])*100 + int(line[5][1:])
                    parsed_list.append([float(col) for col in line]+ [raw_qn] + [qns_up, qns_down])

        dtypes = [('frequency', 'f8'), ('uncertainty', 'f8'), ('intintensity', 'f8'), ('degree_freedom', 'i4'),
                  ('lower_state_energy', 'f8'),('upper_state_degeneracy', 'i4'), ('molecule_tag', 'i4'),
                  ('qn_code', 'i4'), ('raw_qn', 'S%i'%max_qn_length)]
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
        metadata['Date'] = time.strftime('%b. %Y', time.strptime(self.date,'%Y/%m'))

        return metadata

    def calc_derived_params(self, cat, metadata):
        try:
            Q_spinrot = float(metadata['Q_300_0'])
        except ValueError:  # in case there's multiple numbers
            Q_spinrot = float(metadata['Q_300_0'].split('(')[0])
        kt_300_cm1 = 208.50908

        cat['sijmu2'] = 2.40251E4 * 10**(cat['intintensity']) * Q_spinrot * (1./cat['frequency']) * \
                        (1./(np.exp(-1.0*cat['lower_state_energy']/kt_300_cm1) -
                             np.exp(-1.0*(cat['frequency']/29979.2458+cat['lower_state_energy'])/kt_300_cm1)))
        cat['aij'] = np.log10(1.16395E-20*cat['frequency']**3*cat['sijmu2']/cat['upper_state_degeneracy'])
        cat['lower_state_energy_K'] = cat['lower_state_energy']*1.4387863
        cat['upper_state_energy'] = cat['lower_state_energy'] + cat['frequency']/29979.2458
        cat['upper_state_energy_K'] = cat['upper_state_energy']*1.4387863
        cat['error'] = cat['uncertainty']
        cat['roundedfreq'] = np.round(cat['frequency'], 0)
        cat['line_wavelength'] = 299792458./(cat['frequency']*1.0E6)*1000

        cat['quantum_numbers'] = cat['raw_qn']
        
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

    def __init__(self, listing_entry, custom=False, custom_path=""):

        self.date = listing_entry[0]
        self.id = str(listing_entry[1])
        self.tag = self.id
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
        if custom:
            self.cat = self.calc_derived_params(self.parse_cat(cat_url=open(custom_path, 'r'), local=1), self.metadata)
        else:
            self.cat = self.calc_derived_params(self.parse_cat(self.cat_url), self.metadata)


        self.cat['ll_id'] = self.ll_id
        self.cat['`v3.0`'] = 3

def get_updates():

    def build_database(working_path):
        print('No local database of JPL updates exists, rebuilding...')
        print('Takes a few minutes. Be patient!')
        BASE_URL = "http://spec.jpl.nasa.gov"

        # Pull new update list
        update_page = urllib2.urlopen(BASE_URL+"/ftp/pub/catalog/catdir.html")
        date_formats = ['%b. %Y', '%B %Y']

        updates = []

        inTable = False

        for line in update_page:

            if '<PRE>' in line:
                inTable = True
                continue 

            elif '</PRE>' in line:
                break

            if inTable:
                entry = line.split()

                # Scrape ID number and documentation url and name
                id_num = int(entry[0]) 
                doc_url = BASE_URL+re.findall(r'(?:/ftp/pub/catalog/doc/d)\d*(?:.cat)', line)[0]

                end_bound = entry.index('<A')
                name = ' '.join(entry[1:end_bound-2])
                
                # Open documentation URL and read out date 
                try: 
                    for line in urllib2.urlopen(doc_url).read().split('\n'):
                        if 'Date:' in line:              
                                date_line = line.split()
                                # Now let's parse the date... there are lots of exceptions, so this is gonna be spaghetti code
                                date = ' '.join(date_line[2:3+date_line[3:].index('&')]).strip('&').strip()

                                for fmt in date_formats:
                                    try:
                                        parsed_date = time.strptime(date, fmt)
                                        break
                                    except ValueError:
                                        pass
                        
                except urllib2.HTTPError: # TeX file doesn't exist
                    parsed_date = time.strptime('1900/01', '%Y/%m')

                print [time.strftime('%Y/%m', parsed_date),id_num, name]
                updates.append([time.strftime('%Y/%m', parsed_date),id_num, name])

        update_page.close()

        sorted_updates = sorted(updates, key=lambda x:x[0], reverse=True)

        # Write delimited file for database
        with open(working_path+'/jpl_updates.db', 'w') as db_buffer:
            for entry in sorted_updates:
                db_buffer.write('%s :: %s :: %s \n'%(entry[0],entry[1],entry[2]))

        return sorted_updates


    working_path = os.path.dirname(os.path.realpath(__file__))

    # First, let's check if update database exists
    if os.path.exists(working_path+'/jpl_updates.db'):

        msg = 'JPL listing database exists locally, and was created on %s. Would you like to use it, or update it?'%time.ctime(os.path.getctime(working_path+'/jpl_updates.db'))
        title = 'JPL Updates'
        choices = ['Continue', 'Update']
        update_or_not_update = eg.buttonbox(msg=msg, title=title,choices=choices, default_choice='Continue')
        if update_or_not_update == 'Continue':

            updates = []
            with open(working_path+'/jpl_updates.db', 'r') as inp_buffer:
                for line in inp_buffer:
                    elements = [x.strip() for x in line.split(' :: ')]
                    elements[1] = int(elements[1])
                    updates.append(elements)
                    
            return updates
        else: 
            return build_database(working_path)

    
    else: # Gotta build the database 
        return build_database(working_path)

        

    # BASE_URL = "http://spec.jpl.nasa.gov/ftp/pub/catalog"

    # # Pull new update list
    # update_page = urllib2.urlopen(BASE_URL+"/catdir.html")

    # i = 0
    # updates = []
    # for line in update_page:
    #     print line
    #     # if i == 0:
    #     #     i += 1
    #     #     continue
    #     # elif line != '\n':
    #     #     temp = line.split()
    #     #     updates.append([time.strptime(temp[0], '%Y/%m/%d'), int(temp[1]), temp[2]])

    # update_page.close()
    # return updates

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

    SPECIES_ID = entry[0]
    sql_cur.execute("SHOW columns FROM species_metadata")
    db_meta_cols = [tup[0] for tup in sql_cur.fetchall()]
    sql_cur.execute("SELECT * from species_metadata WHERE species_id=%s", (SPECIES_ID,))


    results = sql_cur.fetchall()
    MetadataMalformed = False 


    if len(results) == 1:
        db_meta = results[0]
        db_meta = {key:value for key, value in zip(db_meta_cols, db_meta)}
    
    elif len(results) > 1 and any([res[4] for res in results]):  # There's more than one linelist associated with the chosen species_id
        chc = ['date: %s \t list: %s \t v2.0: %s \t v3.0: %s' % (a[4], a[55], a[57], a[59]) for a in results]
        print('Linelist choices: ', chc)
        user_chc = eg.choicebox("Choose an entry to update (CDMS linelist = 10)", "Entry list", chc)
        idx = 0
        for i, entry in enumerate(chc):
            if user_chc == entry:
                idx = i
                break
        db_meta = results[idx]
        db_meta = {key:value for key, value in zip(db_meta_cols, db_meta)}
    
    else: # Species exists but there are no metadata entries, so we can have to populate a new one
        db_meta = {}
        MetadataMalformed = True
        for i, col_name in enumerate(db_meta_cols):
            if col_name in mol.metadata.keys():
                db_meta[col_name] = mol.metadata[col_name]
            else:
                continue
        mol.metadata['LineList'] = mol.ll_id
        mol.metadata['species_id_noparens'] = mol.s_name_noparens

    #else: # len(results) is 0, so species exists, but metadata is missing


    if len(results) >= 1:  
        metadata_push_answer = eg.buttonbox(msg='Do you want to APPEND or REPLACE a new metadata entry, or DO NOTHING? Do nothing if you are merely adding a hyperfine linelist to an existing entry.', choices=['APPEND', 'REPLACE', 'DO NOTHING'])
        if metadata_push_answer == 'APPEND':
            push_metadata_flag = 'APPEND'
        elif metadata_push_answer == 'REPLACE':
            push_metadata_flag = 'REPLACE'
        else:
            push_metadata_flag = 'NO'
    else:
        push_metadata_flag = 'APPEND'

    append_lines = eg.buttonbox(msg='Do you want to append the linelist, or replace the current linelist in the database?', choices=['Append', 'Replace'])
    if append_lines == 'Append' or not append_lines:
        append_lines = True
    elif append_lines == 'Replace':
        append_lines = False

    try:
        if db_meta['LineList'] != mol.ll_id:
            mol.metadata['LineList'] = mol.ll_id

    except KeyError: # Only catches when species exists but metadata doesn't
        mol.metadata['Linelist'] = mol.ll_id
        db_meta['LineList'] = mol.ll_id

    mol.metadata['v1_0'] = '0'
    mol.metadata['v2_0'] = '0'
    mol.metadata['v3_0'] = '3'
    #mol.metadata['v4_0'] = '4'
        
    new_name = eg.enterbox(msg="Do you want to change the descriptive metadata molecule name? "
                                "Leave blank otherwise. Current name is %s"
                            % mol.metadata['Name'], title="Metadata Name Change")
    if new_name is not '':
        mol.metadata['Name'] = new_name
    elif not MetadataMalformed:
        mol.metadata['Name'] = db_meta['Name']    

    # mol.metadata['Ref1'] = mol.metadata.pop('Ref1')

    mol.metadata['Ref20'] = mol.meta_url
    # meta_fields = ['%s \t %s' %(a[0],a[1]) for a in zip(db_meta_cols, db_meta) if 'Ref' not in a[0]]

    sql_cur.execute("SHOW columns FROM species")

    db_species_cols = [tup[0] for tup in sql_cur.fetchall()]
    sql_cur.execute("SELECT * from species WHERE species_id=%s", (SPECIES_ID,))
    db_species = sql_cur.fetchall()[0]


    if db_meta['LineList'] != mol.ll_id or MetadataMalformed:
        species_entry_dict = {key: value for (key,value) in [(db_species_cols[i], val) for i, val in enumerate(db_species)]}
        ism_set = ('ism_hotcore', 'ism_diffusecloud', 'comet', 'extragalactic', 'known_ast_molecules')
        ism_set_dict = {key: value for (key, value) in [(key, species_entry_dict[key]) for key in ism_set]}
        if any([val == '1' for val in ism_set_dict.values()]):
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

    if db_meta['LineList'] == mol.ll_id or not MetadataMalformed:
        metadata_to_push = {}
        for i, col_name in enumerate(db_meta_cols):
            if col_name in mol.metadata.keys():
                metadata_to_push[col_name] = mol.metadata[col_name]
            #elif db_meta[col_name] is not None:
            #    metadata_to_push[col_name] = db_meta[col_name]
            else: # Hacky fix to ensure clean columns -- this cleans up columns with no default values that don't allow NULL or are values that aren't otherwise filled in by this routine
                if col_name in ['ism', 'species_id', 'LineList']:
                    metadata_to_push[col_name] = db_meta[col_name]

    else:
        metadata_to_push = mol.metadata

    # Generate new unique ID for metadata entry
    try:
        sql_cur.execute('SELECT MAX(line_id) FROM species_metadata')
    except: # line_id doesn't exist in the database so just skip this step
        pass 
    else:
        if push_metadata_flag == 'APPEND':
            try:
                metadata_to_push['line_id'] = str(int(sql_cur.fetchall()[0][0])+1)
            except TypeError: # Gets thrown if there are no metadata entries in the table, thus line_id should be "1". 
                metadata_to_push['line_id'] = 1
        elif push_metadata_flag == 'REPLACE':
            try: 
                metadata_to_push['line_id'] = str(int(sql_cur.fetchall()[0][0]))
            except TypeError: 
                metadata_to_push['line_id'] = 1

    # for key in metadata_to_push:
    #     print '%s: %s' %(key, metadata_to_push[key])

    # QN formatting --- let's just do it on a case-by-case basis
    qn_fmt = mol.cat['qn_code'][0]

    fmtted_QNs = []
    print 'Preparing linelist...'
    # Iterate through rows and add formatted QN
    choice_idx = None
    for idx, row in mol.cat.iterrows():
        format, choice_idx = format_it(qn_fmt, row.filter(regex=re.compile('(qn_)'+'.*?'+'(_)'+'(\\d+)')),
                                       choice_idx=choice_idx)
        fmtted_QNs.append(format)

    mol.cat['resolved_QNs'] = pd.Series(fmtted_QNs, index=mol.cat.index)
    if any(mol.cat['resolved_QNs'] == ''):
        print '======================\n'+'WARNING: The parsing code did not parse the quantum numbers. This may be due to the CAT QN code not being programmed into QNParser, but also might be due to you choosing not to parse the QNs.\n Please contact your friendly code developer (Nathan) if you need help in this regard.\n'+'======================'
    

    if metadata_to_push['ism'] == 1:
        mol.cat['Lovas_NRAO'] = 1

    # Prep linelist for submission to database
    sql_cur.execute("SHOW columns FROM main")
    ll_splat_col_list = [tup[0] for tup in sql_cur.fetchall()]
    ll_col_list = mol.cat.columns.values.tolist()

    final_cat = mol.cat[[col for col in ll_splat_col_list if col in ll_col_list]]

    return final_cat, metadata_to_push, push_metadata_flag, append_lines 

def new_molecule(mol, sql_conn=None):

    sql_cur = sql_conn.cursor()
    #sql_cur.execute("USE splattest")

    # ----------------------------
    # METADATA ADD
    # ----------------------------

    # Generate array of all columns from species_metadata so we can fill them in as we go
    sql_cur.execute("SHOW columns FROM species_metadata")
    db_meta_cols = [tup[0] for tup in sql_cur.fetchall()]
    metadata_to_push = {}

    # Fills in metadata dictionary with the column array we generated above as a list of keys for the metadata dict
    for i, col_name in enumerate(db_meta_cols):
        if col_name in mol.metadata.keys():
            metadata_to_push[col_name] = mol.metadata[col_name]
        else:
            continue

    # Generate new species_id
    sql_cur.execute('SELECT MAX(species_id) FROM species')
    try: # species_id is +1 of the largest species_id in the species table
        metadata_to_push['species_id'] = str(int(sql_cur.fetchall()[0][0])+1)
    except TypeError: # Gets thrown if there are no species in the table; therefore species ID should be "1".
        metadata_to_push['species_id'] = "1"

    metadata_to_push['v1_0'] = '0'
    metadata_to_push['v2_0'] = '0'
    metadata_to_push['v3_0'] = '3'
    #metadata_to_push['v4_0'] = '0'
    metadata_to_push['Ref20'] = mol.meta_url
    metadata_to_push['LineList'] = mol.ll_id

    new_name = eg.enterbox(msg="Do you want to change the descriptive metadata molecule name? Leave blank otherwise. Current name is %s"
                               % metadata_to_push['Name'], title="Metadata Name Change")
    if new_name is not '':
        metadata_to_push['Name'] = new_name

    # Generate new unique ID for metadata entry
    try:
        sql_cur.execute('SELECT MAX(line_id) FROM species_metadata')
    except: # line_id doesn't exist in the database so just skip this step
        pass 
    else: 
        try:
            metadata_to_push['line_id'] = str(int(sql_cur.fetchall()[0][0])+1)
        except TypeError: # Gets thrown if there are no metadata entries in the table, thus line_id should be "1". 
            metadata_to_push['line_id'] = 1

    tag_num = mol.id
    tag_prefix = ''.join(('0',)*(6-len(tag_num)))+tag_num[:(len(tag_num)-3)]
    cmd = "SELECT SPLAT_ID FROM species " \
        "WHERE SPLAT_ID LIKE '%s%%'" % tag_prefix
    print 'Tag prefix, '+tag_prefix    
    sql_cur.execute(cmd)
    splat_id_list = sql_cur.fetchall()

    # If there's more than one species in the splatalogue list with the same molecular mass, this finds the minimum value necessary to make it a unique ID
    if len(splat_id_list) > 0:
        max_id = max([int(x[0][3:]) for x in splat_id_list])
        if max_id < 9:
            splat_id = mol.tag[:3] + '0'+str(max_id+1)
        else:
            splat_id = mol.tag[:3] + str(max_id+1)
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
        if not species_choices[idx]:
            pass
        else:
            species_to_push[key] = species_choices[idx]
        idx += 1

    ism_set = ('ism_hotcore', 'ism_diffusecloud', 'comet', 'extragalactic', 'known_ast_molecules')
    ism_set_dict = {key: value for (key, value) in [(key, species_to_push[key]) for key in ism_set]}
    if any([val == '1' for val in ism_set_dict.values()]):
        metadata_to_push['ism'] = 1
        mol.cat['Lovas_NRAO'] = 1
    else:
        metadata_to_push['ism'] = 0

    ism_overlap_tags = ['species_id', 'ism_hotcore', 'comet', 'planet', 'AGB_PPN_PN', 'extragalactic']
    for tag in ism_overlap_tags:
        metadata_to_push[tag] = species_to_push[tag]

    # Format quantum numbers
    qn_fmt = mol.cat['qn_code'][0]
    fmtted_QNs = []

    # Iterate through rows and add formatted QN
    choice_idx = None
    for idx, row in mol.cat.iterrows():
        fmt, choice_idx = format_it(qn_fmt, row.filter(regex=re.compile('(qn_)'+'.*?'+'(_)'+'(\\d+)')),
                                       choice_idx=choice_idx)
        fmtted_QNs.append(fmt)

    mol.cat['resolved_QNs'] = pd.Series(fmtted_QNs, index=mol.cat.index)
    if any(mol.cat['resolved_QNs'] == ''):
        print '======================\n'+'WARNING: The parsing code did not parse the quantum numbers. This may be due to the CAT QN code not being programmed into QNParser, but also might be due to you choosing not to parse the QNs.\n Please contact your friendly code developer (Nathan) if you need help in this regard.\n'+'======================'
    

    # Prep linelist for submission to database
    sql_cur.execute("SHOW columns FROM main")
    ll_splat_col_list = [tup[0] for tup in sql_cur.fetchall()]
    ll_col_list = mol.cat.columns.values.tolist()
    final_cat = mol.cat[[col for col in ll_splat_col_list if col in ll_col_list]]

    return final_cat, species_to_push, metadata_to_push

def push_molecule(db, ll, spec_dict, meta_dict, push_metadata_flag='APPEND', append_lines_flag=False, update=0):


    for key in meta_dict:
        print key, '\t', meta_dict[key]

    print 'Converting linelist for SQL insertion...'
    ll['species_id'] = meta_dict['species_id']
    ll = ll.where(pd.notnull(ll),None)
    ll_dict = [tuple(x) for x in ll.to_numpy()]

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
        if meta_dict['ism'] == 1:
            print 'Removing previous Lovas NRAO recommended frequencies, if necessary...'
            cursor.execute('UPDATE main SET Lovas_NRAO = 0 WHERE species_id=%s', (meta_dict['species_id'],))

        if push_metadata_flag == 'REPLACE':
            print 'Removing duplicate metadata, if neeeded...' # In case of duplicate data
            cursor.execute('DELETE FROM species_metadata WHERE species_id=%s AND LineList=%s AND v3_0 = 3', (meta_dict['species_id'], meta_dict['LineList']))

        if not append_lines_flag:
            print 'Removing previous current version lines if available...' # Prevents doubling of entries, such as in case of an accidental update
            cursor.execute('DELETE FROM main WHERE species_id=%s AND `v3.0`=3 AND ll_id=%s', (meta_dict['species_id'], meta_dict['LineList']))

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

    if (update == 0) or (update == 1 and push_metadata_flag in ('APPEND','REPLACE')):
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

def main(db):
    pd.options.mode.chained_assignment = None

    # Get JPL update listing
    listing = get_updates()
    choice_list = ["%s  %s  %s" % (x[0], x[1], x[2]) for x in listing]
    JPLLoop = True
    while JPLLoop:

        choice = eg.choicebox('Choose a Molecule to Update', 'Choice', choice_list)
        choice_idx = 0
        for idx, ent in enumerate(listing):
            if int(choice.split()[1]) == ent[1]:
                choice_idx = idx
        custom_cat_file = eg.buttonbox(msg='Would you like to supply a custom CAT file?', choices=['Yes', 'No'])
        if custom_cat_file == 'Yes':
            custom_path = eg.fileopenbox(msg='Please select a CAT file.', title='Custom CAT file')
            cat_entry = JPLMolecule(listing[choice_idx], custom=True, custom_path=custom_path)
            print cat_entry.cat
        else:
            cat_entry = JPLMolecule(listing[choice_idx])

        tag_num = str(cat_entry.id)
        print tag_num, ''.join(('0',)*(6-len(tag_num)))+cat_entry.id[:(len(tag_num)-3)]
        cmd = "SELECT * FROM species " \
             "WHERE SPLAT_ID LIKE '%s%%'" % (''.join(('0',)*(6-len(tag_num)))+cat_entry.id[:len(tag_num)-3],)

        cursor = db.cursor()
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
            push_molecule(db, linelist, species_final, metadata_final, update=0)

        else:  # Molecule already exists in Splatalogue database
            linelist, metadata_final, push_metadata_flag, append_lines_flag = process_update(cat_entry, res[int(choice2[0:5])], db)
            push_molecule(db=db, ll=linelist, spec_dict={}, meta_dict=metadata_final, push_metadata_flag=push_metadata_flag, append_lines_flag=append_lines_flag, update=1)

        choice3 = eg.buttonbox(msg='Do you want to update another JPL entry?', choices=['Yes', 'No'])

        if choice3 == 'No':
            JPLLoop = False
