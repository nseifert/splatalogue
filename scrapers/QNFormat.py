# -*- coding: utf-8 -*-
__author__ = 'nate'
import pandas as pd
import easygui as eg
import numpy as np


class MissingQNFormatException(Exception):
    pass

def make_frac(idx, qn, shift=-1, frac_series=None):
    temp = qn.values.copy()
    if frac_series is None: # No specific rows excluded from fractional shift
        frac_series = idx

    for val in idx:
        if val in frac_series:
            try:
                temp[val] = '%s/2' % str(int(qn[val])*2+shift)
            except ValueError:
                raise
    return temp



def format_it(fmt_idx, qn_series, choice_idx=None):
    customChoice = None

    fmt_dict = {202: ({'fmt': '{:d}({:d}) - {:d}({:d})','series': [0, 1, 2, 3], 'tag':'Symmetric top'},
                      ),

                203: ({'fmt':'{:d}({:d}) - {:d}({:d}), F = {:d} - {:d}',
                       'series': [0, 1, 3, 4, 2, 5], 'tag': 'Symmetric top with 1 hyperfine nuclei.'},
                      {'fmt': '', 'series':[0], 'tag': 'Symmetric top with parity and weird electronic spin QN Omega (custom)'},
                      ),

                213: ({'fmt': '', 'series': [0], 'tag': 'Hunds Case B with Lambda doubling'},
                      {'fmt': '', 'series': [0], 'tag': 'Ziruys lambda-doubling. e.g. NaS'}
                      ),

                303: ({'fmt':'{:d}({:d},{:d}) - {:d}({:d},{:d})', 'series':[0, 1, 2, 3, 4, 5], 'tag': 'Asymmetric top.' },
                      ),

                304: ({'fmt':'{:d}({:d},{:d}) - {:d}({:d},{:d}), F = {:d} - {:d}', 'series': [0, 1, 2, 4, 5, 6, 3, 7], 'tag': 'Asymmetric top with 1 hyperfine nuclei.'},
                      ),

                314: ({'fmt':'N(K<sub>a</sub>,K<sub>c</sub>) = {:d}({:d},{:d}) - {:d}({:d},{:d}), J = {} - {}', 'series': [0, 1, 2, 4, 5, 6, 3, 7], 'frac_series': [3, 7], 'frac_shift': -1,
                      'tag': 'Asymmetric top with non-zero total electronic spin'},
                      ),

                346: ({'fmt': 'N(K<sub>a</sub>,K<sub>c</sub>) = {:d}({:d},{:d}) - {:d}({:d},{:d}), J = {} - {}, F = {} - {}',
                       'series': [0, 1, 2, 6, 7, 8, 3, 9, 4, 11], 'frac_series': [3, 9, 4, 11], 'frac_shift': -1,
                      'tag': 'Asymmetric top with non-zero total electronic spin and 1 hyperfine nuclei'},
                      ),

                1:   ({'fmt': 'J = {:d} - {:d}', 'series': [0, 1], 'tag': 'Atomic hyperfine transitions, pure J\'\' - J\''},),

                112: ({'fmt': 'N = {:d} - {:d}, 2J = {:d} - {:d}', 'series': [0, 2, 1, 3], 'tag': 'Hunds case (A) linear'},
                      ),

                113: ({'fmt': 'N = {:d} - {:d}, J = {:d} - {:d}, F = {} - {}', 'series':[1, 4, 0, 3, 2, 5], 'frac_series': [2,5], 'frac_shift': -1,
                       'tag': 'Linear molecule with singlet electronic spin and hyperfine nuclei'},
                      ),

                123: ({'fmt':'N = {:d} - {:d}, J = {} - {}, F = {:d} - {:d}', 'series':[0, 3, 1, 4, 2, 5], 'frac_series': [1,4], 'frac_shift': -1,
                      'tag': 'Linear molecule with non-singlet electronic spin and hyperfine nuclei'},
                      ),
                1303: ({'fmt': '', 'series': [0], 'tag': 'Lambda doubled symmetric top, e.g. CH3CN v8=1'},
                       {'fmt': '', 'series': [1], 'tag': 'Methylamine (JPL)'},
                       {'fmt': '', 'series': [2], 'tag': 'Ethylene v5-v4 (CDMS)'}
                       ),

                1304: ({'fmt':'N = {:d} - {:d}, J = {:d} - {:d}', 'series':[1, 4, 3, 7],
                       'tag': 'Symmetric top molecule with integral electronic spin'},
                       ),

                1404: ({'fmt': '{:d}({:d},{:d}) - {:d}({:d},{:d}), m = {:d}', 'series': [0, 1, 2, 4, 5, 6, 3], 'tag': 'Asymmetric top with specified upper-state vibrational QN'},
                       {'fmt': '{:d}({:d},{:d}) - {:d}({:d},{:d}), v = {:d} - {:d}', 'series': [0, 1, 2, 4, 5, 6, 3, 7], 'tag': 'Asymmetric top with generic vibrational transition QNs'},
                       {'fmt':'{:d}({:d},{:d}) - {:d}({:d},{:d})', 'series': [0, 1, 2, 4, 5, 6], 'tag': 'Generic asymmetric top, no vibrational labelling.'},
                       {'fmt':'', 'series':[0], 'tag': 'Monodeuterated methanol, CH2DOH'},
                       {'fmt':'', 'series':[1], 'tag': 'Generic asymmetric top with methyl-like internal rotation'},
                       {'fmt':'', 'series':[2], 'tag': 'n-propyl cyanide, gauche/anti combined fit'},
                       {'fmt':'', 'series':[3], 'tag': 'Ethanol, gauche/anti combined fit'},
                       {'fmt':'', 'series':[4], 'tag': 'Dimethyl ether, two methyl rotor fit (CDMS)'},
                       {'fmt':'', 'series':[5], 'tag': 'Methyl mercaptan, internal rotation with torsional excited states'}
                       ),

                224: ({'fmt': 'N = {:d}, J = {} - {}, p = {:d} - {:d}, F = {:d} - {:d}', 'series': [0, 2, 6, 1, 5, 3, 7], 'tag': 'Hunds case A with hyperfine and parity -- generic', 'frac_series': [2,6], 'frac_shift': -1},
                      {'fmt': '', 'series': [0], 'tag': 'Hunds case A with hyperfine splitting, e.g. NO'},
                      ),

                234: ({'fmt':'', 'series': [0], 'tag': 'Hunds case A with hyperfine splitting with half-integer quanta'},
                      ),

                245: ({'fmt':'', 'series': [0], 'tag': 'Hunds case (a) with two hyperfine splittings, e.g. N17O'},
                      ),

                255: ({'fmt': 'J = {} - {}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F<sub>2</sub> = {:d} - {:d}', 'series':[2, 7, 1, 6, 3, 8, 4, 9], 'frac_series':[2,7],  'frac_shift': -1, 'tag': 'Linear molecule with two quads and parity'},
                      ),

                101: ({'fmt': 'J = {:d} - {:d}', 'series': [0, 1], 'tag': 'Linear molecule'}, ),

                102: ({'fmt': 'J = {:d} - {:d}', 'series':[0, 1], 'tag': 'Linear molecule in S state'},
                      ),

                1202: ({'fmt': 'J = {:d} - {:d}, v = {:d} - {:d}', 'series': [0, 2, 1, 3], 'tag': 'Linear molecule with generic vibrational QNs'},
                       ),

                325: ({'fmt': 'N(K<sub>a</sub>,K<sub>c</sub>) = {:d}({:d},{:d}) - {:d}({:d},{:d}), J = {} - {}, F = {:d} - {:d}', 'series': [0, 1, 2, 5, 6, 7, 3, 8, 4, 9], 'frac_series': [3,8], 'frac_shift': -1, 'tag': 'Asymmetric top with half-integer electronic spin + nuclear quad coupling'},
                      ),

                1335: ({'fmt':'N = {:d} - {:d}, J = {} - {}, p = {:d} - {:d}, F = {} - {}', 'series':[0, 5, 3, 8, 1, 6, 4, 9], 'frac_series': [3,8,4,9], 'frac_shift': -1, 'tag': 'Symmetric top with parity and half-integer electronic spin'},
                       ),
                1325: ({'fmt':'N = {:d} - {:d}, J = {} - {}, p = {:d} - {:d}, F = {} - {}', 'series':[0, 5, 3, 8, 1, 6, 4, 9], 'frac_series': [3,8,4,9], 'frac_shift': -1, 'tag': 'Symmetric top with parity and half-integer electronic spin'},
                       ),

                1356: ({'fmt':'N = {:d} - {:d}, J + 1/2 = {} - {}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F + 1/2 = {} - {}', 'series': [0, 6, 3, 9, 1, 7, 4, 10, 5, 11], 'frac_series': [3,9,5,11], 'frac_shift': -1, 'tag': 'Symmetric top with parity and half-integer electronic spin and single half-integer quad'},
                       ),

                1366: ({'fmt': 'N = {:d} - {:d}, J + 1/2 = {} - {}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F = {:d} - {:d}', 'series': [0, 6, 3, 9, 1, 7, 4, 10, 5, 11], 'frac_series': [3,9], 'frac_shift': -1, 'tag': 'Symmetric top with parity and half-integer electronic spin and single integral quad'},
                       ),

                6315: ({'fmt': 'N(KaKc) = {:d}({:d}, {:d}) - {:d}({:d}, {:d}), S = {:d} - {:d}, F = {:d} - {:d}', 'series': [0, 1, 2, 5, 6, 7, 3, 8, 4, 9], 'tag': 'Asymmetric top with crazy coupling with reduced spin QN.'},
                       ),
                       
                1325: ({'fmt': '', 'series': [0], 'tag': 'JPL entry for Iodine monoxide, e.g. Hund\'s \'a\' case for pi1/2 and 3/2cases with nuclear hyperfine and vibrational states'},
                    )

                }

    try:
        temp = fmt_dict[fmt_idx]
        HasFractions = False

        frac_s = None
        frac_sh = None
    except KeyError:
        if qn_series.shape[0] != 2:
            raise MissingQNFormatException("QN format index %i is not recognized by the program. "
                                           "Please add manually." % fmt_idx)
        else:
            fmt = '{:d} - {:d}'
            order = [0, 1]

    else:
        if len(fmt_dict[fmt_idx]) > 1:
            if choice_idx is None:
                choices = ['%s' % x['tag'] for x in fmt_dict[fmt_idx]]
                ch = eg.choicebox(msg='Choose the desired QN format.', choices=choices)
                choice_idx = choices.index(ch)
            #print 'fmt_idx: %s \t\t choice_idx: %s' %(fmt_idx, choice_idx)
            fmt_style = fmt_dict[fmt_idx][choice_idx]

            if not fmt_style['fmt'] and len(fmt_style['series']) == 1:

                customChoice = fmt_style['series'][0] # Needs custom routine to edit style

            else:
                fmt = fmt_style['fmt']
                order = fmt_style['series']

                try:
                    frac_s = fmt_style['frac_series']
                    frac_sh = fmt_style['frac_shift']
                except KeyError:
                    pass
                else: 
                    HasFractions = True

        else:
            fmt_style = fmt_dict[fmt_idx][0]
            if not fmt_style['fmt'] and len(fmt_style['series']) == 1:
                customChoice = fmt_style['series'][0]
                # Needs custom routine to edit style
            else:
                fmt = fmt_style['fmt']
                order = fmt_style['series']

                try:
                    frac_s = fmt_style['frac_series']
                    frac_sh = fmt_style['frac_shift']
                except KeyError:
                    pass
                else: 
                    HasFractions = True

        if customChoice is not None:

            if fmt_idx == 1404:

                if customChoice == 0:

                    fmt = '{:d}({:d},{:d}) - {:d}({:d},{:d})'
                    if int(qn_series[3]) == 0:
                        fmt += ", e<sub>0</sub>"
                    elif int(qn_series[3]) == 1:
                        fmt += ", e<sub>1</sub>"
                    elif int(qn_series[3]) == 2:
                        fmt += ", o<sub>1</sub>"
                    order = [0, 1, 2, 4, 5, 6]

                if customChoice == 1:
                    fmt = '{:d}({:d},{:d}) - {:d}({:d},{:d})'
                    if int(qn_series[3]) == 0:
                        fmt += ", A"
                    elif int(qn_series[3]) == 1:
                        fmt += ", E"
                    order = [0, 1, 2, 4, 5, 6]

                if customChoice == 2:
                    fmt = '{:d}({:d},{:d}) - {:d}({:d},{:d})'
                    if int(qn_series[3]) == 0:
                        fmt += ", anti"
                    elif int(qn_series[3]) == 1:
                        fmt += ", gauche"
                    order = [0, 1, 2, 4, 5, 6]

                if customChoice == 3:
                    fmt = '{:d}({:d},{:d}) - {:d}({:d},{:d})'
                    if int(qn_series[3]) == 0:
                        fmt += ", g<sup>+</sup>"
                    elif int(qn_series[3]) == 1:
                        fmt += ", g<sup>-</sup>"
                    else:
                        fmt += ", anti"
                    order = [0, 1, 2, 4, 5, 6]

                if customChoice == 4:
                    fmt = '{:d}({:d},{:d}) - {:d}({:d},{:d})'
                    if int(qn_series[3]) == 0:
                        fmt += ", AA"
                    elif int(qn_series[3]) == 1:
                        fmt += ", EE"
                    elif int(qn_series[3]) == 3:
                        fmt += ", EA"
                    else:
                        fmt += ", AE"
                    order = [0, 1, 2, 4, 5, 6]
                
                if customChoice == 5:
                    # First build upper state QNs
                    fmt = '{:d}({:d},{:d})'
                    if int(qn_series[1]) > 0:
                        fmt += "<sup>+</sup>"
                    else:
                        fmt += "<sup>-</sup>"
                    fmt += ' - {:d}({:d},{:d})'
                    # Now lower state
                    if int(qn_series[5]) > 0:
                        fmt += "<sup>+</sup>"
                    else:
                        fmt += "<sup>-</sup>"
                    # Now A or E
                    if int(qn_series[3]) in [1, -2, 4]:
                        fmt += " E"
                    else:
                        fmt += " A"
                    # Now torsional state
                    if int(qn_series[3]) in [0,1]:
                        fmt += ', v<sub>t</sub> = 0'
                    elif int(qn_series[3]) in [-2, -3]:
                        fmt += ', v<sub>t</sub> = 1'
                    else:
                        fmt += ', v<sub>t</sub> = 2'
                    order = [0, 1, 2, 4, 5, 6]

            elif fmt_idx == 203:

                if customChoice == 0:

                    if int(qn_series[1]) < 0 and int(qn_series[4]) > 0:
                        if int(qn_series[0]) - int(qn_series[2]) == 1:
                            if int(qn_series[2]) % 2 == 1 :
                                fmt = u'J = {:d} - {:d}, &Omega; = 2, <i>f</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, &Omega; = 1, <i>f</i>'.encode('utf-8')
                        elif int(qn_series[0]) - int(qn_series[2]) == 0:
                            if int(qn_series[2]) % 2 == 1 :
                                fmt = u'J = {:d} - {:d}, &Omega; = 2, <i>f</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, &Omega; = 1, <i>f</i>'.encode('utf-8')
                        else:
                            fmt = u'J = {:d} - {:d}, &Omega; = 3, <i>f</i>'.encode('utf-8')

                    elif int(qn_series[1]) > 0 and int(qn_series[4]) < 0:

                        if int(qn_series[0]) - int(qn_series[2]) == 1:
                            if int(qn_series[2]) % 2 == 1 :
                                fmt = u'J = {:d} - {:d}, &Omega; = 2, <i>e</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, &Omega; = 1, <i>e</i>'.encode('utf-8')
                        elif int(qn_series[0]) - int(qn_series[2]) == 0:
                            if int(qn_series[2]) % 2 == 1:
                                fmt = u'J = {:d} - {:d}, &Omega; = 2, <i>e</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, &Omega; = 1, <i>e</i>'.encode('utf-8')
                        else:
                            fmt = u'J = {:d} - {:d}, &Omega; = 3, <i>e</i>'.encode('utf-8')
                    else:

                        if int(qn_series[0]) - int(qn_series[2]) == 1:
                            if int(qn_series[2]) % 2 == 1:
                                fmt = u'J = {:d} - {:d}, &Omega; = 2, <i>e/f</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, &Omega; = 1, <i>e/f</i>'.encode('utf-8')
                        elif int(qn_series[0]) - int(qn_series[2]) == 0:
                            if int(qn_series[2]) % 2 == 1 :
                                fmt = u'J = {:d} - {:d}, &Omega; = 2, <i>e/f</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, &Omega; = 1, <i>e/f</i>'.encode('utf-8')
                        else:
                            fmt = u'J = {:d} - {:d}, &Omega; = 3, <i>e/f</i>'.encode('utf-8')
                    order = [2, 5]

            elif fmt_idx == 213:  # For Hund's case (b) with Lambda doubling

                if customChoice == 0:

                    HasFractions = True
                    frac_sh = -1

                    if qn_series[1] == '1':
                        if int(qn_series[2])-int(qn_series[0]) == 1:
                            fmt = u'J = {} - {}, &Omega; = 3/2, <i>e</i>'.encode('utf-8')
                        else:
                            fmt = u'J = {} - {}, &Omega; = 1/2, <i>e</i>'.encode('utf-8')
                    else:
                        if int(qn_series[2])-int(qn_series[0]) == 1:
                            fmt = u'J = {} - {}, &Omega; = 3/2, <i>f</i>'.encode('utf-8')
                        else:
                            fmt = u'J = {} - {}, &Omega; = 1/2, <i>f</i>'.encode('utf-8')
                    order = [0, 3]
                
                elif customChoice == 1:

                    HasFractions = True
                    frac_sh = -1
                    
                    if int(qn_series[2]) - int(qn_series[0]) == 1: # pi3/2
                        if int(qn_series[1]) > 0: # e parity
                            fmt = u'J = {} - {}, &Omega; = 3/2, <i>e</i>'.encode('utf-8')
                        else:
                            fmt = u'J = {} - {}, &Omega; = 3/2, <i>f</i>'.encode('utf-8')
                    else:
                        if int(qn_series[2]) - int(qn_series[0]) == 0: #pi1/2
                            if int(qn_series[1]) < 0: #e parity 
                                fmt = u'J = {} - {}, &Omega; = 3/2, <i>e</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {} - {}, &Omega; = 3/2, <i>f</i>'.encode('utf-8')
                    order = [0, 3]
                                

            elif fmt_idx == 234 or fmt_idx == 224:

                if customChoice == 0:

                    # Rewrite qn_series to have fractional strings
                    HasFractions = True
                    
                    
                    if int(qn_series[2]) - int(qn_series[0]) == 1:
                        if int(qn_series[0]) <= 5:
                                frac_sh = +1 # N = J - 0.5 if J <= 5.5 for omega = 3/2
                        else:
                                frac_sh = -1 # N = J + 0.5 if J >= 5.5 

                        if int(qn_series[1]) == 1 and int(qn_series[5]) == -1:

                            fmt = u'J = {} - {}, &Omega; = 3/2, F = {}<sup>+</sup> - {}<sup>-</sup>'
                        else:
                            fmt = u'J = {} - {}, &Omega; = 3/2, F = {}<sup>-</sup> - {}<sup>+</sup>'
                    else:
                        if int(qn_series[0]) <= 5:
                            frac_sh = -1
                        else:
                            frac_sh = +1

                        if int(qn_series[1]) == 1 and int(qn_series[5]) == -1:
                            fmt = u'J = {} - {}, &Omega; = 1/2, F = {}<sup>+</sup> - {}<sup>-</sup>'
                        else:
                            fmt = u'J = {} - {}, &Omega; = 1/2, F = {}<sup>-</sup> - {}<sup>+</sup>'
                    order = [0, 4, 3, 7]

            elif fmt_idx == 245:
                if customChoice == 0:

                    HasFractions = True
                    frac_sh = -1

                    if int(qn_series[2]) - int(qn_series[0]) == 1:
                        if int(qn_series[1]) == 1 and int(qn_series[5]) == -1:
                            fmt = u'J = {} - {}, &Omega; = 3/2, F<sub>1</sub> = {}<sup>+</sup> - {}<sup>-</sup>' \
                                  u', F<sub>2</sub> = {}<sup>+</sup> - {}<sup>-</sup>'
                        else:
                            fmt = u'J = {} - {}, &Omega; = 3/2, F<sub>1</sub> = {}<sup>+</sup> - {}<sup>-</sup>' \
                                  u', F<sub>2</sub> = {}<sup>+</sup> - {}<sup>-</sup>'
                    else:
                        if int(qn_series[1]) == 1 and int(qn_series[5]) == -1:
                            fmt = u'J = {} - {}, &Omega; = 1/2, F<sub>1</sub> = {}<sup>+</sup> - {}<sup>-</sup>' \
                                  u', F<sub>2</sub> = {}<sup>+</sup> - {}<sup>-</sup>'
                        else:
                            fmt = u'J = {} - {}, &Omega; = 1/2, F<sub>1</sub> = {}<sup>+</sup> - {}<sup>-</sup>' \
                                  u', F<sub>2</sub> = {}<sup>+</sup> - {}<sup>-</sup>'
                    order = [0, 5, 3, 8, 4, 9]

            elif fmt_idx == 1303:

                if customChoice == 0:

                    if int(qn_series[2]) == 2:
                        if int(qn_series[1]) > 0 and int(qn_series[1]) > 0:
                            fmt = u'J = {:d} - {:d}, K = {:d} - {:d}'
                        else:
                            fmt = u'J = {:d} - {:d}, <sup>l</sup>K = {:d} - {:d}'

                    elif int(qn_series[2]) == 1:
                        if int(qn_series[1]) > 0 and int(qn_series[1]) > 0:
                            fmt = u'J = {:d} - {:d}, K = -{:d} - -{:d}'
                        else:
                            fmt = u'J = {:d} - {:d}, <sup>l</sup>K = -({:d}) - -({:d})'

                    order = [0, 3, 1, 4]

                elif customChoice == 1:

                    if int(qn_series[2]) == 0:
                            fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, A<sub>1</sub>'
                    elif int(qn_series[2]) == 1:
                            fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, A<sub>2</sub>'
                    elif int(qn_series[2]) == 2:
                            fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, B<sub>1</sub>'
                    elif int(qn_series[2]) == 3:
                            fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, B<sub>2</sub>'
                    elif int(qn_series[2]) == 4:
                            fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, E<sub>1</sub>, l = 1'
                    elif int(qn_series[2]) == 5:
                            fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, E<sub>1</sub>, l = -1'
                    elif int(qn_series[2]) == 6:
                            fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, E<sub>2</sub>, l = 1'
                    elif int(qn_series[2]) == 7:
                            fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, E<sub>2</sub>, l = -1'

                    if int(qn_series[5]) != int(qn_series[2]):
                        if int(qn_series[5]) == 0:
                            fmt += ' -> A<sub>1</sub>'
                        if int(qn_series[5]) == 1:
                            fmt += ' -> A<sub>2</sub>'
                        if int(qn_series[5]) == 2:
                            fmt += ' -> B<sub>1</sub>'
                        if int(qn_series[5]) == 3:
                            fmt += ' -> B<sub>2</sub>'
                        if int(qn_series[5]) == 4:
                            fmt += ' -> E<sub>1</sub>, l = 1'
                        if int(qn_series[5]) == 5:
                            fmt += ' -> E<sub>1</sub>, l = -1'
                        if int(qn_series[5]) == 6:
                            fmt += ' -> E<sub>2</sub>, l = 1'
                        if int(qn_series[5]) == 7:
                            fmt += ' -> E<sub>2</sub>, l = 2'

                    order = [0, 3, 1, 4]

                elif customChoice == 2:
                    if int(qn_series[2]) == 1:
                        fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, v<sub>5 = 1'
                    elif int(qn_series[2]) == 2:
                        fmt = u'J = {:d} - {:d}, K = {:d} - {:d}, v<sub>4 = 1'
                    if int(qn_series[5]) != int(qn_series[2]):
                        if int(qn_series[5] == 1):
                            fmt += ' -> v<sub>5</sub> = 1'
                        else:
                            fmt += ' -> v<sub>4</sub> = 1'
                    order = [0, 3, 1, 4]
        
            elif fmt_idx == 1325: 

                if customChoice == 0:
                    # Sample line:  294425.7040  0.0250 -2.4466 2   65.0997 35-1430011325 14 1 01517  13-1 01416 
# qn_series will look like this: [14, 1, 0, 15, 17, 13, -1, 0, 14, 16] or (14,1,0,15,17) -> (13,-1,0,14,16) for (N, p*K, v, J, F) 5-tuplet
                    HasFractions = True
                    frac_sh = -1 
                    frac_s = [3,4,8,9]
                    if qn_series[2] - qn_series[7] == 0: #delta_v = 0 

                        if qn_series[0] - qn_series[3] == 0: # N' - J' = 0 --> pi 1/2
                            
                            if qn_series[5] - qn_series[8] == 0: # N'' - J'' = 0 --> pi 1/2
                                fmt = u'N = {:d} - {:d}, J = {} - {}, &Lambda = {:d} - {:d}, F = {} - {}, v = {:d}, <sup>2</sup>&Pi<sub>1/2</sub> -> <sup>2</sup>&Pi<sub>1/2</sub>'
                            elif np.abs(qn_series[5] - qn_series[8]) >= 1: # N'' - J'' = 1 --> pi 3/2
                                fmt = u'N = {:d} - {:d}, J = {} - {}, &Lambda = {:d} - {:d}, F = {} - {}, v = {:d},  <sup>2</sup>&Pi<sub>1/2</sub> -> <sup>2</sup>&Pi<sub>3/2</sub>'

                        elif np.abs(qn_series[0] - qn_series[3]) >= 1: # N' - J' = 1 --> pi 3/2

                            if qn_series[5] - qn_series[8] == 0: # N'' - J'' = 0 --> pi 1/2
                                fmt = u'N = {:d} - {:d}, J = {} - {}, &Lambda = {:d} - {:d}, F = {} - {}, v = {:d}, <sup>2</sup>&Pi<sub>3/2</sub> -> <sup>2</sup>&Pi<sub>1/2</sub>'
                            elif np.abs(qn_series[5] - qn_series[8]) >= 1: # N'' - J'' = 1 --> pi 3/2
                                fmt = u'N = {:d} - {:d}, J = {} - {}, &Lambda = {:d} - {:d}, F = {} - {}, v = {:d}, <sup>2</sup>&Pi<sub>3/2</sub> -> <sup>2</sup>&Pi<sub>3/2</sub>'
                        order = [0, 5, 3, 8, 1, 6, 4, 9, 2]

                    else:
                        if qn_series[0] - qn_series[3] == 0: # N' - J' = 0 --> pi 1/2
                            
                            if qn_series[5] - qn_series[8] == 0: # N'' - J'' = 0 --> pi 1/2
                                fmt = u'N = {:d} - {:d}, J = {} - {}, &Lambda = {:d} - {:d}, F = {} - {}, v = {:d} - {:d}, <sup>2</sup>&Pi<sub>1/2</sub> -> <sup>2</sup>&Pi<sub>1/2</sub>'
                            elif np.abs(qn_series[5] - qn_series[8]) >= 1: # N'' - J'' = 1 --> pi 3/2
                                fmt = u'N = {:d} - {:d}, J = {} - {}, &Lambda = {:d} - {:d}, F = {} - {}, v = {:d} - {:d},  <sup>2</sup>&Pi<sub>1/2</sub> -> <sup>2</sup>&Pi<sub>3/2</sub>'

                        elif np.abs(qn_series[0] - qn_series[3]) >= 1: # N' - J' = 1 --> pi 3/2

                            if qn_series[5] - qn_series[8] == 0: # N'' - J'' = 0 --> pi 1/2
                                fmt = u'N = {:d} - {:d}, J = {} - {}, &Lambda = {:d} - {:d}, F = {} - {}, v = {:d} - {:d}, <sup>2</sup>&Pi<sub>3/2</sub> -> <sup>2</sup>&Pi<sub>1/2</sub>'
                            elif np.abs(qn_series[5] - qn_series[8]) >= 1: # N'' - J'' = 1 --> pi 3/2
                                fmt = u'N = {:d} - {:d}, J = {} - {}, &Lambda = {:d} - {:d}, F = {} - {}, v = {:d} - {:d}, <sup>2</sup>&Pi<sub>3/2</sub> -> <sup>2</sup>&Pi<sub>3/2</sub>'
                        order = [0, 5, 3, 8, 1, 6, 4, 9, 2, 7]      


    try: 
        if choice_idx is not None:
            if HasFractions:
                #print 'Fraction shift: %s \t\t Fraction series: %s \t\t QN list: %s'%(frac_sh, frac_s, qn_series)
                new_series = make_frac(order, qn_series, shift=frac_sh, frac_series=frac_s) 
                try:
                    return fmt.format(*[new_series[x] for x in order]), choice_idx
                except:
                    print new_series, qn_series
                    raise
            else:
                return fmt.format(*[int(qn_series[x]) for x in order]), choice_idx
        else:
            if HasFractions:
                #print 'Fraction shift: %s \t\t Fraction series: %s \t\t QN list: %s'%(frac_sh, frac_s, qn_series)
                new_series = make_frac(order, qn_series, shift=frac_sh, frac_series=frac_s)
                return fmt.format(*[new_series[x] for x in order]), ''
            else:
                return fmt.format(*[int(qn_series[x]) for x in order]), ''
    except:
        print('WARNING: If you are seeing this error it probably means the QN code for this CAT has not been programmed into QNFormat. Please contact your friendly local developer for help (e.g. Nate)')
        raise