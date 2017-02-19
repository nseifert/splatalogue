import pandas as pd
import MySQLdb as mysqldb
from tqdm import tqdm
from collections import OrderedDict

def init_sql_db():
    def rd_pass():
        return open('pass.pass','r').read()

    HOST = "127.0.0.1"
    LOGIN = "nseifert"
    PASS = rd_pass()
    db = mysqldb.connect(host=HOST, user=LOGIN, passwd=PASS.strip(), port=3307)
    db.autocommit(False)
    print 'MySQL Login Successful.'

    return db



if __name__ == '__main__':



    ALMA_BANDS = OrderedDict({'BAND4': (125000.0, 163000.0), 'BAND5': (163000.0, 211000.0), 'BAND8': (385000.0, 500000.0)})
    #ALMA_BANDS = OrderedDict({'BAND5': (163000.0, 211000.0)})
    OUTPUT_DELIMITER = ':'

    # First pull molecules

    db = init_sql_db()
    cursor = db.cursor()
    cursor.execute("USE splat")
    print 'Connected to database successfully.'

    SPECIES_COLUMNS = ('species_id', 's_name_noparens', 'chemical_name', 'planet', 'ism_hotcore', 'ism_diffusecloud', 'ism_darkcloud', 'comet',
                       'extragalactic', 'AGB_PPN_PN', 'Top20')
    MAIN_COLUMNS = ('line_id', 'orderedfreq', 'resolved_QNs', 'sijmu2', 'obsintensity_Lovas_NIST', 'upper_state_energy_K')
    cursor.execute("SELECT %s FROM species WHERE known_ast_molecules = 1 AND chemical_name not like \"%%Aluminum%%\"" %', '.join(SPECIES_COLUMNS))
    species = cursor.fetchall()
    cursor.close()
    species_dict = {}
    for entry in tqdm(species):
        cursor = db.cursor()
        species_id = entry[0]

        for i, key in enumerate(ALMA_BANDS.keys()):
            band = ALMA_BANDS[key]
            cursor.execute("SELECT %s FROM main where Lovas_NRAO = 1 AND species_id = %s"
                           " AND orderedfreq >= %s AND orderedfreq <= %s AND `v3.0` = 3"
                           %(', '.join(MAIN_COLUMNS), species_id, band[0], band[1]))
            data_temp = pd.DataFrame.from_records(data=list(cursor.fetchall()), columns=MAIN_COLUMNS)
            if i == 0:
                species_dict[species_id] = data_temp
            else:
                species_dict[species_id] = species_dict[species_id].append(data_temp, ignore_index=True)

        # Now append species_columns to linelist
            for i, val in enumerate(SPECIES_COLUMNS):
                species_dict[species_id][val] = entry[i]

        cursor.close()



    final = pd.concat([species_dict[k] for k in species_dict.keys()], ignore_index = True)

    # Rename columns and rearrange for final output
    final = final.rename(columns={'obsintensity_Lovas_NIST': 'Lovas Int', 'upper_state_energy_K': 'E_up_K', 'Top20': 'Top 20', 'chemical_name': 'chemical name'})

    output_order = 'line_id:species_id:s_name_noparens:chemical name:orderedfreq:resolved_QNs:sijmu2:Lovas Int:E_up_K:' \
                   'planet:ism_hotcore:ism_diffusecloud:comet:' \
                   'ism_darkcloud:extragalactic:AGB_PPN_PN:Top 20'.split(':')

    import numpy as np
    final['line_id'] = final['line_id'].astype(np.int)
    final['resolved_QNs'] = final['resolved_QNs'].str.replace("\n", ' ')
    final.loc[final['Lovas Int'].isnull(), 'Lovas Int'] = 'NULL'

    final[output_order].to_csv('AlmaOTBands4_5_8_ALL_ISM.dat', sep=':', index=False)

