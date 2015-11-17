__author__ = 'nate'
import pandas as pd


class MissingQNFormatException(Exception):
    pass


def format_it(fmt_idx, qn_series):
    fmt_dict = {202: ('{:d}({:d}) - {:d}({:d}',[0, 1, 2, 3] ), # Sym top
                303: ('{:d}({:d},{:d}) - {:d}({:d},{:d})', [0, 1, 2, 3, 4, 5] ),  # Asym top
                304: ('{:d}({:d},{:d}) - {:d}({:d},{:d}), F= {:d} - {:d}', [0, 1, 2, 4, 5, 6, 3, 7]), # Asym top w/ 1 quad
                112: ('N = {:d} - {:d}, 2J = {:d} - {:d}', [0, 2, 1, 3]), # Hund's case A (?) linear
                1404: ('{:d}({:d},{:d}) - {:d}({:d},{:d}), v= {:d} - {:d}', [0, 1, 2, 4, 5, 6, 3, 7])}


    if qn_series.shape[0] == 2:  # Any sort of linear molecule

        fmt = '{:d} - {:d}'
        order = [0, 1]

    else:

        try:
            fmt, order = fmt_dict[fmt_idx]
        except KeyError:
            raise MissingQNFormatException("QN format index %i is not recognized by the program. "
                                       "Please add manually." % fmt_idx)

    return fmt.format(*[int(qn_series[x]) for x in order])
