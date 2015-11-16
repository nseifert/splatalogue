__author__ = 'nate'
import pandas as pd


class MissingQNFormatException(Exception):
    pass


def format_it(fmt_idx, qn_series):

    if qn_series.shape[0] == 2:  # Any sort of linear molecule
        fmt = '{:d} - {:d}'
        order = [0, 1]
    elif fmt_idx == 202:  # Sym top
        fmt = '{:d}({:d}) - {:d}({:d}'
        order = [0, 1, 2, 3]
    elif fmt_idx == 303:  # Asym top
        fmt = '{:d}({:d},{:d}) - {:d}({:d},{:d})'
        order = [0, 1, 2, 3, 4, 5]
    elif fmt_idx == 304:  # Asym top with one quad
        fmt = '{:d}({:d},{:d}) - {:d}({:d},{:d}), F={:d} - {:d}'
        order = [0, 1, 2, 4, 5, 6, 3, 7]
    else:
        raise MissingQNFormatException("QN format index %i is not recognized by the program. "
                                       "Please add manually." % fmt_idx)

    return fmt.format(*[int(qn_series[x]) for x in order])
