Un script pour extraire d'un fichier osm les informations concernant les
rivières. Le schéma pris en compte est celui-là
http://wiki.openstreetmap.org/wiki/User:Frodrigo/Relation:Waterway

Pour extraire les informations, il faut éventuellement modifier update.sh (pour
le faire pointer vers le fichier osm qui vous intéresse) puis le lancer.

Un dossier htmloutput sera créé. Il contiendra:
Un fichier index.html contenant la liste des rivières et leurs affluents.
Un fichier html par rivière. Ce fichier affichera pour la rivière, sa longueure
totale (basée sur le plus long chemin obtenu en parcourant les composants de la
relation), la liste des commune traversées, et la liste des ponts qui enjambent
la rivière.
