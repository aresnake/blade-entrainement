# Reprise - projet entrainement BLADE

Ecrit le 29/08/2026 a 02h38.
Ce fichier est la seule chose a lire pour reprendre. Il est reecrit a
chaque atterrissage, donc il est toujours a jour ou il n'existe pas.

## Ou on en est
- Palier : 08 sur 10 verifies en 5.2. Bascule engagee sur le projet capitales.
- Tests au banc : 52

## Ce qui vient d'etre fait et tient debout
- Depot pousse : github.com/aresnake/blade-entrainement (prive), commit 6c1b5de.
- geo.py branche sur capitales : quartier de l'Opera, 353 emprises reelles, livre dans capitales/00_scenes/opera_reel_osm_v001.blend.
- Les quatre taches planifiees reecrites SANS AUCUN FAIT PERISSABLE : elles ne portent que l'identite, le terrain, la discipline, et ou lire le reste.
- Panne silencieuse evitee : /areas/blender-entrainement.md avait atteint son plafond de 32 ko, toute consignation nocturne aurait echoue. Nouveau fichier blender-journal.md, et devoir d'entretien ajoute a chaque voie.

## PROCHAINE ACTION

> Etendre geo.py d'une fonction voies() qui extrait le reseau viaire OSM (highway=*) du meme secteur avec ses largeurs. Elle sert deux fois : retrancher l'espace public pour mesurer le coefficient d'emprise PAR ILOT, comparable aux 66 % de la reference d'Adrien ; et alimenter son gabarit 1902 avec les largeurs de rue REELLES, ce qui rend enfin vraie sa regle « la hauteur derive de la largeur de la rue ».

## Laisse en suspens - a ne pas croire acquis
- Depot PRIVE : les voies nocturnes ne peuvent pas le cloner. Decision d'Adrien en attente.
- blade_quartier_v1.tar.gz : n'existe que dans la conversation.
- Table ISO 4014 recitee, jamais confrontee a la norme.
- Paliers 9 et 10 verts en 5.0.1, sans verdict duo.
- Gabarit 1902 d'Adrien : sort ~2 m sous la mediane reelle de 18 m.

## Inventaire

Modules : bielle.py, cloture.py, engrenage.py, escalier.py, gameready.py, geo.py, linter.py, matiere.py, roulement.py, visserie.py

Scenes : palier2_boulon_v002.blend, palier2_filetage_v001.blend, palier3_roulement_v001.blend, palier4_gameready_v001.blend, palier5_escalier_v001.blend, palier6_osm_v001.blend, palier7_engrenages_v001.blend, palier8_matiere_v001.blend
