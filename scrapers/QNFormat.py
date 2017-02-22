# -*- coding: utf-8 -*-
__author__ = 'nate'
import pandas as pd
import easygui as eg


class MissingQNFormatException(Exception):
    pass


def format_it(fmt_idx, qn_series, choice_idx=None):
    customChoice = None

    fmt_dict = {202: ({'fmt': '{:d}({:d}) - {:d}({:d})','series': [0, 1, 2, 3], 'tag':'Symmetric top'},
                      ),

                203: ({'fmt':'{:d}({:d}) - {:d}({:d}), F = {:d} - {:d}',
                       'series': [0, 1, 3, 4, 2, 5], 'tag': 'Symmetric top with 1 hyperfine nuclei.'},
                      {'fmt': '', 'series':[0], 'tag': 'Symmetric top with parity and weird electronic spin QN Omega (custom)'},
                      ),

                213: ({'fmt': '', 'series': [0], 'tag': 'Hunds Case B with Lambda doubling'},
                      ),

                303: ({'fmt':'{:d}({:d},{:d}) - {:d}({:d},{:d})', 'series':[0, 1, 2, 3, 4, 5], 'tag': 'Asymmetric top.' },
                      ),

                304: ({'fmt':'{:d}({:d},{:d}) - {:d}({:d},{:d}), F= {:d} - {:d}', 'series': [0, 1, 2, 4, 5, 6, 3, 7], 'tag': 'Asymmetric top with 1 hyperfine nuclei.'},
                      ),

                314: ({'fmt':'N(K<sub>a</sub>,K<sub>c</sub>) = {:d}({:d},{:d}) - {:d}({:d},{:d}), J + 1/2 = {:d} - {:d}', 'series': [0, 1, 2, 4, 5, 6, 3, 7],
                      'tag': 'Asymmetric top with non-zero total electronic spin'},
                      ),

                346: ({'fmt': 'N(K<sub>a</sub>,K<sub>c</sub>) = {:d}({:d},{:d}) - {:d}({:d},{:d}), J+1/2 = {:d} - {:d}, F+1/2 = {:d} - {:d}',
                       'series': [0, 1, 2, 6, 7, 8, 3, 9, 4, 11],
                      'tag': 'Asymmetric top with non-zero total electronic spin and 1 hyperfine nuclei'},
                      ),

                112: ({'fmt': 'N = {:d} - {:d}, 2J = {:d} - {:d}', 'series': [0, 2, 1, 3], 'tag': 'Hunds case (A) linear'},
                      ),

                113: ({'fmt': 'N = {:d} - {:d}, J = {:d} - {:d}, F+1/2 = {:d} - {:d}', 'series':[1, 4, 0, 3, 2, 5],
                       'tag': 'Linear molecule with singlet electronic spin and hyperfine nuclei'},
                      ),

                123: ({'fmt':'N = {:d} - {:d}, J + 1/2 = {:d} - {:d}, F = {:d} - {:d}', 'series':[0, 3, 1, 4, 2, 5],
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
                       {'fmt':'', 'series':[3], 'tag': 'Ethanol, gauche/anti combined fit'}
                       ),

                224: ({'fmt': 'N = {:d}, J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F = {:d} - {:d}', 'series': [0, 2, 6, 1, 5, 3, 7], 'tag': 'Hunds case A with hyperfine and parity -- generic'},
                      {'fmt': '', 'series': [0], 'tag': 'Hunds case A with hyperfine splitting, e.g. NO'},
                      ),

                234: ({'fmt':'', 'series': [0], 'tag': 'Hunds case A with hyperfine splitting with half-integer quanta'},
                      ),

                245: ({'fmt':'', 'series': [0], 'tag': 'Hunds case (a) with two hyperfine splittings, e.g. N17O'},
                      ),

                255: ({'fmt': 'J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F<sub>2</sub> = {:d} - {:d}', 'series':[2, 7, 1, 6, 3, 8, 4, 9], 'tag': 'Linear molecule with two quads and parity'},
                      ),

                102: ({'fmt': 'N = {:d} - {:d}, J = {:d} - {:d}', 'series':[0, 2, 1, 3], 'tag': 'Linear molecule in S state'},
                      ),

                1202: ({'fmt': 'J = {:d} - {:d}, v = {:d} - {:d}', 'series': [0, 2, 1, 3], 'tag': 'Linear molecule with generic vibrational QNs'},
                       ),

                325: ({'fmt': 'N(K<sub>a</sub>,K<sub>c</sub>) = {:d}({:d},{:d}) - {:d}({:d},{:d}), J+1/2 = {:d} - {:d}, F = {:d} - {:d}', 'series': [0, 1, 2, 5, 6, 7, 3, 8, 4, 9], 'tag': 'Asymmetric top with half-integer electronic spin + nuclear quad coupling'},
                      ),

                1335: ({'fmt':'N = {:d} - {:d}, J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F + 1/2 = {:d} - {:d}', 'series':[0, 5, 3, 8, 1, 6, 4, 9], 'tag': 'Symmetric top with parity and half-integer electronic spin'},
                       ),

                1356: ({'fmt':'N = {:d} - {:d}, J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F + 1/2 = {:d} - {:d}', 'series': [0, 6, 3, 9, 1, 7, 4, 10, 5, 11], 'tag': 'Symmetric top with parity and half-integer electronic spin and single half-integer quad'},
                       ),

                1366: ({'fmt': 'N = {:d} - {:d}, J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F = {:d} - {:d}', 'series': [0, 6, 3, 9, 1, 7, 4, 10, 5, 11], 'tag': 'Symmetric top with parity and half-integer electronic spin and single integral quad'},
                       ),

                6315: ({'fmt': 'N(KaKc) = {:d}({:d}, {:d}) - {:d}({:d}, {:d}), S = {:d} - {:d}, F = {:d} - {:d}', 'series': [0, 1, 2, 5, 6, 7, 3, 8, 4, 9], 'tag': 'Asymmetric top with crazy coupling with reduced spin QN.'},
                       )

                }

    try:
        temp = fmt_dict[fmt_idx]
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

            fmt_style = fmt_dict[fmt_idx][choice_idx]

            if not fmt_style['fmt'] and len(fmt_style['series']) == 1:
                customChoice = fmt_style['series'][0]
                # Needs custom routine to edit style
            else:
                fmt = fmt_style['fmt']
                order = fmt_style['series']

        else:
            fmt_style = fmt_dict[fmt_idx][0]
            if not fmt_style['fmt'] and len(fmt_style['series']) == 1:
                customChoice = fmt_style['series'][0]
                # Needs custom routine to edit style
            else:
                fmt = fmt_style['fmt']
                order = fmt_style['series']

        if customChoice:

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

            elif fmt_idx == 203:

                if customChoice == 0:

                    if int(qn_series[1]) < 0 and int(qn_series[4]) > 0:
                        if int(qn_series[0]) - int(qn_series[2]) == 1:
                            if int(qn_series[2]) % 2 == 1 :
                                fmt = u'J = {:d} - {:d}, O = 2, <i>f</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, O = 1, <i>f</i>'.encode('utf-8')
                        elif int(qn_series[0]) - int(qn_series[2]) == 0:
                            if int(qn_series[2]) % 2 == 1 :
                                fmt = u'J = {:d} - {:d}, O = 2, <i>f</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, O = 1, <i>f</i>'.encode('utf-8')
                        else:
                            fmt = u'J = {:d} - {:d}, O = 3, <i>f</i>'.encode('utf-8')

                    elif int(qn_series[1]) > 0 and int(qn_series[4]) < 0:

                        if int(qn_series[0]) - int(qn_series[2]) == 1:
                            if int(qn_series[2]) % 2 == 1 :
                                fmt = u'J = {:d} - {:d}, O = 2, <i>e</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, O = 1, <i>e</i>'.encode('utf-8')
                        elif int(qn_series[0]) - int(qn_series[2]) == 0:
                            if int(qn_series[2]) % 2 == 1:
                                fmt = u'J = {:d} - {:d}, O = 2, <i>e</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, O = 1, <i>e</i>'.encode('utf-8')
                        else:
                            fmt = u'J = {:d} - {:d}, O = 3, <i>e</i>'.encode('utf-8')
                    else:

                        if int(qn_series[0]) - int(qn_series[2]) == 1:
                            if int(qn_series[2]) % 2 == 1:
                                fmt = u'J = {:d} - {:d}, O = 2, <i>e/f</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, O = 1, <i>e/f</i>'.encode('utf-8')
                        elif int(qn_series[0]) - int(qn_series[2]) == 0:
                            if int(qn_series[2]) % 2 == 1 :
                                fmt = u'J = {:d} - {:d}, O = 2, <i>e/f</i>'.encode('utf-8')
                            else:
                                fmt = u'J = {:d} - {:d}, O = 1, <i>e/f</i>'.encode('utf-8')
                        else:
                            fmt = u'J = {:d} - {:d}, O = 3, <i>e/f</i>'.encode('utf-8')
                    order = [2, 5]

            elif fmt_idx == 213:  # For Hund's case (b) with Lambda doubling

                if customChoice == 0:

                    if qn_series[1] == '1':
                        if int(qn_series[2])-int(qn_series[0]) == 1:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 3/2, <i>e</i>'.encode('utf-8')
                        else:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 1/2, <i>e</i>'.encode('utf-8')
                    else:
                        if int(qn_series[2])-int(qn_series[0]) == 1:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 3/2, <i>f</i>'.encode('utf-8')
                        else:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 1/2, <i>f</i>'.encode('utf-8')
                    order = [0, 3]

            elif fmt_idx == 234 or fmt_idx == 224:

                if customChoice == 0:

                    if int(qn_series[2]) - int(qn_series[0]) == 1:
                        if int(qn_series[1]) == 1 and int(qn_series[5]) == -1:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 3/2, F-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>'
                        else:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 3/2, F-1/2 = {:d}<sup>-</sup> - {:d}<sup>+</sup>'
                    else:
                        if int(qn_series[1]) == 1 and int(qn_series[5]) == -1:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 1/2, F-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>'
                        else:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 1/2, F-1/2 = {:d}<sup>-</sup> - {:d}<sup>+</sup>'
                    order = [0, 4, 3, 7]

            elif fmt_idx == 245:
                if customChoice == 0:
                    if int(qn_series[2]) - int(qn_series[0]) == 1:
                        if int(qn_series[1]) == 1 and int(qn_series[5]) == -1:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 3/2, F<sub>1</sub>-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>' \
                                  u', F<sub>2</sub>-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>'
                        else:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 3/2, F<sub>1</sub>-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>' \
                                  u', F<sub>2</sub>-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>'
                    else:
                        if int(qn_series[1]) == 1 and int(qn_series[5]) == -1:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 1/2, F<sub>1</sub>-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>' \
                                  u', F<sub>2</sub>-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>'
                        else:
                            fmt = u'J-1/2 = {:d} - {:d}, O = 1/2, F<sub>1</sub>-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>' \
                                  u', F<sub>2</sub>-1/2 = {:d}<sup>+</sup> - {:d}<sup>-</sup>'
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


    if choice_idx:
        return fmt.format(*[int(qn_series[x]) for x in order]), choice_idx
    else:
        return fmt.format(*[int(qn_series[x]) for x in order]), ''
