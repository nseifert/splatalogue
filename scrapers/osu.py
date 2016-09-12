import time
import datetime
import numpy as np
import pandas as pd
from itertools import izip_longest
from collections import OrderedDict
import re
import MySQLdb as sqldb
import easygui as eg
import os


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

def calc_derived_params(df, options):
        # Build linelist data to push to database
    if 'measfreq' in options['columns']:
        if 'measerrfreq' not in df.columns.values:
            df['measerrfreq'] = options['freq_uncert']
        df['error'] = df['measerrfreq']
        df['roundedfreq'] = df['measfreq'].round(decimals=0)
        df['orderedfreq'] = df['measfreq']
        df['line_wavelength'] = 299792458./(df['measfreq']*1.0E6)*1000

    if 'lower_state_energy' in options['columns']:
        df['lower_state_energy_K'] = 1.438786296 * df['lower_state_energy']
        df['upper_state_energy'] = df['lower_state_energy'] + df['measfreq']/29979.2458
        df['upper_state_energy_K'] = 1.438786296 * df['upper_state_energy']

    # df['intintensity'] = np.log10(opt['C3'] * df['measfreq']*
    #                               (1-np.exp(-6.62607004E-34 * df['measfreq']*1.0E6/(1.38064852E-23*opt['temp'])))
    #                               * np.exp(-1.0*opt['C2']*df['lower_state_energy']/opt['temp']) * df['sijmu2'])
    df['intintensity'] = np.log10(opt['C1'] * np.sqrt(opt['mass']/opt['temp']) *
                                  (1-np.exp(-1.0*opt['C2']*df['measfreq']/opt['temp'])) * df['sijmu2'] *
                                  np.exp(-1.0*opt['C3']*df['lower_state_energy']/opt['temp']))

    df['ll_id'] = 17
    df['species_id'] = options['species_id']
    df['Lovas_NRAO'] = 1
    df['labref_Lovas_NIST'] = options['labref']
    df['`v3.0`'] = 3
    
    return df

def push_data(df, meta, db):

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

    # Push metadata
    cursor = db.cursor()
    cursor.execute("USE splat")

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
    else:
        print 'Linelist successfully pushed.'

    cursor.close()

    

if __name__ == '__main__':

    opt = {
        'path': '/media/sf_Share/osu_data/vinyl_cyanide.txt',
        'rows_to_skip': 14,
        'columns': ['measfreq', 'sijmu2', 'lower_state_energy', 'lextras'],

        'select_columns': ['measfreq', 'sijmu2', 'lower_state_energy'],
        'fixed_widths': [10, 5, 5, 10],
        'labref': 'Fort11',

        'freq_uncert': 0.025,

        'C1': 54.5953,
        'C2': 4.799237E-5,
        'C3': 1.43877506,
        'mass': (1.007825)*3 + 12.0*3 + 14.003074,
        'temp': 300.0,

        'species_id': '21159'
    }

    metadata = {
        'species_id': opt['species_id'],
        'LineList': 17,
        'v3_0': 3,
        'Name': 'Vinyl Cyanide',
        'Date': time.strftime('%b. %Y'),
        'Contributor': 'Nathan Seifert',
        'Ref1': 'The data listed between 210 and 270 GHz was taken from: S. M. Fortman, I. R. Medvedev, C. F. Neese, '
                'F. C. De Lucia, <i>Astrophys. J.</i>,  <b>737</b>, 20 (2011). \n\nCONTRIBUTOR\'S NOTE:\n Values listed'
                ' in the CDMS/JPL integrated intensity are logarithmic normalized absorption coefficients, using Equation 6 in the'
                'above citation.',
        'Ref20': 'http://iopscience.iop.org/article/10.1088/0004-637X/737/1/20'

    }

    inp = pd.read_fwf(filepath_or_buffer=opt['path'], skiprows=opt['rows_to_skip'], names=opt['columns'],
                      header=None, widths=opt['fixed_widths'])

    for col in set(opt['columns']) - set(opt['select_columns']):
        inp.drop(col, axis=1, inplace=True)
    print inp

    inp = calc_derived_params(inp, opt)

    inp[inp==-np.inf] = np.nan
    inp[inp==np.inf] = np.nan

    print 'Pushing data to Splatalogue...\n'
    push_data(inp, metadata, initiate_sql_db())
    print 'Data push successful.'