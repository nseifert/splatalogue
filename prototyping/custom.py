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
from scrapers.QNFormat import *

pd.set_option('chained_assignment',None)

class CustomMolecule:
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
            cat_inp = open(cat_url, 'r').read().split('\n')

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

    def get_metadata(self, meta_inp_path):
        metadata = {}

        # Dictionaries to connect string values in JPL metadata to SQL columns
        tags = {'TITLE': 'Name', 'CHEMICAL_NAME': 'chemical_name', 'SHORT_NAME': 's_name',
                'Q(300.0)': 'Q_300_0', 'Q(225.0)': 'Q_225_0', 'Q(150.0)': 'Q_150_0',
                'Q(75.00)': 'Q_75_00', 'Q(37.50)': 'Q_37_50', 'Q(18.75)': 'Q_18_75', 'Q(9.375)': 'Q_9_375',
                'A': 'A', 'B': 'B', 'C': 'C', 'MU_A': 'MU_A',  'MU_B': 'MU_B', 'MU_C': 'MU_C',
                'CONTRIBUTOR': 'Contributor', 'REF': 'REF'}

        for line in open(meta_inp_path, 'r').read().split('\n'):
            id, value = line.split(':')
            try:
                metadata[tags[id]] = value.strip()
            except KeyError:
                if id == 'STATE_ID_IDX':
                    self.STATE_ID_IDX = value.strip()
                elif id == 'STATE_ID_VAL':
                    self.STATE_ID_VAL = value.strip()
                else:
                    continue

        metadata['Date'] = time.strftime('%b %Y', time.gmtime())
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
        cat['roundedfreq'] = np.round(cat['frequency'].values, 0)
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

    def filter_cat(self, cat, filter_tup, filter_type='state'):
        idx, val = filter_tup

        if filter_type == 'state':
            return cat[(cat['qn_up_%s' %idx] == int(val))]

        if filter_type == 'upper_cut_off':
            return cat[(cat[idx] < float(val))]

        if filter_type == 'lower_cut_off':
            return cat[(cat[idx]) > float(val)]

    def __init__(self, cat_path, meta_inp_path, ll_id = '14'):

        self.metadata = self.get_metadata(meta_inp_path)
        self.cat = self.parse_cat(cat_path, local=1)
        self.cat = self.calc_derived_params(self.cat, self.metadata)
        self.ll_id = ll_id


        try:
            self.cat = self.filter_cat(self.cat, (self.STATE_ID_IDX, self.STATE_ID_VAL))

        except AttributeError:  # If a STATE_ID isn't passed through in the input file
            pass

        self.cat = self.filter_cat(self.cat, ('uncertainty', 999.9), filter_type='upper_cut_off')

def process_custom_entry(cat_path, meta_inp_path):

    input_molecule = CustomMolecule(cat_path, meta_inp_path)

if __name__ == "__main__":
    process_custom_entry("/media/sf_Share/ozone/16-16-18-000_010_combined.cat", 'meta_inp_sample.txt')