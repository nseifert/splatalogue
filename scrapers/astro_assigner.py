# -*- coding: utf-8 -*-
import pandas as pd
import MySQLdb as mysqldb
from MySQLdb import cursors
import numpy as np
import re
import easygui as eg
from tqdm import tqdm, tqdm_pandas


def init_sql_db():
    def rd_pass():
        return open('pass.pass','r').read()

    HOST = "127.0.0.1"
    LOGIN = "nseifert"
    PASS = rd_pass()
    db = mysqldb.connect(host=HOST, user=LOGIN, passwd=PASS.strip(), port=3307, cursorclass=cursors.SSCursor)
    db.autocommit(False)
    print 'MySQL Login Successful.'

    return db


def calc_rough_mass(formula):

    # Look-up table for common elements:
    masses = {'H': 1.0, 'D': 2.0, 'He': 4.0,
              'B': 10.8, 'C': 12.0, 'N': 14.0, 'O': 16.0, 'F': 19.0,
              'Na': 23.0, 'Mg': 24.3, 'Al': 27.0, 'Si': 28.0, 'P': 31.0, 'S': 32.0, 'Cl': 35.0,
              'K': 39.0, 'Ti': 48.0, 'Fe': 56.0
              }
    mass = 0.0
    for entry in re.findall(r'([A-Z][a-z]*)(\d*)', formula):
        try:
            ele_mass = masses[entry[0]]
            if entry[1] != '':
                ele_mass *= int(entry[1])
            mass += ele_mass
        except KeyError:
            continue
    return int(mass)

def read_raw_file(inp, fmt, delimiter, tag, skiprows=0):

    linelist = {}
    for key in fmt: 
        linelist[key] = []

    for i, line in enumerate(inp):
        if i <= skiprows-1:
            continue
        if line.split() is None:
            continue

        else:
            temp = line.decode('unicode_escape').encode('ascii', 'ignore')  # Gets rid of Unicode escape characters
           
            if tag == 'shimajiri':
                line_elements = {}

                # Sanitize formulas
                line_elements['El'] = temp.split()[0]

                # Pull upper quantum number 
                m = re.search(r'\((.*?)\)', temp)

                line_elements['qNu'] = re.findall(r'\d+', m.group(1))[0]

                # Pull frequency
                line_elements['Freq'] = float(re.sub(r'\(.*?\)', '', temp).split()[1])*1000

                for key in fmt:
                    linelist[key].append(line_elements[key])

    return pd.DataFrame.from_dict(linelist)



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
                    if len(line.strip().split(delimiter)) != len(fmt):
                        continue
                    else:
                        linelist[key].append(line.strip().split(delimiter)[i])
            except IndexError:
                print "\"" + line + "\""
                raise

    linelist['Freq'] = [float(f) for f in linelist['Freq']]  # Convert from str to float
    
    return pd.DataFrame.from_dict(linelist)

def push_raw_to_splat(astro_ll, meta, db, fuzzy_search=0, use_qn_mult=1, use_qn_sing=0, freq_tol=1.0, mass_tol=4.0, verbose=0):
    if verbose:
        filename = open('output.txt', 'w')

    if not fuzzy_search:
        species_id_global = {}

    for idx, row in tqdm(astro_ll.iterrows(), total=astro_ll.shape[0]):

        curs2 = db.cursor()

        cmd = "SELECT line_id, orderedfreq, transition_in_space, species_id, quantum_numbers FROM main " \
              "WHERE Lovas_NRAO = 1 AND (orderedfreq <= %s AND orderedfreq >= %s)"\
              % (row['Freq'] + freq_tol, row['Freq'] - freq_tol)

        curs2.execute(cmd)

        res = curs2.fetchall()
        num_results = len(res)

        if not fuzzy_search:
            if row['El'] not in species_id_global.keys():   
                species_id_lookup = {}
                for rrow in res:

                    t_cursor = db.cursor()
                    cmd = "SELECT SPLAT_ID, chemical_name, s_name FROM species where species_id = %s" % rrow[3]
                    t_cursor.execute(cmd)
                    species_id_lookup[rrow[3]] = t_cursor.fetchall()
                    t_cursor.close()

                if len(species_id_lookup.keys()) == 1:
                    species_id_global[row['El']] = species_id_lookup.keys()[0]
                else:
                    selections = [str(k)+'\t'+'\t'.join([str(k) for k in v]) for k, v in species_id_lookup.iteritems()]
                    choice = eg.choicebox(msg='Multiple results for entry %s. Pick the matching splat entry.' % row['El'], choices=selections)
                    species_id_global[row['El']] = choice.split()[0]


        selected_transitions = [] 
        overlap_trans = False
        updated_species_ids = set()

        if num_results > 0:

            for sql_row in res:
                t_cursor = db.cursor()
                cmdd = "SELECT SPLAT_ID FROM species WHERE species_id = %s" % sql_row[3]
                t_cursor.execute(cmdd)
                splat_id = t_cursor.fetchall()[0][0]
                splat_mass = int(splat_id[:-2].lstrip("0"))

                if verbose:
                    filename.write('\t'.join([str(splat_id), str(splat_mass), str(row['rough_mass'])])+"\n")
                
                if str(sql_row[2]) == "1":  # Transition already labeled
                    if verbose: 
                        filename.write('Transition found for %s for splat_id %s\n' %(row['El'], splat_id))
                    continue     

                if np.abs(splat_mass - row['rough_mass']) <= mass_tol:

                    if num_results > 1:
                        if use_qn_mult:
                            if row['qNu'].split()[0] == sql_row[-1].split()[0]:
                                selected_transitions.append(sql_row)
                                updated_species_ids.add(sql_row[3])
                            elif not fuzzy_search: 
                                if str(species_id_global[row['El']]) == str(sql_row[3]):
                                    selected_transitions.append(sql_row)
                                    updated_species_ids.add(sql_row[3])

                    if num_results == 1:
                        selected_transitions.append(sql_row)
                        updated_species_ids.add(sql_row[3])
                t_cursor.close()

        if len(selected_transitions) > 0:  # Push updates to main
            overlap_trans = True
            for trans in selected_transitions:
                curs2.execute("UPDATE main SET transition_in_space=1, source_Lovas_NIST=\"%s\", telescope_Lovas_NIST=\"%s\",  obsref_Lovas_NIST=\"%s\"  WHERE line_id = %s"
                              % (meta['source'], meta['tele'], meta['ref_short'], trans[0]))

        if verbose:
            filename.write('Frequency: %s \t # Results Raw: %i \t Selected Results: %i\n'
                               % (row['Freq'], num_results, len(selected_transitions)))
            if len(selected_transitions) != 0:
                filename.write('--------------\n')
                for sel_row in selected_transitions:
                    filename.write('\t\t Line: %s \t Species ID: %s \t Splat Freq: %s\n\n'
                                   % (sel_row[0], sel_row[2], sel_row[1]))
            else:
                filename.write('--------------\n')
                filename.write('No lines found. Species: %s \t Formula: %s \t Rough Mass: %s \n' \
                      % (row['El'],row['El_parse'], row['rough_mass']))

        # Update metadata for species that were updated
        for species in updated_species_ids:
            curs2.execute("SELECT Ref19, Date from species_metadata where species_id=%s ORDER BY Date DESC" % species)
            try:
                ref_data = curs2.fetchall()[0]
            except IndexError:  # Bad species_id?
                print 'Bad ref data for species id # %s: ' % species
                continue
            if ref_data[0] == None or ref_data[0] == '':
                to_write = "Astronomically observed transitions for this linelist have been marked using data from" \
                           " the following references"
                if overlap_trans:
                    to_write += " (NOTE: Some transitions in the linelist " \
                                "are overlapping at typical astronomical linewidths." \
                                " All transitions within this typical tolerance have been marked as observed.)"
                to_write += ": %s" % meta['ref_full']
            else:
                continue
                # to_write = ref_data[0] + "; %s" % meta['ref_full']

            curs2.execute("UPDATE species_metadata SET Ref19 = \"%s\" WHERE species_id=%s AND Date = \"%s\""
                          % (to_write, species, ref_data[1]))

        curs2.close()
    if verbose:
        filename.close()

    # Update linelist list with ref
    # curs3 = db.cursor()
    # curs3.execute("INSERT INTO lovas_references (Lovas_shortref, Lovas_fullref) VALUES (\"%s\", \"%s\")" %(meta['ref_short'], meta['ref_full']))
    print 'Update completed successfully.'                        


def push_vizier_to_splat(astro_ll, meta, db, use_qn_mult=1, use_qn_sing=0, freq_tol=1.0, mass_tol=4, verbose=0):

    if verbose:
        filename = open('output.txt', 'w')

    for idx, row in tqdm(astro_ll.iterrows(), total=astro_ll.shape[0]):

        curs2 = db.cursor()

        cmd = "SELECT line_id, orderedfreq, transition_in_space, species_id, quantum_numbers FROM main " \
              "WHERE Lovas_NRAO = 1 AND (orderedfreq <= %s AND orderedfreq >= %s)"\
              % (row['Freq'] + freq_tol, row['Freq'] - freq_tol)

        curs2.execute(cmd)

        res = curs2.fetchall()
        num_results = len(res)
        selected_transitions = []
        overlap_trans = False

        updated_species_ids = set()

        if num_results > 0:

            for sql_row in res:
                curs2.execute("SELECT SPLAT_ID FROM species WHERE species_id = %s" % sql_row[3])
                splat_id = curs2.fetchall()[0][0]
                splat_mass = int(splat_id[:-2].lstrip("0"))
                if verbose:
                    filename.write('\t'.join([str(splat_id), str(splat_mass), str(row['rough_mass'])])+"\n")

                if sql_row[2] == "1" or sql_row[2] == 1:   # Transition already labeled
                    continue

                if np.abs(splat_mass - row['rough_mass']) <= mass_tol:

                    if num_results > 1:
                        if use_qn_mult:
                            if row['qNu'].split()[0] == sql_row[-1].split()[0]:
                                selected_transitions.append(sql_row)
                                updated_species_ids.add(sql_row[3])
                        else:
                            selected_transitions.append(sql_row)
                            updated_species_ids.add(sql_row[3])

                    if num_results == 1:
                        if use_qn_sing:
                            if row['qNu'].split()[0] == sql_row[-1].split()[0]:
                                selected_transitions.append(sql_row)
                                updated_species_ids.add(sql_row[3])
                        else:
                            selected_transitions.append(sql_row)
                            updated_species_ids.add(sql_row[3])

        if len(selected_transitions) > 0:  # Push updates to main
            overlap_trans = True
            for trans in selected_transitions:
                curs2.execute("UPDATE main SET transition_in_space=1, source_Lovas_NIST=\"%s\", telescope_Lovas_NIST=\"%s\",  obsref_Lovas_NIST=\"%s\"  WHERE line_id = %s"
                              % (meta['source'], meta['tele'], meta['ref_short'], trans[0]))

        if verbose:
            filename.write('Frequency: %s \t # Results Raw: %i \t Selected Results: %i\n'
                               % (row['Freq'], num_results, len(selected_transitions)))
            if len(selected_transitions) != 0:
                filename.write('--------------\n')
                for sel_row in selected_transitions:
                    filename.write('\t\t Line: %s \t Species ID: %s \t Splat Freq: %s\n\n'
                                   % (sel_row[0], sel_row[2], sel_row[1]))
            else:
                filename.write('--------------\n')
                filename.write('No lines found. Species: %s \t Formula: %s \t Rough Mass: %s \n' \
                      % (row['El'],row['El_parse'], row['rough_mass']))

        # Update metadata for species that were updated
        for species in updated_species_ids:
            curs2.execute("SELECT Ref19, Date from species_metadata where species_id=%s ORDER BY Date DESC" % species)
            try:
                ref_data = curs2.fetchall()[0]
            except IndexError:  # Bad species_id?
                print 'Bad ref data for species id # %s: ' % species
                continue
            if ref_data[0] == None or ref_data[0] == '':
                to_write = "Astronomically observed transitions for this linelist have been marked using data from" \
                           " the following references"
                if overlap_trans:
                    to_write += " (NOTE: Some transitions in the linelist " \
                                "are overlapping at typical astronomical linewidths." \
                                " All transitions within this typical tolerance have been marked as observed.)"
                to_write += ": %s" % meta['ref_full']
            else:
                continue
                # to_write = ref_data[0] + "; %s" % meta['ref_full']

            curs2.execute("UPDATE species_metadata SET Ref19 = \"%s\" WHERE species_id=%s AND Date = \"%s\""
                          % (to_write, species, ref_data[1]))

        curs2.close()
    if verbose:
        filename.close()

    # Update linelist list with ref
    curs3 = db.cursor()
    curs3.execute("INSERT INTO lovas_references (Lovas_shortref, Lovas_fullref) VALUES (\"%s\", \"%s\")" %(meta['ref_short'], meta['ref_full']))
    print 'Update completed successfully.'

if __name__ == "__main__":

    path = "/home/nate/Downloads/Line Survey/Shimajiri 2015/FIR_3N_raw.txt"
    fmt = ['El', 'qNu', 'Freq']
    TOLERANCE = 1.0  # In units of linelist frequency, typically MHz.

    linelist = read_raw_file(open(path, 'r'), fmt, ' ', tag='shimajiri')
    #rint linelist

    # linelist = read_vizier_file(open(path, 'r'), fmt, '\t')
    # linelist['El'] = linelist['El'].apply(lambda x: x.replace('_','')).apply(lambda x: re.sub('\\^.*?\\^', '', x)).apply(lambda x: x.strip())
    # linelist['qNu'] = linelist['qNu'].apply(lambda x: re.findall(r'\d+', x)[0])

    def parse_formula(row):
        return ''.join([x[0] if x[1] == '' else x[0]+x[1]
                                        for x in re.findall(r'([A-Z][a-z]*)(\d*)', row)])
    def sanitize_formula(form):
        formula_chars_to_rid = ['+', '13', '18', '15', '17']
        for val in formula_chars_to_rid:
                    form = form.replace(val, '')
        return form



    linelist['El_parse'] = linelist['El'].apply(parse_formula).apply(sanitize_formula)
    linelist['rough_mass'] = linelist['El_parse'].apply(calc_rough_mass)

    print linelist
    db = init_sql_db()
    print 'Connected to database successfully.'

    cursor = db.cursor()
    cursor.execute("USE splat")

    # Enter metadata for astronomical study
    fields = ['Telescope', 'Source', 'Full Reference', 'Reference Abbrev.']

    # fieldValues = eg.multenterbox(msg="Enter metadata for astro survey.", title="Survey Metadata", fields=fields)

    # metadata = {'tele': fieldValues[0], 'source': fieldValues[1],
    #            'ref_full': fieldValues[2], 'ref_short': fieldValues[3]}

    metadata = {'tele': 'ATSE', 'source': 'OMC 2-FIR-3N',
                'ref_full': 'Y. Shimajiri, T. Sakai, Y. Kitamura, <i>et. al</i>, <b>2015</b>, <i>ApJ. Suppl.</i> 221, 2.',
                'ref_short': 'Shimajiri 2015'}

    print 'Pushing updates from %s, telescope: %s, source: %s...' \
          % (metadata['ref_short'], metadata['tele'], metadata['source'])

    push_raw_to_splat(astro_ll=linelist, meta=metadata, db=db, verbose=0, fuzzy_search=0, use_qn_mult=1, mass_tol=3, freq_tol=2.0)
    # push_vizier_to_splat(astro_ll=linelist, meta=metadata, db=db, use_qn_mult=1, mass_tol=4, freq_tol=1.0)








