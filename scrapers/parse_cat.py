__author__ = 'nate'
import numpy as np
import pandas as pd
from itertools import izip_longest
import re

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

def cdms_parse(cat_inp):

    widths = [13, 8, 8, 2, 10, 3, 7, 4]  # Not including quantum numbers
    w_sum = sum(widths)
    parser = make_parser(tuple(widths))

    initial_list = []

    i = 0
    for line in cat_inp:  # Parses the CAT file into chunks

        if i == 0:
            qn_len = len(line)-w_sum
            widths.append(qn_len)
            parser = make_parser(widths)

        initial_list.append(parser(line))
        #print ('{}'.format(parser(line))
        i += 1

    # Let's put everything together to put into a dataframe
    parsed_list = []
    for row in initial_list:

        qns = re.findall('..', row[-1])  # splits QN entry into pairs
        up_done = False
        qns_up = []
        qns_down = []
        for val in qns:
            if val.strip() == '':
                up_done = True
                continue
            if not up_done:
                qns_up.append(int(val))
            else:
                qns_down.append(int(val))

        parsed_list.append([float(s.strip()) for s in row[:-1]] + [qns_up, qns_down])

    dtypes = [('freq', 'f8'), ('err', 'f8'), ('int', 'f8'), ('dof', 'i4'),
              ('Elow', 'f8'),('g_up', 'i4'), ('tag', 'i4'), ('qn_fmt', 'i4')]
    dtypes.extend([('qn_up_%s' %i,'i4') for i in range(len(parsed_list[0][-2]))])
    dtypes.extend([('qn_dwn_%s' %i,'i4') for i in range(len(parsed_list[0][-2]))])

    final_list = []
    for row in parsed_list:
        final_list.append(tuple(row[:-2]+row[-2]+row[-1]))


    nplist = np.zeros((len(final_list),), dtype=dtypes)
    nplist[:] = final_list

    return pd.DataFrame(nplist)


# Test routine for parsing

# if __name__ == "__main__":
#     stream = open('c060503.cat','r')
#     parsed_frame = cdms_parse(stream)
#
#     writer = pd.ExcelWriter('test.xlsx', engine='xlsxwriter')
#     parsed_frame.to_excel(writer, sheet_name='cat')
#     writer.save()
#





