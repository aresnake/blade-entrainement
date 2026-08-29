"""visserie.py - filetage metrique ISO parametrique, projet BLADE palier 2.

Profil de base ISO 68-1 : triangle equilateral de hauteur H = (V3/2)P, tronque
de H/8 au sommet et de H/4 au fond. Profondeur radiale utile = 5H/8, d'ou
diametre sur fond = d - 5H/4 = d - 1,0825 P.

La tige est une surface helicoidale fermee : le rayon en tout point vaut
r(theta, z) = profil(frac((z - P*theta/2pi)/P)). Un seul filet, pas de booleen,
maillage manifold par construction.
"""
import bmesh, math

# ISO 261 / 262 - pas gros (coarse)
PAS = {3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25,
       10: 1.5, 12: 1.75, 16: 2.0, 20: 2.5}

RACINE3 = math.sqrt(3.0)

# bornes du profil sur une periode, en fraction de P
A = 1.0 / 8.0            # fin du plat de sommet
B = A + 5.0 / 16.0       # fin du flanc descendant
C = B + 1.0 / 4.0        # fin du plat de fond
E = 5.0 / 16.0           # course axiale d'un flanc


def hauteur_theorique(P):
    return RACINE3 / 2.0 * P


def profondeur(P):
    return 5.0 / 8.0 * hauteur_theorique(P)


def profil(t, R, P):
    """Rayon au parametre axial t (fraction de periode), en metres."""
    h = profondeur(P)
    t = t - math.floor(t)
    if t < A:
        return R
    if t < B:
        return R - h * (t - A) / E
    if t < C:
        return R - h
    return R - h * (1.0 - (t - C) / E)


def tige_filetee(d_mm, longueur_mm, n_theta=48, pas_par_periode=12):
    """Rend un bmesh de tige filetee, cotes en millimetres, unites Blender = m."""
    P = PAS[d_mm] / 1000.0
    R = d_mm / 2000.0
    L = longueur_mm / 1000.0
    dz = P / pas_par_periode
    n_z = max(2, int(round(L / dz)) + 1)
    dz = L / (n_z - 1)

    bm = bmesh.new()
    grille = []
    for j in range(n_z):
        z = j * dz
        rang = []
        for i in range(n_theta):
            th = 2.0 * math.pi * i / n_theta
            t = (z - P * th / (2.0 * math.pi)) / P
            r = profil(t, R, P)
            rang.append(bm.verts.new((r * math.cos(th), r * math.sin(th), z)))
        grille.append(rang)
    bm.verts.index_update()

    for j in range(n_z - 1):
        for i in range(n_theta):
            k = (i + 1) % n_theta
            bm.faces.new((grille[j][i], grille[j][k], grille[j + 1][k], grille[j + 1][i]))

    # capuchons en eventail : le contour n'est pas circulaire (le filet le coupe)
    for j, sens in ((0, False), (n_z - 1, True)):
        c = bm.verts.new((0.0, 0.0, j * dz))
        for i in range(n_theta):
            k = (i + 1) % n_theta
            a, b = grille[j][i], grille[j][k]
            bm.faces.new((c, b, a) if sens is False else (c, a, b))

    bm.normal_update()
    return bm


def mesures(bm, d_mm, longueur_mm):
    """Grandeurs relues sur le maillage, en millimetres."""
    P = PAS[d_mm]
    # Les deux sommets centraux des capuchons ont un rayon nul : les exclure par
    # leur rayon, jamais par leur z. Le z du capuchon haut vaut (n_z-1)*dz, qui
    # n'est pas exactement L en flottant, donc un filtre sur z laisse passer un
    # rayon 0 et effondre le diametre sur fond a zero. Piege paye le 28/08/2026.
    seuil = d_mm / 4000.0
    rs = [r for r in (math.hypot(v.co.x, v.co.y) for v in bm.verts) if r > seuil]
    zs = [v.co.z for v in bm.verts]
    nm = [e for e in bm.edges if not e.is_manifold]
    return {
        "diametre_exterieur": max(rs) * 2000.0,
        "diametre_fond": min(rs) * 2000.0,
        "longueur": (max(zs) - min(zs)) * 1000.0,
        "pas": P,
        "profondeur_relue": (max(rs) - min(rs)) * 1000.0,
        "aretes_non_manifold": len(nm),
        "sommets": len(bm.verts),
        "faces": len(bm.faces),
    }


def attendu(d_mm):
    P = PAS[d_mm]
    return {
        "diametre_exterieur": float(d_mm),
        "diametre_fond": d_mm - 1.25 * hauteur_theorique(P),
        "profondeur": profondeur(P),
    }


def controle(d_mm, longueur_mm, tol=1e-6):
    """Verdict cote par cote. tol : tolerance RELATIVE (plancher float32 = 2,2e-8)."""
    bm = tige_filetee(d_mm, longueur_mm)
    m = mesures(bm, d_mm, longueur_mm)
    a = attendu(d_mm)
    bm.free()
    crit = []

    def juge(nom, lu, ref, t=tol):
        err = abs(lu - ref) / abs(ref) if ref else abs(lu)
        crit.append({"critere": nom, "lu": lu, "attendu": ref,
                     "erreur_relative": err, "vert": err <= t})

    juge("diametre exterieur", m["diametre_exterieur"], a["diametre_exterieur"])
    juge("diametre sur fond", m["diametre_fond"], a["diametre_fond"])
    juge("profondeur du filet", m["profondeur_relue"], a["profondeur"])
    juge("longueur", m["longueur"], float(longueur_mm))
    crit.append({"critere": "maillage manifold", "lu": m["aretes_non_manifold"],
                 "attendu": 0, "erreur_relative": 0.0,
                 "vert": m["aretes_non_manifold"] == 0})
    return {"designation": "M%d x %g" % (d_mm, PAS[d_mm]),
            "mesures": m, "criteres": crit,
            "vert": all(c["vert"] for c in crit)}


def famille(longueur_facteur=6.0):
    return [controle(d, max(10.0, d * longueur_facteur)) for d in sorted(PAS)]


# --------------------------------------------------------------- tete hexagonale

# ISO 4014 : s = entreplats, k = hauteur de tete. Table RECITEE, pas encore
# confrontee a la norme - a verifier (voie D). La GEOMETRIE, elle, est prouvee :
# les criteres relisent s et k sur le maillage, quels que soient les chiffres.
TETE = {3: (5.5, 2.0), 4: (7.0, 2.8), 5: (8.0, 3.5), 6: (10.0, 4.0),
        8: (13.0, 5.3), 10: (16.0, 6.4), 12: (18.0, 7.5),
        16: (24.0, 10.0), 20: (30.0, 12.5)}


def rayon_hexagone(theta, s):
    """Rayon du contour hexagonal d'entreplats s, a l'angle theta."""
    a = (theta + math.pi / 6.0) % (math.pi / 3.0) - math.pi / 6.0
    return (s / 2.0) / math.cos(a)


def boulon(d_mm, longueur_mm, filetage_mm=None, n_theta=96, pas_par_periode=24):
    """Boulon a tete hexagonale, maillage FERME, sans aucun booleen.

    Une seule surface : capuchon bas, portion filetee, degagement de filet sur un
    pas, tige lisse, dessous de tete, cotes hexagonaux, dessus de tete. Toutes les
    couronnes ont n_theta sommets, donc tout se coud sans raccord.
    n_theta doit etre multiple de 6 pour que les six aretes tombent sur des sommets.
    """
    assert n_theta % 6 == 0, "n_theta doit etre multiple de 6"
    P = PAS[d_mm] / 1000.0
    R = d_mm / 2000.0
    s, k = TETE[d_mm]
    s /= 1000.0
    k /= 1000.0
    L = longueur_mm / 1000.0
    Lf = (filetage_mm / 1000.0) if filetage_mm else min(L * 0.6, L - 2.0 * P)

    thetas = [2.0 * math.pi * i / n_theta for i in range(n_theta)]
    couronnes = []          # (z, [rayons])

    dz = P / pas_par_periode
    n_z = max(2, int(round(Lf / dz)) + 1)
    dz = Lf / (n_z - 1)
    for j in range(n_z):
        z = j * dz
        # degagement : sur le dernier pas, le rayon rejoint la tige lisse
        f = 0.0
        if z > Lf - P:
            f = (z - (Lf - P)) / P
        rs = []
        for th in thetas:
            r = profil((z - P * th / (2.0 * math.pi)) / P, R, P)
            rs.append(r * (1.0 - f) + R * f)
        couronnes.append((z, rs))

    couronnes.append((L, [R] * n_theta))                       # tige lisse
    hexa = [rayon_hexagone(th, s) for th in thetas]
    couronnes.append((L, hexa))                                # dessous de tete
    couronnes.append((L + k, hexa))                            # dessus de tete

    bm = bmesh.new()
    grille = [[bm.verts.new((r * math.cos(th), r * math.sin(th), z))
               for th, r in zip(thetas, rs)] for z, rs in couronnes]
    bm.verts.index_update()
    for j in range(len(grille) - 1):
        for i in range(n_theta):
            q = (i + 1) % n_theta
            a, b = grille[j][i], grille[j][q]
            c, e = grille[j + 1][q], grille[j + 1][i]
            if a.co == e.co and b.co == c.co:
                continue                                        # couronne degeneree
            bm.faces.new((a, b, c, e))
    bas = bm.verts.new((0.0, 0.0, 0.0))
    for i in range(n_theta):
        q = (i + 1) % n_theta
        bm.faces.new((bas, grille[0][q], grille[0][i]))
    haut = bm.verts.new((0.0, 0.0, L + k))
    for i in range(n_theta):
        q = (i + 1) % n_theta
        bm.faces.new((haut, grille[-1][i], grille[-1][q]))
    bm.normal_update()
    return bm


def controle_boulon(d_mm, longueur_mm, tol=1e-6):
    bm = boulon(d_mm, longueur_mm)
    s, k = TETE[d_mm]
    L = longueur_mm / 1000.0
    zt = L + k / 1000.0
    # entreplats : mesure au MILIEU d'un plat, la ou le rayon vaut s/2
    # tolerance RELATIVE : les coordonnees sont en float32, un seuil absolu de
    # 1e-9 sur un z de 55 mm ne selectionne rien du tout. Piege paye le 28/08.
    tol_z = max(1e-9, zt * 1e-6)
    hauts = [v for v in bm.verts if abs(v.co.z - zt) < tol_z
             and (abs(v.co.x) + abs(v.co.y)) > 1e-9]
    rs = [math.hypot(v.co.x, v.co.y) for v in hauts]
    zs = [v.co.z for v in bm.verts]
    nm = len([e for e in bm.edges if not e.is_manifold])
    entreplats = min(rs) * 2000.0
    entrecoins = max(rs) * 2000.0
    hauteur_tete = (max(zs) - L) * 1000.0
    bm.free()
    crit = []

    def juge(nom, lu, ref, t=tol):
        err = abs(lu - ref) / abs(ref) if ref else abs(lu)
        crit.append({"critere": nom, "lu": lu, "attendu": ref,
                     "erreur_relative": err, "vert": err <= t})

    juge("entreplats s", entreplats, s)
    juge("entrecoins", entrecoins, s / math.cos(math.pi / 6.0))
    juge("hauteur de tete k", hauteur_tete, k)
    juge("longueur totale", (max(zs) - min(zs)) * 1000.0, longueur_mm + k)
    crit.append({"critere": "maillage ferme", "lu": nm, "attendu": 0,
                 "erreur_relative": 0.0, "vert": nm == 0})
    return {"designation": "M%d x %g, tete %g" % (d_mm, PAS[d_mm], s),
            "criteres": crit, "vert": all(c["vert"] for c in crit)}
