"""roulement.py - palier 3 : assemblage. Roulement rigide a billes 6202.

La difficulte nouvelle n'est pas la piece, c'est la RELATION entre les pieces.
Tout est pose analytiquement : les gorges sont des arcs de rayon Rg centres sur
le cercle primitif, les billes des spheres de rayon Dw/2 centrees au meme endroit.
Le jeu est donc uniforme et vaut Rg - Dw/2 par construction - et c'est cette
egalite que le controle verifie sur le MAILLAGE, pas sur le papier.
"""
import bmesh, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# 6202 : alesage 15, exterieur 35, largeur 11
SPEC = {
    "alesage": 15.0, "exterieur": 35.0, "largeur": 11.0,
    "dm": 25.0,            # diametre du cercle primitif (centres des billes)
    "Dw": 6.35,            # diametre de bille
    "z_billes": 8,
    "osculation": 0.52,    # Rg / Dw, valeur usuelle
    "epaulement": 1.4,     # hauteur d'epaulement de part et d'autre du primitif
}


def cotes(s=None):
    s = dict(SPEC if s is None else s)
    s["Rg"] = s["osculation"] * s["Dw"]
    s["jeu"] = s["Rg"] - s["Dw"] / 2.0          # jeu radial gorge/bille, uniforme
    s["r_primitif"] = s["dm"] / 2.0
    s["r_epaul_int"] = s["r_primitif"] - s["epaulement"]
    s["r_epaul_ext"] = s["r_primitif"] + s["epaulement"]
    s["demi_largeur"] = s["largeur"] / 2.0
    s["dz_gorge"] = math.sqrt(max(0.0, s["Rg"] ** 2 - s["epaulement"] ** 2))
    return s


def _arc(cx, cz, R, a0, a1, n):
    return [(cx + R * math.cos(a0 + (a1 - a0) * i / n),
             cz + R * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def profil_bague_interieure(s, n_arc=24):
    """Boucle fermee (r, z) en mm, sens direct."""
    ri, w = s["alesage"] / 2.0, s["demi_largeur"]
    re, dz = s["r_epaul_int"], s["dz_gorge"]
    a = math.asin(dz / s["Rg"])
    gorge = _arc(s["r_primitif"], 0.0, s["Rg"], math.pi + a, math.pi - a, n_arc)
    return [(ri, -w), (re, -w)] + gorge + [(re, w), (ri, w)]


def profil_bague_exterieure(s, n_arc=24):
    ro, w = s["exterieur"] / 2.0, s["demi_largeur"]
    ri, dz = s["r_epaul_ext"], s["dz_gorge"]
    a = math.asin(dz / s["Rg"])
    gorge = _arc(s["r_primitif"], 0.0, s["Rg"], -a, a, n_arc)
    return [(ri, -w)] + gorge + [(ri, w), (ro, w), (ro, -w)]


def revolution(profil, n_theta=96):
    """Revolution d'une boucle FERMEE : surface close, aucun capuchon necessaire."""
    bm = bmesh.new()
    n = len(profil)
    grille = []
    for i in range(n_theta):
        th = 2.0 * math.pi * i / n_theta
        c, si = math.cos(th), math.sin(th)
        grille.append([bm.verts.new((r / 1000.0 * c, r / 1000.0 * si, z / 1000.0))
                       for r, z in profil])
    bm.verts.index_update()
    for i in range(n_theta):
        j = (i + 1) % n_theta
        for k in range(n):
            l = (k + 1) % n
            a, b = grille[i][k], grille[i][l]
            if a.co == b.co:
                continue
            bm.faces.new((a, b, grille[j][l], grille[j][k]))
    bm.normal_update()
    return bm


def bille(s, indice, segments=48, anneaux=24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=anneaux,
                              radius=s["Dw"] / 2000.0)
    th = 2.0 * math.pi * indice / s["z_billes"]
    bmesh.ops.translate(bm, verts=bm.verts,
                        vec=(s["r_primitif"] / 1000.0 * math.cos(th),
                             s["r_primitif"] / 1000.0 * math.sin(th), 0.0))
    bm.normal_update()
    return bm


def assemblage(s=None, n_theta=96):
    s = cotes(s)
    pieces = {"bague_interieure": revolution(profil_bague_interieure(s), n_theta),
              "bague_exterieure": revolution(profil_bague_exterieure(s), n_theta)}
    for i in range(s["z_billes"]):
        pieces["bille_%d" % i] = bille(s, i)
    return s, pieces


def _bvh(bm):
    return BVHTree.FromBMesh(bm)


def distance_mini(bm_a, bvh_b):
    """Plus petite distance des sommets de A a la surface de B, en mm."""
    d = float("inf")
    for v in bm_a.verts:
        loc, nor, idx, dist = bvh_b.find_nearest(v.co)
        if loc is not None and dist < d:
            d = dist
    return d * 1000.0


def controle(s=None, n_theta=96):
    s, pieces = assemblage(s, n_theta)
    bvh = {k: _bvh(v) for k, v in pieces.items()}
    crit = []

    def juge(nom, ok, lu, attendu, note=""):
        crit.append({"critere": nom, "lu": lu, "attendu": attendu,
                     "vert": bool(ok), "note": note})

    # 1. aucune interpenetration : recouvrement de surfaces, paire a paire
    noms = list(pieces)
    paires = 0
    for i in range(len(noms)):
        for j in range(i + 1, len(noms)):
            paires += len(bvh[noms[i]].overlap(bvh[noms[j]]))
    juge("aucune interpenetration", paires == 0, paires, 0,
         "recouvrement de surfaces sur les %d paires" % (len(noms) * (len(noms) - 1) // 2))

    # 2. jeu bille/gorge : mesure sur le maillage, comparee a Rg - Dw/2
    b0 = pieces["bille_0"]
    ji = distance_mini(b0, bvh["bague_interieure"])
    je = distance_mini(b0, bvh["bague_exterieure"])
    theo = s["jeu"]
    # la facettisation rapproche les surfaces : on tolere 12 % en moins, rien en plus
    juge("jeu bille / bague interieure", theo * 0.88 <= ji <= theo * 1.02, ji, theo)
    juge("jeu bille / bague exterieure", theo * 0.88 <= je <= theo * 1.02, je, theo)

    # 3. les billes ne se touchent pas
    d01 = distance_mini(pieces["bille_0"], _bvh(pieces["bille_1"]))
    ecart_theorique = 2.0 * s["r_primitif"] * math.sin(math.pi / s["z_billes"]) - s["Dw"]
    juge("ecart entre billes voisines", d01 > 0.05, d01, ecart_theorique)

    # 4. cotes d'encombrement
    def rayons(bm):
        return [math.hypot(v.co.x, v.co.y) * 1000.0 for v in bm.verts]
    ri = min(rayons(pieces["bague_interieure"])) * 2.0
    re = max(rayons(pieces["bague_exterieure"])) * 2.0
    zs = [v.co.z * 1000.0 for bm in pieces.values() for v in bm.verts]
    juge("alesage", abs(ri - s["alesage"]) / s["alesage"] < 1e-6, ri, s["alesage"])
    juge("diametre exterieur", abs(re - s["exterieur"]) / s["exterieur"] < 1e-6,
         re, s["exterieur"])
    juge("largeur", abs((max(zs) - min(zs)) - s["largeur"]) / s["largeur"] < 1e-6,
         max(zs) - min(zs), s["largeur"])

    # 5. toutes les pieces fermees
    ouvertes = {k: len([e for e in v.edges if not e.is_manifold]) for k, v in pieces.items()}
    juge("toutes les pieces fermees", sum(ouvertes.values()) == 0,
         sum(ouvertes.values()), 0, str({k: n for k, n in ouvertes.items() if n}))

    for v in pieces.values():
        v.free()
    return {"cotes": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()},
            "criteres": crit, "vert": all(c["vert"] for c in crit)}
