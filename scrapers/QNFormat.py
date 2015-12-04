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
                112: ('N = {:d} - {:d}, 2J = {:d} - {:d}', [0, 2, 1, 3]), # Hund's case A (?) linear
                1404: ('{:d}({:d},{:d}) - {:d}({:d},{:d}), v= {:d} - {:d}', [0, 1, 2, 4, 5, 6, 3, 7]),
                224: ('N = {:d}, J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F = {:d} - {:d}', [0, 2, 6, 1, 5, 3, 7]),
                255: ('J + 1/2 = {:d} - {:d}, p = {:d} - {:d}, F<sub>1</sub> = {:d} - {:d}, F<sub>2</sub> = {:d} - {:d}', [2, 7, 1, 6, 3, 8, 4, 9]),
                102: ('N = {:d} - {:d}, J = {:d} - {:d}', [0, 2, 1, 3])
                }

    if fmt_idx == 213: # For Hund's case (b) with Lambda doubling
        if qn_series[1] == '1':
            if int(qn_series[2])-int(qn_series[0]) == 1:
                fmt = u'J-1/2: {:d} - {:d}, O = 3/2, <i>e</i>'.encode('utf-8')
                order = [0, 3]
            else:
                fmt = u'J-1/2: {:d} - {:d}, O = 1/2, <i>e</i>'.encode('utf-8')
                order = [0, 3]
        else:
            if int(qn_series[2])-int(qn_series[0]) == 1:
                fmt = u'J-1/2: {:d} - {:d}, O = 3/2, <i>f</i>'.encode('utf-8')
                order = [0, 3]
            else:
                fmt = u'J-1/2: {:d} - {:d}, O = 1/2, <i>f</i>'.encode('utf-8')
                order = [0, 3]

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
