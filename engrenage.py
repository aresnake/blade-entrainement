"""engrenage.py - palier 7 : le mouvement. Denture a developpante de cercle.

Profil normalise ISO 53 : angle de pression 20 degres, saillie = m, creux = 1,25 m.
La developpante d'un cercle de base rb s'ecrit, en polaire, par la fonction
involute : inv(a) = tan(a) - a. A un rayon r, l'angle de pression local vaut
a_r = arccos(rb / r), et le flanc se place a l'angle

    phi(r) = psi + inv(alpha) - inv(a_r)

ou psi est la demi-epaisseur angulaire de dent au cercle primitif. C'est cette
formule, et rien d'autre, qui fait qu'un couple d'engrenages roule sans a-coup.

Le controle du palier ne verifie pas un rapport annonce : il fait TOURNER le
couple sur un tour complet au rapport theorique z1/z2 et mesure qu'aucune dent
n'en touche une autre. Si le rapport etait faux, les dents se percuteraient en
une fraction de tour - ce qui est demontre en l'essayant expres.
"""
import bmesh, math
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

ALPHA = math.radians(20.0)      # angle de pression normalise


def inv(a):
    return math.tan(a) - a


def cotes(m, z):
    rp = m * z / 2.0
    return {"module": m, "dents": z,
            "r_primitif": rp,
            "r_base": rp * math.cos(ALPHA),
            "r_tete": rp + m,
            "r_pied": rp - 1.25 * m,
            "pas": math.pi * m,
            "epaisseur_primitif": math.pi * m / 2.0}


def profil_dent(m, z, jeu=0.0, n_flanc=14):
    """Points (x, y) d'UNE dent, du pied au pied, dent centree sur l'angle 0.

    `jeu` retire une epaisseur angulaire de part et d'autre : sans lui, deux
    developpantes theoriques se TOUCHENT, et un test de recouvrement ne peut
    plus distinguer le contact normal d'une collision.
    """
    c = cotes(m, z)
    rb, rp, ra, rf = c["r_base"], c["r_primitif"], c["r_tete"], c["r_pied"]
    psi = math.pi / (2.0 * z) - jeu / rp

    def phi(r):
        r = max(r, rb)
        a_r = math.acos(min(1.0, rb / r))
        return psi + inv(ALPHA) - inv(a_r)

    r_dep = max(rb, rf)
    rayons = [r_dep + (ra - r_dep) * i / (n_flanc - 1) for i in range(n_flanc)]
    flanc = [(r * math.cos(phi(r)), r * math.sin(phi(r))) for r in rayons]
    autre = [(x, -y) for x, y in reversed(flanc)]

    pts = []
    # raccord du pied vers le debut de developpante, cote positif
    if rf < rb:
        a0 = phi(rb)
        pts.append((rf * math.cos(a0), rf * math.sin(a0)))
    pts += flanc                      # flanc montant
    pts += autre                      # sommet puis flanc descendant
    if rf < rb:
        a1 = -phi(rb)
        pts.append((rf * math.cos(a1), rf * math.sin(a1)))
    # La dent est construite du cote positif vers le cote negatif, donc dans le
    # sens HORAIRE, alors que la roue est assemblee dent apres dent dans le sens
    # direct. Melanger les deux sens produit un contour qui se recoupe - et un
    # solide qui percute son voisin des le premier pas. On remet la dent dans le
    # sens direct.
    return list(reversed(pts))


def angle_pied(m, z, jeu=0.0):
    """Angle du point de pied, cote positif. Analytique, jamais par atan2."""
    c = cotes(m, z)
    rb, rp = c["r_base"], c["r_primitif"]
    psi = math.pi / (2.0 * z) - jeu / rp
    return psi + inv(ALPHA)


def profil_roue(m, z, jeu=0.0, n_flanc=14, n_pied=4):
    """Contour ferme de la roue entiere, sens direct.

    Les angles des arcs de pied sont calcules ANALYTIQUEMENT. Les prendre par
    atan2 sur les points deja tournes casse a la premiere traversee de +pi :
    l'arc repart en arriere, le contour se recoupe, et l'aire passe de 1 000 a
    4 100 mm carres. Mesure a l'appui le 28/08/2026.
    """
    dent = profil_dent(m, z, jeu, n_flanc)
    pas = 2.0 * math.pi / z
    rf = cotes(m, z)["r_pied"]
    ap = angle_pied(m, z, jeu)
    contour = []
    for k in range(z):
        a = k * pas
        ca, sa = math.cos(a), math.sin(a)
        contour += [(x * ca - y * sa, x * sa + y * ca) for x, y in dent]
        a_fin = a + ap                       # dernier point de la dent k
        a_deb = (k + 1) * pas - ap           # premier point de la dent k+1
        for i in range(1, n_pied):
            t = a_fin + (a_deb - a_fin) * i / n_pied
            contour.append((rf * math.cos(t), rf * math.sin(t)))
    return contour


def roue(m, z, largeur=10.0, jeu=0.0, n_flanc=14, alesage=None):
    """bmesh d'une roue dentee, cotes en millimetres, unites Blender = metres."""
    contour = profil_roue(m, z, jeu, n_flanc)
    bm = bmesh.new()
    bas = [bm.verts.new((x / 1000.0, y / 1000.0, -largeur / 2000.0))
           for x, y in contour]
    haut = [bm.verts.new((x / 1000.0, y / 1000.0, largeur / 2000.0))
            for x, y in contour]
    n = len(contour)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bas[i], bas[j], haut[j], haut[i]))
    bm.faces.new(list(reversed(bas)))
    bm.faces.new(haut)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return bm


# ------------------------------------------------------------------ controle

def _bvh_tourne(bm, angle, centre=(0.0, 0.0)):
    c = bm.copy()
    R = Matrix.Rotation(angle, 4, 'Z')
    T = Matrix.Translation((centre[0] / 1000.0, centre[1] / 1000.0, 0.0))
    c.transform(T @ R)
    t = BVHTree.FromBMesh(c)
    c.free()
    return t


def cycle(m, z1, z2, pas_angulaire=2.0, jeu=0.06, rapport=None, largeur=10.0):
    """Fait tourner le couple et mesure. `rapport` force un rapport faux si donne."""
    entraxe = m * (z1 + z2) / 2.0
    r1 = roue(m, z1, largeur, jeu)
    r2 = roue(m, z2, largeur, jeu)
    k = rapport if rapport is not None else -float(z1) / float(z2)
    # Calage. La roue 1 a une dent centree sur l'angle 0, donc pointee vers la
    # roue 2. Il faut donc un CREUX de la roue 2 en face, c'est-a-dire a l'angle
    # pi dans son propre repere. Les dents de la roue 2 sont centrees sur les
    # multiples de 2pi/z2 : l'angle pi en est un si et seulement si z2 est PAIR.
    # D'ou un demi-pas de calage pour z2 pair, et rien pour z2 impair.
    cale = (math.pi / z2) if (z2 % 2 == 0) else 0.0
    n = max(1, int(round(360.0 / pas_angulaire)))
    collisions, distances = 0, []
    for i in range(n):
        a1 = math.radians(i * pas_angulaire)
        a2 = k * a1 + cale
        b1 = _bvh_tourne(r1, a1, (0.0, 0.0))
        b2 = _bvh_tourne(r2, a2, (entraxe, 0.0))
        rec = b1.overlap(b2)
        if rec:
            collisions += 1
        else:
            # distance mini entre les deux roues a ce pas
            c2 = r2.copy()
            c2.transform(Matrix.Translation((entraxe / 1000.0, 0, 0))
                         @ Matrix.Rotation(a2, 4, 'Z'))
            d = min(b1.find_nearest(v.co)[3] for v in c2.verts)
            c2.free()
            distances.append(d * 1000.0)
    r1.free(); r2.free()
    return {"entraxe_mm": entraxe, "pas": n, "collisions": collisions,
            "jeu_mini_mm": round(min(distances), 4) if distances else None,
            "jeu_moyen_mm": round(sum(distances) / len(distances), 4) if distances else None,
            "rapport": k}


def controle(m=2.0, z1=17, z2=31, pas_angulaire=3.0):
    c1, c2 = cotes(m, z1), cotes(m, z2)
    crit = []

    def juge(nom, ok, lu, attendu, note=""):
        crit.append({"critere": nom, "lu": lu, "attendu": attendu,
                     "vert": bool(ok), "note": note})

    # 1. epaisseur de dent au cercle primitif = pi*m/2, relue sur le PROFIL
    pts = profil_dent(m, z1, jeu=0.0, n_flanc=60)
    rp = c1["r_primitif"]
    angles = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        r0, r1_ = math.hypot(x0, y0), math.hypot(x1, y1)
        if (r0 - rp) * (r1_ - rp) <= 0 and r0 != r1_:
            t = (rp - r0) / (r1_ - r0)
            angles.append(math.atan2(y0 + t * (y1 - y0), x0 + t * (x1 - x0)))
    ep = abs(angles[0] - angles[-1]) * rp if len(angles) >= 2 else 0.0
    juge("epaisseur de dent au primitif", abs(ep - c1["epaisseur_primitif"])
         / c1["epaisseur_primitif"] < 2e-3, ep, c1["epaisseur_primitif"],
         "relue par intersection du profil avec le cercle primitif")

    # 2. rayon de base = rp cos(alpha)
    juge("rayon de base", abs(c1["r_base"] - c1["r_primitif"] * math.cos(ALPHA)) < 1e-12,
         c1["r_base"], c1["r_primitif"] * math.cos(ALPHA))

    # 3. un tour complet au bon rapport : aucune collision
    bon = cycle(m, z1, z2, pas_angulaire)
    juge("un tour au rapport z1/z2 : aucune collision", bon["collisions"] == 0,
         bon["collisions"], 0,
         "jeu mini %.3f mm, jeu moyen %.3f mm" % (bon["jeu_mini_mm"] or -1,
                                                  bon["jeu_moyen_mm"] or -1))

    # 4. epreuve inverse : un rapport FAUX doit percuter. Sinon le test 3 ne
    #    prouve rien - il pourrait passer sur n'importe quel reglage.
    faux = cycle(m, z1, z2, pas_angulaire, rapport=-float(z1) / float(z2) * 1.03)
    juge("un rapport faux de 3 % percute bien", faux["collisions"] > 0,
         faux["collisions"], "> 0", "epreuve en sens inverse du critere 3")

    return {"roue1": c1, "roue2": c2, "cycle_bon": bon, "cycle_faux": faux,
            "criteres": crit, "vert": all(c["vert"] for c in crit)}
