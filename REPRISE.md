# Reprise - projet entrainement BLADE

Ecrit le 29/08/2026 a 02h22.
Ce fichier est la seule chose a lire pour reprendre. Il est reecrit a
chaque atterrissage, donc il est toujours a jour ou il n'existe pas.

## Ou on en est
- Palier : 08 franchi sur 10. Palier 9 non commence.
- Tests au banc : 52

## Ce qui vient d'etre fait et tient debout
- Huit paliers verifies en Blender 5.2, 52 tests au banc.
- Scene de travail du palier 8 : projets/entrainement/00_scenes/palier8_matiere_v001.blend - c'est elle qui fait foi, rien n'a ete perdu.
- La sauvegarde session_28_08.blend faite par Adrien contient les objets temporaires du banc (_hi, _lo), pas les boulons du palier 8.

## PROCHAINE ACTION

> AU CHOIX D'ADRIEN. (a) Palier 9 : addon_blade/ dans le projet entrainement, commencer par __init__.py plus le seul operateur visserie, de bout en bout. (b) Brancher geo.py sur le projet capitales, qui poursuit le meme but avec des donnees reelles - c'est la que l'entrainement devient livrable.

## Laisse en suspens - a ne pas croire acquis
- Escalier sans contremarches ni limon ; roulement sans cage ; boulon sans chanfreins.
- Table ISO 4014 recitee, jamais confrontee a la norme.
- Depot Git absent : les voies nocturnes repartent de zero.

## Inventaire

Modules : bielle.py, cloture.py, engrenage.py, escalier.py, gameready.py, geo.py, linter.py, matiere.py, roulement.py, visserie.py

Scenes : palier2_boulon_v002.blend, palier2_filetage_v001.blend, palier3_roulement_v001.blend, palier4_gameready_v001.blend, palier5_escalier_v001.blend, palier6_osm_v001.blend, palier7_engrenages_v001.blend, palier8_matiere_v001.blend
