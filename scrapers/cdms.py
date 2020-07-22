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
import sys
import os

class CDMSMolecule:

    def parse_cat(self, cat_url=None, local=0):
        """ This function takes a Pickett prediction file (a so-called "CAT" file) and converts it into a Pandas DataFrame. 
        This code should work for any well-formed CAT file, and works for all CDMS and JPL entries, as well as custom, user-generated
        CAT files. It is unclear if there are any edge cases this misses as CAT files are fairly rigorous in their formatting.
        """
        num_qns = 0

        def l_to_idx(letter):  # For when a QN > 99
                _abet = 'abcdefghijklmnopqrstuvwxyz'
                return next((z for z, _letter in enumerate(_abet) if _letter == letter.lower()), None)

        # Generates a parsing string formatter for CAT file rows 
        def make_parser(fieldwidths):
            def accumulate(iterable):
                total = next(iterable)
                yield total
                for value in iterable:
                    total += value
                    yield total

            cuts = tuple(cut for cut in accumulate(abs(fw) for fw in fieldwidths))
            pads = tuple(fw < 0 for fw in fieldwidths)  # bool for padding
            flds = tuple(izip_longest(pads, (0,)+cuts, cuts))[:-1]  # don't need final one

            def parse(lyne): return tuple(lyne[i:j] for pad, i, j in flds if not pad)

            parse.size = sum(abs(fw) for fw in fieldwidths)
            parse.fmtstring = ' '.join('{}{}'.format(abs(fw), 'x' if fw < 0 else 's') for fw in fieldwidths)

            return parse

        widths = [13, 8, 8, 2, 10, 3, 7, 4]  # Character widths for each CAT file entry, not including quantum numbers
        w_sum = sum(widths)
        parser = make_parser(tuple(widths))
        try:
            print '========\n'+ cat_url.name + '\n========\n'
        except AttributeError: # cat_url is a string:
            print '========\n'+ cat_url + '\n========\n'
        if local == 0:
            cat_inp = urllib2.urlopen(cat_url).read()

            # Save cat_inp to working directory
            with open(self.working_directory+'/'+self.tag+"_"+self.name+'.cat','wb') as otpt:
                otpt.write(cat_inp)

            # Split by line to ready CAT file for parse
            cat_inp = cat_inp.split('\n')
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
            if num_qns == 0:  # Get number of quantum numbers per state
                try:
                    num_qns = int(row[7][-1])
                except IndexError: # You should never end up here unless there's a crazy edge case or a badly formed CAT file.
                    print row
                    raise 

            # This is a really hacky way to parse the quantum numbers, but it's robust and has worked without a hitch so far. 
            # Uses a series of if-else statements to iterate through the QNs in a linear fashion
            raw_qn = row[-1].rstrip()
            if len(raw_qn) > max_qn_length:
                max_qn_length = len(raw_qn)
            qns = qn_parser(row[-1])  # splits QN entry into pairs
            up_done = False # Boolean for being done with the upper state QNs
            in_middle = False # Are we in the character gap between the upper and lower state QNs?
            down_done = False # Boolean for being down with the lower state QNs
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

                if not up_done and not in_middle: # Still in the upper state
                    try:
                        qns_up.append(int(val))
                    except ValueError: # In case it isn't an integer quantum number
                        try:
                            if val.strip() == '+':  # For parity symbols in CH3OH, for instance
                                qns_up.append(1)
                            elif val.strip() == '-':
                                qns_up.append(-1)
                            elif val.strip() == '':  # No parity symbol?
                                qns_up.append(0)
                            elif re.search('[A-Z]', val.strip()):  # QN > 99
                                temp = list(val)
                                qns_up.append((100 + (l_to_idx(temp[0]))*10) + int(temp[1]))
                            elif re.search('[a-z]', val.strip()): # QN < -9, e.g. CDMS CD3CN entry
                                temp = list(val)
                                qns_up.append((-10 - l_to_idx(temp[0])*10) - int(temp[1]))
                        except TypeError: # You shouldn't ever get here, but just in case...
                            print i, val, [x.strip() for x in qns]
                            raise

                if up_done and (not down_done and not in_middle): # Hit the beginning of the lower states
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
                            elif re.search('[A-Z]', val.strip()):  # QN > 99
                                temp = list(val)
                                qns_down.append((100 + (l_to_idx(temp[0]))*10) + int(temp[1]))
                            elif re.search('[a-z]', val.strip()): # QN < -9, e.g. CDMS CD3CN entry
                                temp = list(val)
                                qns_down.append((-10 - l_to_idx(temp[0])*10) - int(temp[1]))
                        except TypeError:
                            print i, val, [x.strip() for x in qns]
                            raise
            try:
                parsed_list.append([float(s.strip()) for s in row[:-1]] + [raw_qn] + [qns_up, qns_down])
            except ValueError:  # Get blank line or other issue?
                line = [s.strip() for s in row[:-1]]
                if not line[0]: # Blank line
                    continue
                elif any([char.isalpha() for char in line[5]]): # Upper state degeneracy > 99:
                    line[5] = 1000 + l_to_idx(line[5][0])*100 + int(line[5][1:])
                    parsed_list.append([float(col) for col in line] + [raw_qn] + [qns_up, qns_down])

        # Generates columns for dataframe that correlate with columns in main
        dtypes = [('frequency', 'f8'), ('uncertainty', 'f8'), ('intintensity', 'f8'), ('degree_freedom', 'i4'),
                  ('lower_state_energy', 'f8'), ('upper_state_degeneracy', 'i4'), ('molecule_tag', 'i4'),
                  ('qn_code', 'i4'), ('raw_qn', 'S%i'%max_qn_length)]
        dtypes.extend([('qn_up_%s' % i, 'i4') for i in range(len(parsed_list[0][-2]))])
        dtypes.extend([('qn_dwn_%s' % i, 'i4') for i in range(len(parsed_list[0][-2]))])

        final_list = []
        
        for row in parsed_list:
            final_list.append(tuple(row[:-2]+row[-2]+row[-1]))

        nplist = np.zeros((len(final_list),), dtype=dtypes)
        nplist[:] = final_list

        return pd.DataFrame(nplist)
    

    # Not used but useful in case you want to append custom lines to a linelist
    def add_row(self, row_name, value): 
        
        @staticmethod
        def add(cat, row, val):
            cat[row] = val
            return cat
        
        add(self.cat, row_name, value)

    def parse_formula(self, input_formula):

        common_isotopes = ['13C', '15N','18O','17O','33S','34S','36S', '40Ar', '26Al','30Si','29Si','65Cu','52Cr','66Zn', '68Zn','35Cl','36Cl','37Cl','39K', '40K', '41K','46Ti','50Ti']

        
        # Get rid of any junk after a comma, usually some state descriptor
        if ',' in input_formula:
            output_formula = input_formula.split(',')[0]
            leftovers = ' '.join(input_formula.split(',')[1:])
        else: 
            output_formula = input_formula
            leftovers = ''

        for isotope in common_isotopes:
            # Do isotopes first
            if isotope in output_formula:
                num_part, element = re.findall(r'[^\W\d_]+|\d+', isotope)
                output_formula = output_formula.replace(isotope, '<sup>'+num_part+'</sup>'+element)
        # Replace every other number with <sub>
        atoms_with_multiplicity = re.findall(r'[A-Z][a-z]*\d+', output_formula)
        for atom in atoms_with_multiplicity:
            element, num_part = re.findall(r'[^\W\d_]+|\d+', atom)
            output_formula = output_formula.replace(atom, element+'<sub>'+num_part+'</sub>',1)

        # Add <sub> to any parenthesized subgroup of the formula
        parenthetical_subgroups = re.findall(r'\)\d+', output_formula)
        for subgroup in parenthetical_subgroups:
            output_formula = output_formula.replace(subgroup, ')'+'<sub>'+subgroup.split(')')[1]+'</sub>')

        # Now, let's build s_name and s_name_noparens
        s_name = output_formula.replace('<sup>','(').replace('</sup>', ')').replace('<sub>','').replace('</sub>','')
        s_name_noparens = s_name.replace('(','').replace(')','')
        return output_formula+leftovers, s_name+leftovers, s_name_noparens+leftovers

    # Scrapes CDMS site to generate metadata 
    def get_metadata(self, meta_url):
        print self.name
        metadata = {}  # Dictionary for metadata, keys are consistent with columns in SQL

        # Dictionaries to connect string values in CDMS metadata to SQL columns
        q_temps = {'2000.': 'Q_2000_', '1000.': 'Q_1000_', '500.0': 'Q_500_0', '300.0': 'Q_300_0',
                   '225.0': 'Q_225_0', '150.0': 'Q_150_0', '75.00': 'Q_75_00', '37.50': 'Q_37_50',
                   '18.75': 'Q_18_75', '9.375': 'Q_9_375', '5.000': 'Q_5_00', '2.725': 'Q_2_725'}
        dipoles = {'a / D': 'MU_A', 'b / D': 'MU_B', 'c / D': 'MU_C'}

        # Initialize scraper
        meta_page = urllib2.urlopen(meta_url)
        meta_page_read = meta_page.read()

        with open(self.working_directory+'/'+self.tag+"_"+self.name+'.html','wb') as otpt:
            otpt.write(meta_page_read)

        soup = BeautifulSoup(meta_page_read, 'lxml')

        # Grab formula
        formula = soup.find_all('caption')[0].get_text().split('\n')[0].encode('utf-8')

        # Need to add lit data / dipoles etc

        meta_page.close()

        table = soup.find_all('tr')
        for entry in table:  # Right now it seems the best way is to brute force this
            temp = entry.get_text()

            metadata['Name'] = self.name
            metadata['Date'] = time.strftime('%b. %Y', self.date)
            if 'Contributor' in temp:
                if self.ll_id == '10':
                    metadata['Contributor'] = 'H. S. P. Mueller'
                else:
                    metadata['Contributor'] = temp.split('Contributor')[1].encode('utf-8')

            # Pull out spin-rotation partition function values
            for key in q_temps:
                if 'Q(%s)' % key in temp:
                    metadata[q_temps[key].encode('utf-8')] = temp.split('Q(%s)' % key)[1].encode('utf-8')

            def value_check(x): return any(i.isdigit() for i in x)

            def pull_float(x): return re.findall(r'\d+.\d+', x)

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
        # Some hard-coded replace statements for weird things that don't parse correctly when displaying the metadata
        metadata['Ref1'] = metadata["Ref1"].replace('\xc2\x96','-') # Fixes long dashes that Holger sometimes likes to use

        return self.parse_formula(formula), metadata

    # Calculates all derived parameters from data in the CAT file, e.g. lower/upper state energies, sijmu2 values, etc. 
    # Currently does NOT calculate sij values, because of the case-by-case, or even line-by-line, difficulty on how to identify the electric dipole to divide by
    @staticmethod
    def calc_derived_params(cat, metadata):
        try:
            q_spinrot = float(metadata['Q_300_0'])
        except ValueError:  # in case there's multiple numbers
            q_spinrot = float(metadata['Q_300_0'].split('(')[0])
        kt_300_cm1 = 208.50908

        cat['sijmu2'] = 2.40251E4 * 10**(cat['intintensity']) * q_spinrot * (1./cat['frequency']) * \
                        (1./(np.exp(-1.0*cat['lower_state_energy']/kt_300_cm1) -
                             np.exp(-1.0*(cat['frequency']/29979.2458+cat['lower_state_energy'])/kt_300_cm1)))
        cat['aij'] = np.log10(1.16395E-20*cat['frequency']**3*cat['sijmu2']/cat['upper_state_degeneracy'])
        cat['lower_state_energy_K'] = cat['lower_state_energy']*1.4387863
        cat['upper_state_energy'] = cat['lower_state_energy'] + cat['frequency']/29979.2458
        cat['upper_state_energy_K'] = cat['upper_state_energy']*1.4387863
        cat['error'] = cat['uncertainty']
        cat['roundedfreq'] = cat['frequency'].round(0)
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

    def create_directory(self):
        save_path = 'working_molecules/'
        folder_name = 'CDMS_'+self.tag+"_"+self.name+'_'+time.strftime('%b%Y', self.date)

        total_path = save_path+folder_name
        # Check to see if folder already exists; if so, we'll append an integer to it
        if os.path.isdir(total_path):
            # There might be more than 1, so we should add +1 to the tally if so
            dupe_idx = 1
            while os.path.isdir(total_path+'_{:d}'.format(dupe_idx)):
                dupe_idx += 1
            total_path = save_path+folder_name+'_{:d}'.format(dupe_idx)


        try:
            os.makedirs(total_path)
        except OSError:
            print('Creation of directory %s failed' %(total_path,))
        else:
            print('Created working directory for molecular information at: %s' %(total_path,))

        return total_path
        

    def __init__(self, cdms_inp, custom=False, ll_id='10', custom_path="", write_directory=True):
        base_url = "http://cdms.astro.uni-koeln.de"

        self.tag = cdms_inp[0]
        self.name = cdms_inp[1]
        self.date = cdms_inp[2]
        self.cat_url = cdms_inp[3]
        self.meta_url = cdms_inp[4]
        self.ll_id = ll_id
        if write_directory:
            self.working_directory = self.create_directory()
        if custom:
            self.cat = self.parse_cat(cat_url=open(custom_path, 'r'), local=1)
        else:
            self.cat = self.parse_cat(cat_url=base_url+self.cat_url)
        
        (self.formula, self.s_name, self.s_name_noparens), self.metadata = self.get_metadata(base_url+self.meta_url)

        self.cat = self.calc_derived_params(self.cat, self.metadata)
        self.cat['ll_id'] = self.ll_id
        self.cat['`v3.0`'] = '3'

        # Write parsed CAT dataframe to CSV file
        self.cat.to_csv(path_or_buf=self.working_directory+'/'+self.tag+"_"+self.name+'_parsed_cat.csv')
        for key in self.metadata:
            print key, ': ', self.metadata[key]
        



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
        return "{:5} {:10} {:>25} {:>15}".format(it[0], it[1], it[2], time.strftime("%B %Y", it[3]))


def unidrop(x):  # Strips any non-ASCII unicode text from string
    return re.sub(r'[^\x00-\x7F]+', ' ', x)


def pretty_print(comp):
    form = "{:5}\t{:45}\t{:15}\t{:40} {:40}"
    output = form.format(*('Tag', 'Molecule', 'Date', 'Cat Link', 'Metadata Link'))+'\n'
    for row in comp:
        output += form.format(*(row[0], row[1], time.strftime("%B %Y", row[2]), row[3], row[4]))+'\n'
    return output


def pull_updates():

    base_url = "http://cdms.astro.uni-koeln.de"
    page = urllib2.urlopen(base_url+"/classic/entries")
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

    compiled.sort(key=lambda x: x[2], reverse=True) # Sorts by update time, most recent first
    return compiled


def process_update(mol, entry=None, sql_conn=None):

    sql_cur = sql_conn.cursor()

    # ----------------------------
    # METADATA PULL CHECK & UPDATE
    # ----------------------------

    sql_cur.execute("SHOW columns FROM species_metadata")
    db_meta_cols = [tup[0] for tup in sql_cur.fetchall()]
    sql_cur.execute("SELECT * from species_metadata WHERE species_id=%s", (entry[0],))

    results = sql_cur.fetchall()
    if len(results) == 1:
        db_meta = results[0]

    else:  # There's more than one linelist associated with the chosen species_id
        chc = ['date: %s \t list: %s \t v2.0: %s \t v3.0: %s' % (a[3], a[54], a[57], a[58]) for a in results]
        user_chc = eg.choicebox("Choose an entry to update (CDMS linelist = 10)", "Entry list", chc)
        idx = 0
        for i, entry in enumerate(chc):
            if user_chc == entry:
                idx = i
                break
        db_meta = results[idx]

    db_meta = {key:value for key, value in zip(db_meta_cols, db_meta)}
    
    metadata_push_answer = eg.buttonbox(msg='Do you want to append a new metadata entry? For instance, say no if you are merely adding a hyperfine linelist to an existing entry.', choices=['Yes', 'No'])
    if metadata_push_answer == 'Yes':
        push_metadata_flag = True
    else:
        push_metadata_flag = False
    append_lines = eg.buttonbox(msg='Do you want to append the linelist, or replace the current linelist in the database?', choices=['Append', 'Replace'])
    if append_lines == 'Append' or not append_lines:
        append_lines = True
    elif append_lines == 'Replace':
        append_lines = False

    if db_meta['LineList'] != mol.ll_id:
        mol.metadata['LineList'] = mol.ll_id
        # Only entry in database isn't from the linelist of the entry that user wants to update
    mol.metadata['v1_0'] = '0'
    mol.metadata['v2_0'] = '0'
    mol.metadata['v3_0'] = '3'
    #mol.metadata['v4_0'] = '4'
        
    new_name = eg.enterbox(msg="Do you want to change the descriptive metadata molecule name? "
                                "Leave blank otherwise. Current name is %s"
                            % mol.metadata['Name'], title="Metadata Name Change")
    if new_name is not '':
        mol.metadata['Name'] = new_name
    else:
        mol.metadata['Name'] = db_meta['Name']
    
    # Check to see first column to place reference info
    # ref_idx = 1
    # while True:
    #     if not db_meta['Ref%s'%ref_idx]:
    #         break
    #     ref_idx += 1

    #mol.metadata['Ref%s'%ref_idx] = mol.metadata.pop('Ref1')

    mol.metadata['Ref20'] = '<a href=' + "\"" + 'http://www.astro.uni-koeln.de'+mol.meta_url + "\"" + " target=\"_blank\">CDMS Entry</a>"
    mol.metadata['Ref19'] = mol.metadata['Ref20'].replace('file=e','file=c')
    mol.metadata['Ref19'] = mol.metadata['Ref19'].replace('Entry', 'CAT file')
    # meta_fields = ['%s \t %s' %(a[0],a[1]) for a in zip(db_meta_cols, db_meta) if 'Ref' not in a[0]]

    sql_cur.execute("SHOW columns FROM species")

    db_species_cols = [tup[0] for tup in sql_cur.fetchall()]
    sql_cur.execute("SELECT * from species WHERE species_id=%s", (db_meta['species_id'],))
    db_species = sql_cur.fetchall()[0]

    if db_meta['LineList'] != mol.ll_id:
        species_entry_dict = {key: value for (key, value) in [(db_species_cols[i], val) for i, val
                                                              in enumerate(db_species)]}

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

    if db_meta['LineList'] == mol.ll_id:
        metadata_to_push = {}
        for i, col_name in enumerate(db_meta_cols):
            if col_name in mol.metadata.keys():
                metadata_to_push[col_name] = mol.metadata[col_name]
            elif db_meta[col_name] is not None:
                metadata_to_push[col_name] = db_meta[col_name]
            else:
                continue
    else:
        metadata_to_push = mol.metadata

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
    # for key in metadata_to_push:
    #     print '%s: %s' %(key, metadata_to_push[key])

    # QN formatting --- let's just do it on a case-by-case basis
    qn_fmt = mol.cat['qn_code'][0]

    fmtted_qns = []
    print 'Preparing linelist...'
    # Iterate through rows and add formatted QN
    choice_idx = None
    for idx, row in mol.cat.iterrows():
        format, choice_idx = format_it(qn_fmt, row.filter(regex=re.compile('(qn_)'+'.*?'+'(_)'+'(\\d+)')),
                                       choice_idx=choice_idx)
        fmtted_qns.append(format)

    # Push formatted quantum numbers to linelist
    mol.cat['resolved_QNs'] = pd.Series(fmtted_qns, index=mol.cat.index)

    if metadata_to_push['ism'] == 1:
        mol.cat['Lovas_NRAO'] = 1
    else:
        mol.cat['Lovas_NRAO'] = 0
        # mol.cat['Lovas_NRAO'] = pd.Series(np.ones(len(mol.cat.index)), index=mol.cat.index)
    
    # Prep linelist for submission to
    sql_cur.execute("SHOW columns FROM main")
    ll_splat_col_list = [tup[0] for tup in sql_cur.fetchall()]
    ll_col_list = mol.cat.columns.values.tolist()
    final_cat = mol.cat[[col for col in ll_splat_col_list if col in ll_col_list]]
    
    return final_cat, metadata_to_push, push_metadata_flag, append_lines


def new_molecule(mol, sql_conn=None):

    sql_cur = sql_conn.cursor()

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

    # Odds and ends; we default to v4_0 for splat_2019    
    metadata_to_push['v1_0'] = '0'
    metadata_to_push['v2_0'] = '0'
    metadata_to_push['v3_0'] = '3'
    #metadata_to_push['v4_0'] = '4'
    metadata_to_push['Ref20'] = '<a href=' + "\"" + 'http://cdms.astro.uni-koeln.de'+mol.meta_url + "\"" + " target=\"_blank\">CDMS Entry</a>"
    metadata_to_push['Ref19'] = metadata_to_push['Ref20'].replace('cdmsinfo?file=e','cdmssearch?file=c').replace('Entry', 'CAT file')
    metadata_to_push['LineList'] = mol.ll_id

    # If you want to give the molecule a pretty new, or non-standard, name
    new_name = eg.enterbox(msg="Do you want to change the descriptive metadata molecule name?"
                               " Leave blank otherwise. Current name is %s"
                               % metadata_to_push['Name'], title="Metadata Name Change")
    if new_name is not '':
        metadata_to_push['Name'] = new_name

    # Generates new splat_id from the molecular mass
    cmd = "SELECT SPLAT_ID FROM species " \
        "WHERE SPLAT_ID LIKE '%s%%'" % str(mol.tag[:3])
    sql_cur.execute(cmd)
    splat_id_list = sql_cur.fetchall()

    # If there's more than one species in the splatalogue list with the same molecular mass, this finds the minimum value necessary to make it a unique ID
    if len(splat_id_list) > 0:
        max_id = max([int(x[0][3:]) for x in splat_id_list])
        if max_id < 10:
            splat_id = mol.tag[:3] + '0'+str(max_id+1)
        else:
            splat_id = mol.tag[:3] + str(max_id+1)
    else:
        splat_id = mol.tag[:3] + '01'

    # Self-explanatory: This is where we build the species row entry
    species_to_push = OrderedDict([('species_id', metadata_to_push['species_id']),
                                   ('name', mol.formula), ('chemical_name', None), ('s_name', mol.s_name),
                                   ('s_name_noparens', mol.s_name_noparens),
                                   ('SPLAT_ID', splat_id), ('atmos', '0'), ('potential', '1'), ('probable', '0'),
                                   ('known_ast_molecules', '0'), ('planet', '0'), ('ism_hotcore', '0'),
                                   ('ism_diffusecloud', '0'), ('comet', '0'), ('extragalactic', '0'),
                                   ('AGB_PPN_PN', '0'), ('SLiSE_IT', '0'), ('Top20', '0')])

    species_choices_fieldnames = ['%s (%s)' % (key, value) for key, value in species_to_push.items()]
    species_choices = eg.multenterbox('Set species entries', 'species entry', species_choices_fieldnames)

    # Ensures we keep a 1-1 correspondence between species_to_push and users' entries from above
    for idx, key in enumerate(species_to_push):
        if not species_choices[idx]: # If user entry is empty, we do nothing
            pass
        else:
            species_to_push[key] = species_choices[idx]

    # Interstellar values; instantiated separately so we can correlate between metadata and species ISM tags 
    ism_set = ('ism_hotcore', 'ism_diffusecloud', 'comet', 'extragalactic', 'known_ast_molecules')
    ism_set_dict = {key: value for (key, value) in [(key, species_to_push[key]) for key in ism_set]}

    # If it's an ISM detection, we probably want to make the freqs NRAO recommended ('Lovas_NRAO' column in main). 
    # This may need to be changed in the future, but this was decided under agreement with A. Remijan 
    if any([val == '1' for val in ism_set_dict.values()]):
        metadata_to_push['ism'] = 1
        mol.cat['Lovas_NRAO'] = 1 # Sets all lines in linelist to be NRAO recommended if it's a detected molecule
    else:
        metadata_to_push['ism'] = 0

    # ISM tag overlap between metadata and species tables
    ism_overlap_tags = ['ism_hotcore', 'comet', 'planet', 'AGB_PPN_PN', 'extragalactic', 'species_id',]
    for tag in ism_overlap_tags:
        metadata_to_push[tag] = species_to_push[tag]

    # Format quantum numbers
    qn_fmt = mol.cat['qn_code'][0]
    fmtted_qns = []

    # Iterate through rows and add formatted QN
    choice_idx = None
    for idx, row in mol.cat.iterrows():
        format, choice_idx = format_it(qn_fmt, row.filter(regex=re.compile('(qn_)'+'.*?'+'(_)'+'(\\d+)')),
                                       choice_idx=choice_idx) # See QNFormat.py for this function
        fmtted_qns.append(format)

    # Push formatted quantum numbers to linelist
    mol.cat['resolved_QNs'] = pd.Series(fmtted_qns, index=mol.cat.index)

    # Prep linelist for submission to database
    sql_cur.execute("SHOW columns FROM main")
    ll_splat_col_list = [tup[0] for tup in sql_cur.fetchall()] # Generates a list of columns from the main table
    ll_col_list = mol.cat.columns.values.tolist() # Kick it out of the dataframe so we can throw it into a list, which mysqldb can handle
    final_cat = mol.cat[[col for col in ll_splat_col_list if col in ll_col_list]] # Gets rid of dataframe columns NOT in the main column list

    return final_cat, species_to_push, metadata_to_push


def push_molecule(db, ll, spec_dict, meta_dict, push_metadata_flag=True, append_lines_flag=False, update=0):

    # push_molecule() takes all the prepared entry data from either new_molecule() or process_update() and pushes it to the database

    for key in meta_dict: # For your viewing pleasure
        print key, '\t', meta_dict[key]

    print 'Converting linelist for SQL insertion...'
    ll['species_id'] = meta_dict['species_id'] # Copies species_id from metadata, where it's first generated, into the linelist
    ll = ll.where(pd.notnull(ll),None)
    ll_dict = [tuple(x) for x in ll.to_numpy()]

    num_entries = len(ll_dict)
    #ll_dict = [(None if pd.isnull(y) else y for y in x) for x in ll.to_numpy()] # Ensures NULL values for empty rows

    # Create new species entry in database

    # Helper functions to generate well-formed SQL INSERT statements
    def placeholders(inp): return ', '.join(['%s'] * len(inp))

    def placeholders_err(inp): return ', '.join(['{}'] * len(inp))

    def columns(inp): return ', '.join(inp.keys())

    def query(table, inp): return "INSERT INTO %s ( %s ) VALUES ( %s )" % (table, columns(inp), placeholders(inp))

    def query_err(table, inp): "INSERT INTO %s ( %s ) VALUES ( %s )" % \
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

        # Replace old NRAO recommended frequency tags so the updated data set becomes the new NRAO rec
        if meta_dict['ism'] == 1:
            print 'Removing previous Lovas NRAO recommended frequencies, if necessary...'
            cursor.execute('UPDATE main SET Lovas_NRAO = 0 WHERE species_id=%s', (meta_dict['species_id'],))

        if push_metadata_flag:
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

    ### This commented block of code enables replacement of older metadata content in species_metadata if updating an entry;
    ### current behavior is to merely append the new metadata content to species_metadata and preserve older versions. 
    # if update:
    #     cursor = db.cursor()
    #     print 'Removing original metadata entry for replacing with new data...'
    #     cursor.execute('DELETE from species_metadata WHERE species_id=%s AND v1_0=%s AND v2_0=%s AND LineList=%s',
    #                    (meta_dict['species_id'], meta_dict['v1_0'], meta_dict['v2_0'], meta_dict['LineList']))
    #     print 'Removing original linelist for replacement...'
    #     cursor.execute('DELETE from main WHERE species_id=%s AND ll_id=%s',
    #                    (meta_dict['species_id'], meta_dict['LineList']))
    #     cursor.close()

    
    # Create new metadata entry in database
    if (update == 0) or (update == 1 and push_metadata_flag == True):
        cursor = db.cursor()
        print 'Creating new entry in metadata table...'
        try:
            cursor.execute(query("species_metadata", meta_dict), meta_dict.values())
        except sqldb.ProgrammingError:
            print "The folllowing query failed: "
            print query_err("species_metadata", meta_dict).format(*meta_dict.values())
        print 'Finished successfully.\n'
        cursor.close()

    print 'Pushing linelist (%s entries) to database...' % num_entries
    cursor = db.cursor()

    # Generates a giant INSERT query for all rows in the linelist. 
    # This is a MUCH faster process than having Python loop through each row and insert it manually.
    query_ll = "INSERT INTO %s ( %s ) VALUES ( %s )" \
               % ("main", ', '.join(ll.columns.values), placeholders(ll.columns.values))

    try:
        cursor.executemany(query_ll, ll_dict)
    except sqldb.ProgrammingError:
        print 'Pushing linelist failed.'
    except TypeError: 
        raise

    cursor.close()
    db.commit()

    print 'Finished with linelist push.'


def main(db):

    # ------------------
    # POPULATE CDMS LIST
    # ------------------
    pd.options.mode.chained_assignment = None
    print 'Pulling updates from CDMS...'
    update_list = pull_updates()
    choice_list = [CDMSChoiceList([str(i)]+update_list[i]) for i in range(len(update_list))]

    # RUN PROCESS

    CDMSLoop = True
    while CDMSLoop:
        cursor = db.cursor()

        choice = eg.choicebox("Choose a Molecule to Update", "Choice", choice_list)
        custom_cat_file = eg.buttonbox(msg='Would you like to supply a custom CAT file?', choices=['Yes', 'No'])
        if custom_cat_file == 'Yes':
            custom_path = eg.fileopenbox(msg='Please select a CAT file.', title='Custom CAT file')
            cat_entry = CDMSMolecule(update_list[int(choice[0:5])], custom=True, custom_path=custom_path)
        else:
            cat_entry = CDMSMolecule(update_list[int(choice[0:5])], custom=False)

        # Queries database for all species with valid "SPLAT IDs"
        cmd = "SELECT * FROM species " \
            "WHERE SPLAT_ID LIKE '%s%%'" % str(cat_entry.tag[:3])

        cursor.execute(cmd)
        res = cursor.fetchall()

        # Hacky way to get easygui to correlate the mysql query output rows to rows in the GUI molecule list
        splatmolresults = [SplatSpeciesResultList([i]+list(x)) for i, x in enumerate(res)]
        splatmolresults += [SplatSpeciesResultList([len(splatmolresults),999999999,0,'NEW MOLECULE',
                                                    'X', '', '', '', '', '', ''])]
        choice2 = eg.choicebox("Pick molecule from Splatalogue to update, or create a new molecule.\n "
                               "Current choice is:\n %s" % choice, "Splatalogue Search Results",
                               splatmolresults)
        cursor.close()

        if choice2[68] == 'X': # New molecule
            linelist, species_final, metadata_final = new_molecule(cat_entry, db)
            push_molecule(db, linelist, species_final, metadata_final, update=0)
        else:  # Molecule already exists in Splatalogue database
            linelist, metadata_final, push_metadata_flag, append_lines_flag = process_update(cat_entry, res[int(choice2[0:5])], db)
            push_molecule(db=db, ll=linelist, spec_dict={}, meta_dict=metadata_final, push_metadata_flag=push_metadata_flag, append_lines_flag=append_lines_flag, update=1)

        choice3 = eg.buttonbox(msg='Do you want to update another CDMS entry?', choices=['Yes', 'No'])

        if choice3 == 'No':
            CDMSLoop = False
