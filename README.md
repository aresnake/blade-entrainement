# BLADE — entraînement Blender

Bibliothèque accumulée par le programme d'entraînement en dix paliers.
Chaque module se vérifie par du code : les critères sont mesurés, jamais appréciés.

| module | palier | ce qu'il fait |
|---|---|---|
| `visserie.py` | 2 | filetage métrique ISO 68-1, tête hexagonale, boulon fermé sans booléen |
| `roulement.py` | 3 | roulement à billes 6202, jeux uniformes par construction |
| `linter.py` | 4 | 16 règles, deux profils, chacune éprouvée dans les deux sens |
| `gameready.py` | 4 | LODs à erreur mesurée, coque de collision, aller-retour FBX/GLB |
| `escalier.py` | 5 | arbre Geometry Nodes construit par script |
| `geo.py` | 6 | OpenStreetMap, projection métrique, Vincenty comme oracle |
| `engrenage.py` | 7 | denture à développante ISO 53 |
| `bielle.py` | 7 | cinématique exacte, animée et relue au depsgraph |
| `matiere.py` | 8 | densité de texel, bake de normales sous contrôle |
| `cloture.py` | — | arrêt propre : écrit `REPRISE.md` à tout instant |
| `banc/banc.py` | — | banc de non-régression, 52 tests |

`REPRISE.md` est le seul fichier à lire pour reprendre le travail.
