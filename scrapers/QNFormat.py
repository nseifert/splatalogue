# -*- coding: utf-8 -*-
__author__ = 'nate'
import pandas as pd


class MissingQNFormatException(Exception):
    pass


def format_it(fmt_idx, qn_series):
    fmt_dict = {202: ('{:d}({:d}) - {:d}({:d}',[0, 1, 2, 3] ), # Sym top
                303: ('{:d}({:d},{:d}) - {:d}({:d},{:d})', [0, 1, 2, 3, 4, 5] ),  # Asym top
                304: ('{:d}({:d},{:d}) - {:d}({:d},{:d}), F= {:d} - {:d}', [0, 1, 2, 4, 5, 6, 3, 7]), # Asym top w/ 1 quad
                314: ('{:d}({:d},{:d}) - {:d}({:d},{:d}), 2F = {:d} - {:d}', [0, 1, 2, 4, 5, 6, 3, 7]),
                346: ('N(KaKc) = {:d}({:d},{:d}) - {:d}({:d},{:d}), J+1/2 = {:d} - {:d}, F+1/2 = {:d} - {:d}', [0, 1, 2, 6, 7, 8, 3, 9, 4, 11]),
                112: ('N = {:d} - {:d}, 2J = {:d} - {:d}', [0, 2, 1, 3]), # Hund's case A (?) linear
                113: ('N = {:d} - {:d}, J = {:d} - {:d}, F+1/2 = {:d} - {:d}', [1, 4, 0, 3, 2, 5]),
                123: ('N = {:d} - {:d}, J + 1/2 = {:d} - {:d}, F = {:d} - {:d}', [0, 3, 1, 4, 2, 5]),
                1304: ('N = {:d} - {:d}, J = {:d} - {:d}', [1, 4, 3, 7]),
                1404: ('{:d}({:d},{:d}) - {:d}({:d},{:d}), m = {:d}', [0, 1, 2, 4, 5, 6, 3]),
                #1404: ('{:d}({:d},{:d}) - {:d}({:d},{:d})', [0, 1, 2, 4, 5, 6]),
                #  224: ('N = {:d}, J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F = {:d} - {:d}', [0, 2, 6, 1, 5, 3, 7]),
                255: ('J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F<sub>2</sub> = {:d} - {:d}', [2, 7, 1, 6, 3, 8, 4, 9]),
                102: ('N = {:d} - {:d}, J = {:d} - {:d}', [0, 2, 1, 3]),
                1202: ('J = {:d} - {:d}, v = {:d} - {:d}', [0, 2, 1, 3]),
                325: ('N(KaKc) = {:d}({:d},{:d}) - {:d}({:d},{:d}), J+1/2 = {:d} - {:d}, F = {:d} - {:d}', [0, 1, 2, 5, 6, 7, 3, 8, 4, 9]),
                1335: ('N = {:d} - {:d}, J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F + 1/2 = {:d} - {:d}', [0, 5, 3, 8, 1, 6, 4, 9]),
                1356: ('N = {:d} - {:d}, J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F + 1/2 = {:d} - {:d}', [0, 6, 3, 9, 1, 7, 4, 10, 5, 11]),
                1366: ('N = {:d} - {:d}, J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F = {:d} - {:d}', [0, 6, 3, 9, 1, 7, 4, 10, 5, 11])
                }

    # if fmt_idx == 1404:  # For deuterated methanol, CH2DOH
    #     fmt = '{:d}({:d},{:d}) - {:d}({:d},{:d})'
    #     if int(qn_series[3]) == 0:
    #         fmt += ", e<sub>0</sub>"
    #     elif int(qn_series[3]) == 1:
    #         fmt += ", e<sub>1</sub>"
    #     elif int(qn_series[3]) == 2:
    #         fmt += ", o<sub>1</sub>"
    #     order = [0, 1, 2, 4, 5, 6]

    if fmt_idx == 203:

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
                if int(qn_series[2]) % 2 == 1 :
                    fmt = u'J = {:d} - {:d}, O = 2, <i>e</i>'.encode('utf-8')
                else:
                    fmt = u'J = {:d} - {:d}, O = 1, <i>e</i>'.encode('utf-8')
            else:
                fmt = u'J = {:d} - {:d}, O = 3, <i>e</i>'.encode('utf-8')
        else:

            if int(qn_series[0]) - int(qn_series[2]) == 1:
                if int(qn_series[2]) % 2 == 1 :
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

    elif fmt_idx == 234 or fmt_idx == 224:  # NO Hund's case (a) with hyperfine splitting
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

    elif fmt_idx == 245:  # N-17O Hund's case (a) with two hyperfine splittings
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

    elif fmt_idx == 1303:  # CH3CN v8 = 1, for instance
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

    elif qn_series.shape[0] == 2:  # Any sort of linear molecule

        fmt = '{:d} - {:d}'
        order = [0, 1]

    else:

        try:
            fmt, order = fmt_dict[fmt_idx]
        except KeyError:
            raise MissingQNFormatException("QN format index %i is not recognized by the program. "
                                       "Please add manually." % fmt_idx)

    return fmt.format(*[int(qn_series[x]) for x in order])
