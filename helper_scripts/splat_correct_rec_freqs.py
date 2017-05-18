import MySQLdb as sqldb
from tqdm import tqdm

if __name__ == "__main__":

    def rd_pass():
        return open('pass.pass').read()

    db = sqldb.connect(host="127.0.0.1", user="nseifert",
                       passwd=rd_pass().strip(), port=3307)
    db.autocommit(False)
    print 'MySQL Login Successful.'

    cursor = db.cursor()
    cursor.execute("USE splat")

    """ This section is setting species that are known astronomical molecules
    that are set to potential/probable """
    # cursor.execute("SELECT species_id, chemical_name,
    #                 potential, probable, known_ast_molecules FROM species
    #                 WHERE (potential = 1 OR probable = 1) AND (known_ast_molecules = 1)")
    # for entry in cursor.fetchall():
    # 	if entry[2] == 1:
    # 		cursor.execute("UPDATE species SET potential = 0 WHERE species_id = %s" %entry[0])
    # 	if entry[3] == 1:
    # 		cursor.execute("UPDATE species SET probable = 0 WHERE species_id = %s" %entry[0])
    # cursor.close()

    """ This section is for correcting entries with multiple linelists that have Lovas_NRAO = 1
    set for more than one linelist.

    The correct priority for linelists should be those with intensity information first;
    if no intensity information is known, then most recent linelist should be recommended.
    This will also disable Lovas_NRAO for all molecules that are not known_ast. """

    # Set LOVAS_NRAO = 0 for all molecules that are not known_ast.
    # cursor.execute("SELECT species_id FROM species WHERE known_ast_molecules = 0")
    # non_ast_molecules = cursor.fetchall()
    # print 'There are %i non-AST molecules' % len(non_ast_molecules)
    # for entry in tqdm(non_ast_molecules):
    #     curs2 = db.cursor()
    #     curs2.execute("UPDATE main SET Lovas_NRAO = 0 WHERE species_id = %s" % entry[0])
    #     curs2.close()
    # print 'Finished correcting Lovas_NRAO for non-AST molecules.'

    # Now let's check for species that have multiple linelists with Lovas_NRAO = 1

    print 'Correcting recommended frequencies for all known AST molecules...'
    #cursor.execute("SELECT species_id FROM species WHERE known_ast_molecules = 1")
    #ast_molecules = cursor.fetchall()
    ast_molecules = [(155,)]

    for entry in tqdm(ast_molecules):
        HasLatestVersion = True 
        LatestVersion = 3

        curs2 = db.cursor()
        curs2.execute("SELECT ll_id FROM main WHERE species_id = %s" % entry[0])

        temp = set(curs2.fetchall())
        temp = [x[0] for x in temp]

        if len(temp) == 1:  # Only one choice.
            curs2.execute("UPDATE main SET Lovas_NRAO = 1 WHERE species_id = %s" % entry[0])

        else:
            if 11 in temp: 
                # Pull all values with observed intensity information from Lovas entries 
                curs2.execute("SELECT frequency, measfreq, obsintensity_Lovas_NIST FROM main WHERE species_id = %s"
                              " AND ll_id = 11 AND obsintensity_Lovas_NIST IS NOT NULL" % entry[0])
                freqs_and_ints = [filter(lambda a: a != 0.0, list(row)) for row in curs2]

                # Pull most recent linelist to append 
                curs2.execute("SELECT LineList, Date, v%i_0, v%i_0 FROM species_metadata WHERE species_id = %s"
                              " ORDER BY Date DESC" % (LatestVersion-1, LatestVersion, entry[0]))
                try:
                    res = curs2.fetchall()
                    linelist_rec = res[0]
                    if linelist_rec[-1] == 0 or linelist_rec[-1] is None:
                        HasLatestVersion = False
                except IndexError:  # No metadata entry for this species_id. We can skip.
                    continue

                # Now let's go through Lovas linelist with intensities and match to most recent linelist
                TOLERANCE = 2.0 # MHz
                for trans in freqs_and_ints:
                    freq_min = trans[0] - TOLERANCE
                    freq_max = trans[0] + TOLERANCE

                    # Search for transition in linelist
                    if HasLatestVersion:
                        cmd = "SELECT line_id, frequency, measfreq FROM main WHERE species_id = %s" \
                              " AND ll_id = %s AND `v%i.0` = %i AND (orderedfreq <= %s AND orderedfreq >= %s)"\
                              % (entry[0], linelist_rec[0], LatestVersion, LatestVersion, freq_max, freq_min)
                    else: 
                        cmd = "SELECT line_id, frequency, measfreq FROM main WHERE species_id = %s" \
                              " AND ll_id = %s AND `v%i.0` = %i AND (orderedfreq <= %s AND orderedfreq >= %s)"\
                              % (entry[0], linelist_rec[0], LatestVersion-1, LatestVersion-1, freq_max, freq_min)
                    curs2.execute(cmd)
                    # print 'For species %s and linelist %s we found:' %(entry[0], linelist_rec[0])
                    results = curs2.fetchall()
                    if not results:  # No matches
                        continue
                    else:
                        for line in results:
                            cmd = "UPDATE main SET obsintensity_Lovas_NIST = \'%s\' WHERE line_id = %s" %(trans[1], line[0])
                            curs2.execute(cmd)

            else:  # No Lovas data.
                curs2.execute("SELECT LineList, Date, v1_0, v2_0 FROM species_metadata "
                              "WHERE species_id = %s ORDER BY Date DESC" % entry[0])
                try:
                    linelist_rec = res[0]
                    if linelist_rec[-1] == 0 or linelist_rec[-1] is None:
                        HasLatestVersion = False

                except IndexError:  # No metadata entry for this species_id. We can skip.
                    continue



            # if 11 in temp:
            #     temp.remove(11)
            #     curs2.execute("UPDATE main SET Lovas_NRAO = 1 WHERE species_id = %s AND ll_id = 11" % entry[0])
            #     for val in temp:
            #         curs2.execute("UPDATE main SET Lovas_NRAO = 0 WHERE species_id = %s AND ll_id = %s" % (entry[0], val))

            # else:  # Need to figure out which linelist is most recently updated
            #     curs2.execute("SELECT LineList, Date FROM species_metadata WHERE species_id = %s ORDER BY Date DESC" % entry[0])
            #     try:
            #         linelist_rec = curs2.fetchall()[0][0]
            #     except IndexError:   # No metadata entry for this species_id. We can skip.
            #         continue
            if HasLatestVersion:
                curs2.execute("UPDATE main SET Lovas_NRAO = 1 WHERE species_id = %s "
                              "AND ll_id = %s AND `v%i.0` = 2" % (entry[0], linelist_rec[0], LatestVersion))
            else:
                curs2.execute("UPDATE main SET Lovas_NRAO = 1 WHERE species_id = %s "
                              "AND ll_id = %s AND `v1.0` = 1" % (entry[0], linelist_rec[0]))
            curs2.execute("UPDATE main SET Lovas_NRAO = 0 WHERE species_id = %s "
                          "AND ll_id != %s" % (entry[0], linelist_rec[0]))
            curs2.close()

    print 'Finished correcting known AST molecule recommended frequencies.'
