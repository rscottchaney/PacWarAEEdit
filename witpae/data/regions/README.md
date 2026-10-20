# Region file

`Kull_Regions_v131a.txt` is the region file by Kull, version 1.31a, as
distributed in the `region-mappings` folder of WitPTracker AE Release 1.11. It
is bundled unchanged and is read by `witpae/regions.py`.

Format: one line per location, four TAB-separated fields:

    location id <TAB> name <TAB> region id <TAB> region name

Lines end with a bare CR (old Mac style), so the file is marked `-text` in
`.gitattributes` and must not be converted. The location ids match the save's
location table (section 0x13 record index). A region name can appear under more
than one id ("Line Islands" is 20 and 36), so regions are told apart by id.
