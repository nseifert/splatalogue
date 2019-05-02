# Nate's list of things to do


### Species_id between old <--> 2019 databases

Currently, the 2019 database has no species in it (May 1). As we go ahead and populate that new 2019 database, the first species we add from, say, CDMS, will be assigned species_id = 1. However, this will almost definitely conflict with the species that is assigned species_id = 1 in the old table.

Therefore, we need to have a new species_id system for this temporary propagation of 2019 until we are ready to merge good, old data into the new database. My suggestion:

1. When you select a species from CDMS/JPL, the code will re-enter into the `splat` database, pull the list of species from that species, and have the user select the best species, or select new species.

    1. If the new entry into `splat_2019` is for a molecule already in `splat`, then set the 2019 species_id = 100 000 + species_id set for that molecule in `splat`. For instance, if methyl formate has species_id = 25 in `splat`, then a new entry for `splat_2019` will have species id 100 025.

    2. If the new entry into `splat_2019` is a new molecule not already in `splat`, then set the 2019 species_id = 1 000 000 + max(species_id_2019). So if this new entry would be assigned species_id = 11 (starting at 1) for splat_2019, then its temporary species_id will be 1 000 011.  