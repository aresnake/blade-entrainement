"""cloture.py - s'arreter proprement, a tout instant, sans preavis.

Le probleme : Claude ne voit ni le quota d'Adrien ni son epuisement. Une
technique fondee sur « detecter la fin qui approche » serait donc une promesse
creuse. La solution ne consiste pas a mieux voir la fin, mais a faire en sorte
qu'elle n'ait plus d'importance.

Deux regles, et un bouton.

REGLE 1 - Toujours atterrissable. Aucun travail en cours ne vit uniquement dans
la conversation. Des qu'une brique tient debout, elle part sur le disque, gagne
son test au banc, et laisse une note. Une session coupee au milieu ne perd alors
que la minute en cours.

REGLE 2 - Petits pas. Une unite de travail ne depasse pas un cran de palier.
Ce qui ne rentre pas dans un cran se decoupe avant d'etre commence, jamais
pendant.

LE BOUTON - `poser()` ecrit REPRISE.md : ou on en est, ce qui marche, ce qui
reste, et LA PROCHAINE ACTION EXACTE. Un seul mot d'Adrien suffit a le declencher,
et n'importe quelle session future - la mienne, une voie nocturne - reprend le
fil en lisant ce fichier.
"""
import bpy, io, os, sys, datetime, importlib

DOSSIER = os.path.join(os.path.expanduser("~"), "Blender_Atelier",
                       "projets", "entrainement")
FICHIER = os.path.join(DOSSIER, "REPRISE.md")


def _banc_compte():
    d = bpy.utils.user_resource('SCRIPTS', path="modules")
    if d not in sys.path:
        sys.path.append(d)
    try:
        import banc
        importlib.reload(banc)
        return len(banc.TESTS)
    except Exception as e:
        return "indisponible (%s)" % type(e).__name__


def etat():
    modules = sorted(f for f in os.listdir(DOSSIER) if f.endswith(".py"))
    scenes = sorted(os.listdir(os.path.join(DOSSIER, "00_scenes"))) \
        if os.path.isdir(os.path.join(DOSSIER, "00_scenes")) else []
    return {"modules": modules, "scenes": scenes, "tests_au_banc": _banc_compte(),
            "instance_unsaved": bpy.data.filepath == "",
            "objets_en_scene": [o.name for o in bpy.context.scene.objects][:20]}


def poser(palier, fait, prochaine_action, en_suspens=None, scene=None):
    """Ecrit REPRISE.md et enregistre une copie de la scene si demande.

    `prochaine_action` doit etre executable telle quelle par quelqu'un qui n'a
    rien vu de la session : pas « continuer le palier 9 » mais « ecrire
    __init__.py de l'addon avec register/unregister et le tester en headless ».
    """
    e = etat()
    if scene:
        os.makedirs(os.path.join(DOSSIER, "00_scenes"), exist_ok=True)
        chemin = os.path.join(DOSSIER, "00_scenes", scene)
        # copy=True : l'instance doit rester « unsaved », c'est a cela que les
        # sessions futures reconnaissent qu'elles peuvent y ecrire.
        bpy.ops.wm.save_as_mainfile(filepath=chemin, copy=True)
        e = etat()

    lignes = [
        "# Reprise - projet entrainement BLADE",
        "",
        "Ecrit le %s." % datetime.datetime.now().strftime("%d/%m/%Y a %Hh%M"),
        "Ce fichier est la seule chose a lire pour reprendre. Il est reecrit a",
        "chaque atterrissage, donc il est toujours a jour ou il n'existe pas.",
        "",
        "## Ou on en est",
        "- Palier : %s" % palier,
        "- Tests au banc : %s" % e["tests_au_banc"],
        "",
        "## Ce qui vient d'etre fait et tient debout",
    ]
    lignes += ["- %s" % x for x in (fait if isinstance(fait, list) else [fait])]
    lignes += ["", "## PROCHAINE ACTION", "", "> %s" % prochaine_action, ""]
    if en_suspens:
        lignes += ["## Laisse en suspens - a ne pas croire acquis"]
        lignes += ["- %s" % x for x in (en_suspens if isinstance(en_suspens, list)
                                        else [en_suspens])]
        lignes += [""]
    lignes += ["## Inventaire", "",
               "Modules : " + ", ".join(e["modules"]),
               "", "Scenes : " + ", ".join(e["scenes"]) if e["scenes"] else "", ""]
    with io.open(FICHIER, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes))
    return {"ecrit": FICHIER, "octets": os.path.getsize(FICHIER),
            "tests_au_banc": e["tests_au_banc"],
            "scene_enregistree": scene, "instance_unsaved": e["instance_unsaved"]}


def lire():
    if not os.path.exists(FICHIER):
        return "Aucun REPRISE.md : rien n'etait en cours."
    return io.open(FICHIER, encoding="utf-8").read()
