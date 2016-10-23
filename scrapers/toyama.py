from bs4 import BeautifulSoup
from types import *
import pandas as pd
import numpy as np
import re
import time
import MySQLdb as sqldb


def format_qns(df, fmt):

    fmt_idx_up = fmt['index_up']
    fmt_idx_dwn = fmt['index_down']
    fmt_style = fmt['style']

    df['resolved_QNs'] = df[['Uqn%s'%i for i in fmt_idx_up]+['Lqn%s'%i for i in fmt_idx_dwn]].apply(lambda x: fmt_style.format(*x), axis=1)
    if 'Symmetry' in df.columns.values:
        df['resolved_QNs'] = df['resolved_QNs'] + ' ' + df['Symmetry']

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
    return data


def prep_data(df, opt):

    rename_dict = {'Frequency': 'measfreq', 'Exp uncert': 'measerrfreq',
                       'Source': 'labref_Lovas_NIST', 'Enenrgy': 'lower_state_energy',
                       'Intensity': 'intintensity', 'Source': 'labref_Lovas_NIST', 'resolved_QNs': 'resolved_QNs'}
    df.rename(columns=rename_dict, inplace=True)

    for col in set(df.columns.values)-set(rename_dict.values()):
        df.drop(col, axis=1, inplace=True)

    df[['measfreq', 'measerrfreq', 'lower_state_energy', 'intintensity']] = \
        df[['measfreq', 'measerrfreq', 'lower_state_energy', 'intintensity']].apply(pd.to_numeric)

    df['error'] = df['measerrfreq']
    df['roundedfreq'] = df['measfreq'].round(decimals=0)
    df['orderedfreq'] = df['measfreq']
    df['line_wavelength'] = 299792458./(df['measfreq']*1.0E6)*1000

    if 'lower_state_energy' in df.columns.values:
        df['lower_state_energy_K'] = 1.438786296 * df['lower_state_energy']
        df['upper_state_energy'] = df['lower_state_energy'] + df['measfreq']/29979.2458
        df['upper_state_energy_K'] = 1.438786296 * df['upper_state_energy']

    df['intintensity'] = df['intintensity']/max(df['intintensity'])
    df['intintensity'].apply(lambda x: np.log10(x))

    df['ll_id'] = 16
    df['`v3.0`'] = 3
    df['species_id'] = meta['species_id']

    if opt['ism_molecule']:
        df['Lovas_NRAO'] = 1
    else:
        df['Lovas_NRAO'] = 0


    return df


def push_data(df, meta, new_species=False, species_data=None):
    def initiate_sql_db():
        def rd_pass():
            return open('pass.pass').read()

        print '\nLogging into MySQL database...'

        HOST = "127.0.0.1"
        LOGIN = "nseifert"
        PASS = rd_pass()
        db = sqldb.connect(host=HOST, user=LOGIN, passwd=PASS.strip(), port=3307)
        db.autocommit(False)
        print 'MySQL Login Successful.'
        return db

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

    db = initiate_sql_db()

    # Create new species entry, if needed
    print 'Creating new species entry...'
    cursor = db.cursor()
    cursor.execute("USE splat")
    if new_species:
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

    cursor.close()


if __name__ == "__main__":

    opt = {
    'path': '/media/sf_Share/toyama/data/',
    'file': 'C2H5OCH3_v29.html',

    'qn_style': '{}({}, {}) - {}({}, {})',
    'qn_index_up': [2, 3, 4],
    'qn_index_down': [2, 3, 4],

    'ism_molecule': False,
    }

    meta = {
        'species_id': 21163,
        'LineList': 16,
        'v3_0': 3,
        'Name': 'Ethyl Methyl Ether, v<sub>28</sub> = 1',
        'Date': time.strftime('%b. %Y'),
        'Contributor': 'Nathan Seifert',

        'Ref1': open(opt['path']+'C2H5OCH3_ref.txt', 'r').read(),
        'Ref2': 'CONTRIBUTOR NOTE: Intensities are sourced from the "Intensity" column of the ToyaMA entry, but'
                'they are presented here in normalized and logarithmic form.',

        'A': '',
        'B': '',
        'C': '',
        'MU_A': '',
        'MU_B': '',
        'MU_C': ''
    }

    species = {
        'species_id': meta['species_id'],
        'name': 'C<sub>2</sub>H<sub>5</sub>OCH<sub>3</sub>, v<sub>28</sub> = 1',
        'chemical_name': 'Ethyl Methyl Ether',
        's_name': 'C2H5OCH3, v28=1',
        's_name_noparens': 'C2H5OCH3, v28=1',
        'SPLAT_ID': '06028',

        'potential': 1,
        'probable': 0,
        'known_ast_molecules': 0,

        # Shouldn't have to change the ones below
        'created': 'NOW()',
        'atmos': 0,
        'resolved': 1,
        'Top20': 0,
        'version': 1,
    }


    input_table = open(opt['path']+opt['file'],'r')
    print 'Loaded file from path: %s' %opt['path']+opt['file']

    data = format_qns(parse_html(input_table), fmt={'style': opt['qn_style'], 'index_up': opt['qn_index_up'], 'index_down': opt['qn_index_down']})
    data = prep_data(data, opt)
    push_data(data, meta, new_species=True, species_data=species)
