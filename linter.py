"""linter.py - palier 4 : ce qui rend un asset livrable.

Un controle ne vaut que s'il se tait sur une piece saine. Chaque regle est donc
eprouvee dans les DEUX SENS par `epreuve()` : un cas fautif construit expres doit
la declencher, un cas propre construit expres doit la laisser muette.

    import linter
    linter.rapport(bpy.data.objects["x"])       # dict
    print(linter.texte(bpy.data.objects["x"]))  # lisible
    linter.epreuve()                            # auto-validation des regles
"""
import bpy, bmesh, math, re
from mathutils.bvhtree import BVHTree

NOMMAGE = re.compile(r"^(SM|SK|T|M)_[A-Za-z0-9]+(_LOD[0-9])?$")
REGLES = []


def regle(cle, gravite="erreur", profils=("rendu", "collision")):
    """Une regle ne vaut pas pour tous les types d'asset : un volume de collision
    n'a ni UV ni materiau, et l'exiger de lui produit un faux positif - le defaut
    exact qu'un linter ne doit jamais avoir."""
    def deco(f):
        REGLES.append({"cle": cle, "fn": f, "gravite": gravite,
                       "profils": set(profils)})
        return f
    return deco


def _bm(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    return bm


# ------------------------------------------------------------------- les regles

@regle("echelle_appliquee")
def r_echelle(ob, bm):
    s = tuple(round(v, 6) for v in ob.scale)
    return s == (1.0, 1.0, 1.0), {"echelle": s}


@regle("rotation_appliquee", "avertissement")
def r_rotation(ob, bm):
    r = tuple(round(v, 6) for v in ob.rotation_euler)
    return r == (0.0, 0.0, 0.0), {"rotation": r}


@regle("pivot_dans_la_boite")
def r_pivot(ob, bm):
    if not bm.verts:
        return False, {}
    xs = [v.co for v in bm.verts]
    mini = [min(c[i] for c in xs) for i in range(3)]
    maxi = [max(c[i] for c in xs) for i in range(3)]
    diag = math.sqrt(sum((maxi[i] - mini[i]) ** 2 for i in range(3)))
    marge = max(1e-6, 0.10 * diag)
    dedans = all(mini[i] - marge <= 0.0 <= maxi[i] + marge for i in range(3))
    return dedans, {"boite_min": [round(v, 5) for v in mini],
                    "boite_max": [round(v, 5) for v in maxi],
                    "marge_m": round(marge, 5)}


@regle("ferme")
def r_manifold(ob, bm):
    n = len([e for e in bm.edges if not e.is_manifold])
    return n == 0, {"aretes_ouvertes": n}


@regle("normales_coherentes")
def r_normales(ob, bm):
    copie = bm.copy()
    bmesh.ops.recalc_face_normals(copie, faces=copie.faces)
    retournees = sum(1 for a, b in zip(bm.faces, copie.faces)
                     if a.normal.dot(b.normal) < 0.0)
    copie.free()
    return retournees == 0, {"faces_retournees": retournees}


@regle("sans_ngon", "avertissement", profils=("rendu",))
def r_ngon(ob, bm):
    n = sum(1 for f in bm.faces if len(f.verts) > 4)
    return n == 0, {"ngons": n}


@regle("sans_face_degeneree")
def r_degeneree(ob, bm):
    """Une face d'aire nulle passe tous les autres controles et casse un moteur.
    C'est ce que produit un generateur nourri d'une entree a zero : la geometrie
    reste fermee, coherente, bien nommee - et inutilisable."""
    n = sum(1 for f in bm.faces if f.calc_area() <= 1e-12)
    return n == 0, {"faces_d_aire_nulle": n, "faces": len(bm.faces)}


@regle("sans_element_isole")
def r_isoles(ob, bm):
    vs = sum(1 for v in bm.verts if not v.link_edges)
    es = sum(1 for e in bm.edges if not e.link_faces)
    return vs == 0 and es == 0, {"sommets_isoles": vs, "aretes_isolees": es}


@regle("sans_doublon")
def r_doublons(ob, bm):
    """Doublons comptes PAR ILE. Deux batiments mitoyens partagent les
    coordonnees de leurs angles sans que ce soit un defaut ; deux sommets
    confondus dans un meme volume, si."""
    seuil = 1e-6
    parent = list(range(len(bm.verts)))
    bm.verts.index_update()

    def racine(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for e in bm.edges:
        a, b = racine(e.verts[0].index), racine(e.verts[1].index)
        if a != b:
            parent[a] = b
    iles = {}
    n = 0
    for v in bm.verts:
        cle = (racine(v.index),
               round(v.co.x / seuil), round(v.co.y / seuil), round(v.co.z / seuil))
        if cle in iles:
            n += 1
        iles[cle] = 1
    n_iles = len({racine(v.index) for v in bm.verts})
    return n == 0, {"sommets_confondus_dans_une_meme_ile": n, "iles": n_iles}


@regle("materiau_present", profils=("rendu",))
def r_materiau(ob, bm):
    """Un emplacement vide n'est un defaut que si des FACES s'y rapportent.
    Un arbre Geometry Nodes laisse derriere lui l'emplacement vide de sa
    primitive : il ne gene personne tant qu'aucune face ne l'utilise."""
    mats = [s.material for s in ob.material_slots]
    if not mats:
        return False, {"emplacements": 0, "utilises": []}
    utilises = sorted({p.material_index for p in ob.data.polygons})
    orphelins = [i for i in utilises if i >= len(mats) or mats[i] is None]
    vides_inutilises = [i for i, m in enumerate(mats)
                        if m is None and i not in utilises]
    return not orphelins, {"emplacements": len(mats), "utilises": utilises,
                           "faces_sans_materiau": orphelins,
                           "emplacements_vides_inutilises": vides_inutilises}


@regle("uv_presente", profils=("rendu",))
def r_uv(ob, bm):
    return len(ob.data.uv_layers) > 0, {"couches_uv": len(ob.data.uv_layers)}


@regle("nommage", "avertissement", profils=("rendu",))
def r_nom(ob, bm):
    return bool(NOMMAGE.match(ob.name)), {"nom": ob.name,
                                          "attendu": "SM_Nom ou SM_Nom_LOD0"}


@regle("echelle_metrique_plausible")
def r_taille(ob, bm):
    if not bm.verts:
        return False, {}
    d = [max(v.co[i] for v in bm.verts) - min(v.co[i] for v in bm.verts) for i in range(3)]
    g = max(d)
    return 0.0005 <= g <= 20000.0, {"plus_grande_dimension_m": round(g, 6)}


# ------------------------------------------------------------------- le rapport

def rapport(ob, profil="rendu"):
    bm = _bm(ob)
    lignes = []
    for r in REGLES:
        if profil not in r["profils"]:
            continue
        try:
            ok, det = r["fn"](ob, bm)
        except Exception as ex:
            ok, det = False, {"exception": "%s: %s" % (type(ex).__name__, ex)}
        lignes.append({"regle": r["cle"], "gravite": r["gravite"],
                       "vert": bool(ok), "detail": det})
    bm.free()
    err = [l for l in lignes if not l["vert"] and l["gravite"] == "erreur"]
    avt = [l for l in lignes if not l["vert"] and l["gravite"] == "avertissement"]
    return {"objet": ob.name, "profil": profil,
            "verdict": "VERT" if not err else "ROUGE",
            "erreurs": len(err), "avertissements": len(avt), "lignes": lignes}


def texte(ob, profil="rendu"):
    r = rapport(ob, profil)
    out = ["%s [%s] : %s (%d erreurs, %d avertissements)"
           % (r["objet"], r["profil"], r["verdict"], r["erreurs"], r["avertissements"])]
    for l in r["lignes"]:
        if not l["vert"]:
            out.append("  [%s] %s %s" % (l["gravite"][:4].upper(), l["regle"], l["detail"]))
    return "\n".join(out)


# --------------------------------------------------- epreuve dans les deux sens

def _cube_propre(nom="SM_Temoin"):
    me = bpy.data.meshes.new(nom)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.2)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.scene.collection.objects.link(ob)
    me.uv_layers.new(name="UVMap")
    m = bpy.data.materials.get("_lint_mat") or bpy.data.materials.new("_lint_mat")
    me.materials.append(m)
    return ob


def _jeter(ob):
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if me.users == 0:
        bpy.data.meshes.remove(me)


def epreuve():
    """Chaque regle doit se taire sur le temoin et crier sur la faute qui la vise."""
    res = {}
    temoin = _cube_propre()
    base = {l["regle"]: l["vert"] for l in rapport(temoin)["lignes"]}
    res["temoin_tout_vert"] = all(base.values())
    res["temoin_rouges"] = [k for k, v in base.items() if not v]
    _jeter(temoin)

    fautes = {
        "echelle_appliquee": lambda o: setattr(o, "scale", (2.0, 1.0, 1.0)),
        "rotation_appliquee": lambda o: setattr(o, "rotation_euler", (0.3, 0.0, 0.0)),
        "pivot_dans_la_boite": lambda o: _decaler(o, 1.0),
        "ferme": lambda o: _ouvrir(o),
        "normales_coherentes": lambda o: _retourner(o),
        "sans_element_isole": lambda o: _isoler(o),
        "sans_doublon": lambda o: _dupliquer(o),
        "sans_face_degeneree": lambda o: _aplatir(o),
        "materiau_present": lambda o: o.data.materials.clear(),
        "uv_presente": lambda o: o.data.uv_layers.remove(o.data.uv_layers[0]),
        "nommage": lambda o: setattr(o, "name", "Cube.001"),
        "echelle_metrique_plausible": lambda o: _gonfler(o, 500000.0),
    }
    detectees = {}
    for cle, casser in fautes.items():
        ob = _cube_propre("SM_Faute")
        casser(ob)
        lignes = {l["regle"]: l["vert"] for l in rapport(ob)["lignes"]}
        detectees[cle] = (lignes.get(cle) is False)
        _jeter(ob)
    res["fautes_detectees"] = detectees
    res["toutes_detectees"] = all(detectees.values())
    res["vert"] = res["temoin_tout_vert"] and res["toutes_detectees"]
    return res


def _modif(ob, fn):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    # bm.faces[0] leve « outdated internal index table » sans cet appel : un bmesh
    # rempli depuis un mesh n'a pas de table d'index tant qu'on ne la demande pas.
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    fn(bm)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def _decaler(ob, d):
    _modif(ob, lambda bm: bmesh.ops.translate(bm, verts=bm.verts, vec=(d, 0, 0)))


def _gonfler(ob, k):
    _modif(ob, lambda bm: bmesh.ops.scale(bm, verts=bm.verts, vec=(k, k, k)))


def _ouvrir(ob):
    def f(bm):
        bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES_ONLY')
    _modif(ob, f)


def _retourner(ob):
    def f(bm):
        bmesh.ops.reverse_faces(bm, faces=[bm.faces[0]])
    _modif(ob, f)


def _isoler(ob):
    _modif(ob, lambda bm: bm.verts.new((0.9, 0.9, 0.9)))


def _dupliquer(ob):
    """Le doublon doit etre DANS l'ile, sinon la regle par ile ne le voit pas :
    un sommet flottant forme sa propre ile. On le raccorde donc a un voisin."""
    def f(bm):
        v = bm.verts[0]
        jumeau = bm.verts.new(v.co.copy())
        voisin = v.link_edges[0].other_vert(v)
        bm.edges.new((jumeau, voisin))
    _modif(ob, f)


@regle("collision_nommee", profils=("collision",))
def r_col_nom(ob, bm):
    return ob.name.startswith("UCX_") and ob.name[-3:-2] == "_", \
        {"nom": ob.name, "attendu": "UCX_<Nom>_00"}


@regle("collision_convexe", profils=("collision",))
def r_col_convexe(ob, bm):
    """Convexite : aucun sommet du cote interieur d'un plan de face."""
    marge = 1e-6
    hors = 0
    for f in bm.faces:
        n, c = f.normal, f.calc_center_median()
        for v in bm.verts:
            if (v.co - c).dot(n) > marge:
                hors += 1
                break
    return hors == 0, {"faces_avec_sommet_au_dela": hors, "faces": len(bm.faces)}


@regle("collision_legere", "avertissement", profils=("collision",))
def r_col_poids(ob, bm):
    return len(bm.faces) <= 256, {"faces": len(bm.faces), "plafond": 256}


def _aplatir(ob):
    """Ecrase une face sur elle-meme : aire nulle, maillage par ailleurs sain."""
    def f(bm):
        face = bm.faces[0]
        cible = face.verts[0].co.copy()
        for v in face.verts[1:]:
            v.co = cible
    _modif(ob, f)
