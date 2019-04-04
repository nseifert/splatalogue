from bs4 import BeautifulSoup
from types import *
import pandas as pd
import numpy as np
import re
import time
import MySQLdb as sqldb
import easygui as eg
from os.path import exists


def format_qns(df, fmt):
    # Resolve indicies
    fmt_idx = fmt['index']
    fmt_style = fmt['style']
    print fmt_idx, fmt_style

    if len(fmt_idx) % 2 == 1 or len(fmt_idx) == 0:

        print 'You shouldn\'t have ever come here.'
        return 0

    else:

        order = []
        for val in fmt_idx:

            try:
                if 'up' in val:
                    order.append('Uqn%s' %[int(s) for s in val if s.isdigit()][0])
                elif 'low' in val:
                    order.append('Lqn%s' %[int(s) for s in val if s.isdigit()][0])
            except IndexError:
                print 'Your QN# input is malformed in some way. It failed on: %s ' %val
                raise
    print df[order]
    df['resolved_QNs'] = df[order].apply(pd.to_numeric, args=('coerce','integer')).apply(lambda x: fmt_style.format(*x), axis=1)

    if 'Symmetry' in df.columns.values:
        df['resolved_QNs'] = df['resolved_QNs'] + ' ' + df['Symmetry']

    # Now let's do a quick regex to check if there are any QNs of the form "N_IJ" and replace with N(I, J)
    def fix_QNs(buffer, regex='(\\d+_\\d+)'):
        out = buffer
        r = re.compile(regex)
        res = re.findall(r, buffer)
        if res:
            for val in res:

                upper_qn, lower_qn = val.split('_')
                if len(lower_qn) >= 3:
                    if len(upper_qn) % 2 == 0:
                        idx = len(lower_qn)/2
                        out = out.replace(val, upper_qn+'(%s, %s)' %(lower_qn[:idx], lower_qn[idx:]))
                    else:
                        # e.g. Ka,Kc = 2,10 or 10,2, etc.
                        idx = len(lower_qn)/2 - 1
                        if int(lower_qn[:idx]) + int(lower_qn[idx:]) in [int(upper_qn)+1, int(upper_qn)]:
                            out = out.replace(val, upper_qn+'(%s, %s)' %(lower_qn[:idx], lower_qn[idx:]))
                        else:
                            out = out.replace(val, upper_qn+'(%s, %s)' %(lower_qn[:idx+1], lower_qn[idx+1:]))

                else:
                    out = out.replace(val, upper_qn+'(%s, %s)' %(lower_qn[:1], lower_qn[1:])) # Ka, Kc < 10

        return out

    # Get rid of any NaNs
    def drop_nans_hyperfine(buffer):
        if 'nan' in buffer:
            # If hyperfine, look for F = first'
            buffer = buffer.split(', F =')[0]
            buffer.replace('nan', '')
        return buffer


    df['resolved_QNs'] = df['resolved_QNs'].apply(fix_QNs)
    df['resolved_QNs'] = df['resolved_QNs'].apply(drop_nans_hyperfine)
    df['resolved_QNs'] = df['resolved_QNs'].apply(lambda x: x.replace('.0',''))
    return df


def parse_html(inp):

    def isfloat(x):
        try:
            a = float(x)
        except ValueError:
            return False
        else:
            return True
    def isint(x):
        try:
            a = float(x)
            b = int(a)
        except ValueError:
            return False
        else:
            return a == b

    print 'Performing initial HTML parsing...'
    soup = BeautifulSoup(inp, 'html.parser')
    print 'HTML has been parsed successfully.'

    print 'Extracting data from HTML...'
    tbl_headers = []
    tbl_data = []
    table = soup.find('table')
    table_body = table.find('tbody')

    rows = table_body.find_all('tr')
    for i, row in enumerate(rows):
        if i == 0:
            titles = row.find_all('th')
            titles = [ele.text.strip() for ele in titles]
            tbl_headers = [ele.encode('utf-8') for ele in titles]
        else:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            tbl_data.append([ele.encode('utf-8') if ele else np.nan for ele in cols])

    data = pd.DataFrame(tbl_data)
    data.columns = tbl_headers

    # Get rid of any columns that are all NaN entries
    return data.dropna(axis=1, how='all')


def inp_metadata(meta_inp_path):
    mdata = {}

    # Dictionaries to connect string values in JPL metadata to SQL columns
    tags = {'TITLE': 'Name', 'CHEMICAL_NAME': 'chemical_name', 'SHORT_NAME': 's_name',
            'Q(300.0)': 'Q_300_0', 'Q(225.0)': 'Q_225_0', 'Q(150.0)': 'Q_150_0',
            'Q(75.00)': 'Q_75_00', 'Q(37.50)': 'Q_37_50', 'Q(18.75)': 'Q_18_75', 'Q(9.375)': 'Q_9_375',
            'A': 'A', 'B': 'B', 'C': 'C', 'MU_A': 'MU_A',  'MU_B': 'MU_B', 'MU_C': 'MU_C',
            'CONTRIBUTOR': 'Contributor', 'REF': 'Ref1'}


    fill_ins = {'v4_0': 4, 'LineList': 16}

    for line in open(meta_inp_path, 'r').read().split('\n'):
        if line[0] == '!':
            continue

        id = line.split(':')[0]
        value = ':'.join(line.split(':')[1:])
        try:
            mdata[tags[id]] = value.strip()
        except KeyError:
            if 'ref' in id.lower():
                i = 1
                for j in range(i, 21):
                    if 'Ref%i'%j not in mdata.keys():
                        break
                    i += 1
                mdata['Ref%i'%i] = value.strip()
            else:
                continue

    mdata['Date'] = time.strftime('%b %Y', time.gmtime())
    for key in fill_ins.keys():
        mdata[key] = fill_ins[key]

    return mdata


def prep_data(df, opt, meta):

    rename_dict = {'Frequency': 'measfreq', 'Exp uncert': 'measerrfreq',
                       'Source': 'labref_Lovas_NIST', 'Enenrgy': 'lower_state_energy',
                       'Intensity': 'intintensity', 'Source': 'labref_Lovas_NIST', 'resolved_QNs': 'resolved_QNs'}
    df.rename(columns=rename_dict, inplace=True)

    for col in set(df.columns.values)-set(rename_dict.values()):
        df.drop(col, axis=1, inplace=True)

    df[['measfreq', 'measerrfreq']] = \
        df[['measfreq', 'measerrfreq']].apply(pd.to_numeric)

    df['error'] = df['measerrfreq']
    df['roundedfreq'] = df['measfreq'].round(decimals=0)
    df['orderedfreq'] = df['measfreq']
    df['line_wavelength'] = 299792458./(df['measfreq']*1.0E6)*1000

    if 'lower_state_energy' in df.columns.values:
        pd.to_numeric(['lower_state_energy'], errors='coerce')
        df['lower_state_energy_K'] = 1.438786296 * df['lower_state_energy']
        df['upper_state_energy'] = df['lower_state_energy'] + df['measfreq']/29979.2458
        df['upper_state_energy_K'] = 1.438786296 * df['upper_state_energy']

    if 'intintensity' in df.columns.values:
        df['intintensity'] = pd.to_numeric(df['intintensity'], errors='coerce')
        df['intintensity'] = df['intintensity']/max(df['intintensity'])
        df['intintensity'].apply(lambda x: np.log10(x))

    df['ll_id'] = 16
    df['`v4.0`'] = 4
    df['species_id'] = meta['species_id']

    # if opt['ism_molecule']:
    #     df['Lovas_NRAO'] = 1
    # else:
    #     df['Lovas_NRAO'] = 0


    return df


def push_data(df, meta, db, new_species=False, species_data=None):

    def placeholders(inp_dict, err=False):
        if not err:
            return ', '.join(['%s'] * len(inp_dict))
        else:
            return ', '.join(['{}'] * len(inp_dict))

    def columns(inp_dict):
        return ', '.join(inp_dict.keys())

    def query(table, inp_dict, err=False):
        if not err:
            return "INSERT INTO %s ( %s ) VALUES ( %s )" % (table, columns(inp_dict), placeholders(inp_dict))
        else:
            return "INSERT INTO %s ( %s ) VALUES ( %s )" % (table, columns(inp_dict), placeholders(inp_dict, err=True))


    # Create new species entry, if needed

    cursor = db.cursor()
    cursor.execute("USE splat")
    if new_species:
        print 'Creating new species entry...'
        if species_data:
            cursor.execute(query("species", species_data), species_data.values())
    print 'Created new species entry.'
    time.sleep(2.0)

    # Push metadata
    print 'Pushing metadata...'
    cursor.execute(query("species_metadata", meta), meta.values())
    print 'Metadata push complete.'

    time.sleep(2.0)
    ll_dict = [(None if pd.isnull(y) else y for y in x) for x in df.values]

    print 'Pushing linelist (%i entries)...' %len(ll_dict)

    query_ll = "INSERT INTO %s ( %s ) VALUES ( %s )" \
               % ("main", ', '.join(df.columns.values), placeholders(df.columns.values))

    try:
        cursor.executemany(query_ll, ll_dict)
    except sqldb.ProgrammingError:
        print 'Pushing linelist failed.'
        raise
    else:
        print 'Linelist successfully pushed.'

    fix_float_qns = 'UPDATE main set resolved_QNs = REPLACE(resolved_QNs, \'.0\', \'\')' \
                    ' WHERE ll_id=16 AND species_id=%s' % meta['species_id']
    cursor.execute(fix_float_qns)

    cursor.close()

def main(db):

    pd.options.mode.chained_assignment = None # default='warn'

    ToyamaLoop = True

    while ToyamaLoop:

        opt = {}

        opt['path'] = eg.fileopenbox(msg='Please select input HTML table for Toyama entry', title='Toyama table entry')
        if not opt['path']:
            break

        qn_style_settings = {
            'msg': 'Please specify your quantum number style and ordering. \n'
                   'Please see README.md for specific examples of QN style formatters.',
            'title': 'QN Style Entry for Toyama',
            'fields': ['QN Style', 'QN Index Ordering']
        }
        qn_style = eg.multenterbox(msg=qn_style_settings['msg'],
                                   title=qn_style_settings['title'], fields=qn_style_settings['fields'])

        opt['qn_style'] = qn_style[0]
        opt['qn_index'] = [x.strip().lower() for x in qn_style[1].strip().split(',')]

        NewOrAppend = eg.buttonbox(msg='Do you want to add this entry as a new molecule or append to previously added Splat species?',
                                   title='New or append?', choices=['New', 'Append', 'QUIT'])
        if NewOrAppend == 'New':

            species = {}

            spec_inp_menu = {'msg': 'Please enter species entry information.',
                             'title': 'Species entry menu.',
                             'fields': ['name', 'chemical_name', 's_name', 's_name_noparens', 'SPLAT_ID',
                                        'potential', 'probable', 'known_ast_molecules']}

            species_inp = eg.multenterbox(msg=spec_inp_menu['msg'], title=spec_inp_menu['title'], fields=spec_inp_menu['fields'])

            if species_inp:

                for i, val in enumerate(spec_inp_menu['fields']):
                    species[val] = species_inp[i]

            else:
                break

            # Generate new species ID
            cur = db.cursor()
            cur.execute('SELECT MAX(species_id) FROM species')
            species['species_id'] = str(int(cur.fetchall()[0][0])+1)

        elif NewOrAppend == 'Append':
            # We at least need the species ID in order to push
            splat_id = eg.enterbox(msg='Please enter the SPLAT ID # of the species you wish to append to.')

            cur = db.cursor()
            cur.execute('SELECT species_id from species where SPLAT_ID = %s' %splat_id)
            res = cur.fetchall()
            cur.close()

            if res:
                species = res[0][0]
            else:
                break

        else:
            break

        # Generate metadata
        MetadataInpChoice = eg.buttonbox(msg='Do you want to supply a metadata input file?', title='Metadata input', choices=['Input File', 'Manual Entry'])

        if MetadataInpChoice:
            if MetadataInpChoice == 'Input File':
                meta = inp_metadata(eg.fileopenbox(msg='Please choose a valid metadata input file.', title='Metadata input'))
            elif MetadataInpChoice == 'Manual Entry':
                meta = {}

                MetaFields = ['Name', 'Contributor', 'Ref1', 'Ref2', 'A', 'B', 'C', 'MU_A', 'MU_B', 'MU_C', 'Q_300_0', 'Q_225_0', 'Q_150_0', 'Q_75_00', 'Q_37_50', 'Q_18_75', 'Q_9_375']
                MetaChoices = eg.multenterbox(msg='Please enter basic metadata information.', title='Metadata entry', fields=MetaFields)
                for i, val in enumerate(MetaFields):
                    # Check if meta entry is a text file -- for Ref only
                    if 'Ref' in val and exists(MetaChoices[i]):
                        try:
                            meta[val] = open(MetaChoices[i], 'r').read()
                        except:
                            meta[val] = ''
                        continue

                    meta[val] = MetaChoices[i]

            if isinstance(species, dict):
                meta['species_id'] = species['species_id']

            else:
                meta['species_id'] = species
                meta['LineList'] = 16
                meta['v3_0'] = 3
                meta['Date'] = time.strftime('%b %Y', time.gmtime())

        else:
            break

        if NewOrAppend == 'New':
            data = format_qns(parse_html(open(opt['path'],'r')), fmt={'style': opt['qn_style'], 'index': opt['qn_index']})
            push_data(df=prep_data(data, opt, meta), meta=meta, db=db, new_species=True, species_data=species)

        else:
            data = format_qns(parse_html(open(opt['path'],'r')), fmt={'style': opt['qn_style'], 'index': opt['qn_index']})
            push_data(df=prep_data(data, opt, meta), meta=meta, db=db, new_species=False)

        RestartChoice = eg.buttonbox(msg='Would you like to add another Toyama entry?', title='Another perhaps?', choices=['Yes', 'No'])

        if RestartChoice == 'No':
            break
