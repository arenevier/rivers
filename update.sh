#!/bin/sh

wget http://download.geofabrik.de/osm/europe/france.osm.bz2
bunzip2 france.osm.bz2
rm france.osm.bz2
python river_import.py france.osm
python river_output.py
ssh renevier.net "rm -rf /var/httpd/main/maps/rivers"
