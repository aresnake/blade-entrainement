"""geo.py - palier 6 : la donnee arbitre.

Emprises de batiments reelles depuis OpenStreetMap, projetees en metres et
extrudees. Plus rien ne s'invente : chaque cote se confronte a la source.

Le controle repose sur deux chemins INDEPENDANTS vers la meme grandeur :
- la distance projetee, calculee dans le plan local ;
- la distance geodesique (haversine) calculee sur la sphere.
Leur ecart mesure la deformation de la projection. C'est la meme methode que
Bolt Factory face au filetage : deux routes vers un nombre valent mieux qu'une.
"""
import bmesh, json, math, os, time
import urllib.request

CACHE = os.path.join(os.path.expanduser("~"), "Blender_Atelier", "projets",
                     "entrainement", "_cache_osm")
R_TERRE = 6371008.8          # rayon moyen WGS84, en metres
ETAGE_M = 3.0                # hauteur d'etage par defaut quand OSM ne donne rien


# --------------------------------------------------------------- projection

def echelles(lat_deg):
    """Metres par degre, developpement WGS84 local (precis au cm sur 1 km)."""
    p = math.radians(lat_deg)
    mlat = (111132.92 - 559.82 * math.cos(2 * p) + 1.175 * math.cos(4 * p)
            - 0.0023 * math.cos(6 * p))
    mlon = (111412.84 * math.cos(p) - 93.5 * math.cos(3 * p)
            + 0.118 * math.cos(5 * p))
    return mlat, mlon


def projeter(lat, lon, lat0, lon0):
    mlat, mlon = echelles(lat0)
    return ((lon - lon0) * mlon, (lat - lat0) * mlat)


def haversine(a, b):
    """Sphere de rayon MOYEN. Conserve pour memoire : ce n'est PAS un bon oracle.

    Mesure du 28/08/2026 : compare a la projection ellipsoidale, l'ecart valait
    3,0016e-3 sur les aretes est-ouest. Ce n'etait pas une deformation de la
    projection mais le rapport N/R_moyen - 1 = 3,0246e-3, c'est-a-dire l'ecart
    entre le rayon de courbure normal du WGS84 a cette latitude et le rayon moyen
    de la sphere. L'oracle etait moins juste que ce qu'il jugeait.
    """
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_TERRE * math.asin(min(1.0, math.sqrt(h)))


A_WGS84 = 6378137.0
F_WGS84 = 1.0 / 298.257223563
B_WGS84 = A_WGS84 * (1.0 - F_WGS84)


def geodesique(p, q, iterations=200, tol=1e-12):
    """Vincenty inverse sur l'ellipsoide WGS84. Le vrai oracle : au millimetre.

    Independant des echelles polynomiales de `echelles()`, donc utilisable pour
    les juger.
    """
    lat1, lon1 = math.radians(p[0]), math.radians(p[1])
    lat2, lon2 = math.radians(q[0]), math.radians(q[1])
    L = lon2 - lon1
    U1 = math.atan((1 - F_WGS84) * math.tan(lat1))
    U2 = math.atan((1 - F_WGS84) * math.tan(lat2))
    sU1, cU1 = math.sin(U1), math.cos(U1)
    sU2, cU2 = math.sin(U2), math.cos(U2)
    lam = L
    for _ in range(iterations):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.sqrt((cU2 * sl) ** 2 + (cU1 * sU2 - sU1 * cU2 * cl) ** 2)
        if ss == 0.0:
            return 0.0
        cs = sU1 * sU2 + cU1 * cU2 * cl
        sigma = math.atan2(ss, cs)
        sa = cU1 * cU2 * sl / ss
        c2a = 1 - sa * sa
        c2sm = cs - 2 * sU1 * sU2 / c2a if c2a != 0 else 0.0
        C = F_WGS84 / 16 * c2a * (4 + F_WGS84 * (4 - 3 * c2a))
        lam_p = lam
        lam = L + (1 - C) * F_WGS84 * sa * (
            sigma + C * ss * (c2sm + C * cs * (-1 + 2 * c2sm ** 2)))
        if abs(lam - lam_p) < tol:
            break
    u2 = c2a * (A_WGS84 ** 2 - B_WGS84 ** 2) / B_WGS84 ** 2
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    dsig = B * ss * (c2sm + B / 4 * (
        cs * (-1 + 2 * c2sm ** 2)
        - B / 6 * c2sm * (-3 + 4 * ss ** 2) * (-3 + 4 * c2sm ** 2)))
    return B_WGS84 * A * (sigma - dsig)


# --------------------------------------------------------------- moisson OSM

def _requete(bbox, timeout=25):
    s, o, n, e = bbox
    return ('[out:json][timeout:%d];('
            'way["building"](%f,%f,%f,%f);'
            ');out body geom;' % (timeout, s, o, n, e))


def moissonner(bbox, cache=True):
    os.makedirs(CACHE, exist_ok=True)
    cle = "osm_%s.json" % "_".join("%.5f" % v for v in bbox)
    chemin = os.path.join(CACHE, cle)
    if cache and os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f), {"origine": "cache", "chemin": chemin}
    t0 = time.perf_counter()
    donnees = urllib.parse.urlencode({"data": _requete(bbox)}).encode()
    req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                                 data=donnees,
                                 headers={"User-Agent": "BLADE-training/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        brut = json.loads(r.read().decode("utf-8"))
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(brut, f)
    return brut, {"origine": "reseau", "duree_s": round(time.perf_counter() - t0, 1),
                  "chemin": chemin}


def _hauteur(tags):
    for cle, facteur in (("height", 1.0), ("building:levels", ETAGE_M)):
        v = tags.get(cle)
        if v:
            try:
                return abs(float(str(v).split()[0].replace(",", "."))) * facteur
            except ValueError:
                pass
    return None


def emprises(brut):
    """Chemins FERMES uniquement : une emprise ouverte ne fait pas un volume."""
    sortie, rejets = [], {"non_ferme": 0, "trop_court": 0}
    for el in brut.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        pts = [(g["lat"], g["lon"]) for g in el["geometry"]]
        if len(pts) < 4:
            rejets["trop_court"] += 1
            continue
        if abs(pts[0][0] - pts[-1][0]) > 1e-9 or abs(pts[0][1] - pts[-1][1]) > 1e-9:
            rejets["non_ferme"] += 1
            continue
        tags = el.get("tags", {})
        sortie.append({"id": el["id"], "points": pts[:-1], "tags": tags,
                       "hauteur": _hauteur(tags),
                       "etages": tags.get("building:levels")})
    return sortie, rejets


# --------------------------------------------------------------- geometrie

def aire_shoelace(xy):
    n = len(xy)
    s = sum(xy[i][0] * xy[(i + 1) % n][1] - xy[(i + 1) % n][0] * xy[i][1]
            for i in range(n))
    return abs(s) / 2.0


def construire(emprises_, lat0, lon0, hauteur_defaut=12.0):
    """Un bmesh unique, une ile fermee par batiment. Cotes en metres."""
    bm = bmesh.new()
    fiches = []
    for e in emprises_:
        xy = [projeter(la, lo, lat0, lon0) for la, lo in e["points"]]
        if aire_shoelace(xy) < 1.0:          # moins d'un metre carre : ce n'est pas un batiment
            continue
        h = e["hauteur"] or hauteur_defaut
        base = [bm.verts.new((x, y, 0.0)) for x, y in xy]
        try:
            f = bm.faces.new(base)
        except ValueError:
            for v in base:
                bm.verts.remove(v)
            continue
        r = bmesh.ops.extrude_face_region(bm, geom=[f])
        haut = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=haut, vec=(0.0, 0.0, h))
        fiches.append({"id": e["id"], "hauteur_m": h, "aire_m2": aire_shoelace(xy),
                       "sommets": len(xy), "etages": e["etages"]})
    # Retourner la face du bas a la main donne des normales incoherentes selon le
    # sens d'enroulement de chaque emprise OSM - mesure : 1046 faces retournees
    # sur 1712. Recalcul global : chaque ile est fermee, donc l'exterieur est
    # defini sans ambiguite.
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return bm, fiches


# --------------------------------------------------------------- controle

def controle(bbox, lat0=None, lon0=None):
    brut, info = moissonner(bbox)
    emp, rejets = emprises(brut)
    if lat0 is None:
        lat0 = (bbox[0] + bbox[2]) / 2.0
        lon0 = (bbox[1] + bbox[3]) / 2.0
    bm, fiches = construire(emp, lat0, lon0)

    crit = []

    def juge(nom, ok, lu, attendu, note=""):
        crit.append({"critere": nom, "lu": lu, "attendu": attendu,
                     "vert": bool(ok), "note": note})

    # 1. deformation de la projection, mesuree contre la geodesique
    pire = 0.0
    paire = None
    for e in emp[:40]:
        pts = e["points"]
        for i in range(0, len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            xa = projeter(a[0], a[1], lat0, lon0)
            xb = projeter(b[0], b[1], lat0, lon0)
            dp = math.hypot(xb[0] - xa[0], xb[1] - xa[1])
            dg = geodesique(a, b)
            if dg > 1.0:
                err = abs(dp - dg) / dg
                if err > pire:
                    pire, paire = err, (a, b, dp, dg)
    juge("deformation de la projection", pire < 1e-4, pire, "< 1e-4",
         "compare a la distance geodesique, %d aretes" % sum(len(e["points"]) for e in emp[:40]))

    # 2. l'aire relue sur le MAILLAGE egale l'aire calculee sur la source
    aire_source = sum(f["aire_m2"] for f in fiches)
    aires_bas = sum(f.calc_area() for f in bm.faces
                    if abs(f.calc_center_median().z) < 1e-9)
    ecart = abs(aires_bas - aire_source) / max(1e-9, aire_source)
    juge("aire au sol : maillage contre source", ecart < 1e-6, aires_bas, aire_source)

    # 3. tous les volumes fermes
    ouvertes = len([e for e in bm.edges if not e.is_manifold])
    juge("volumes fermes", ouvertes == 0, ouvertes, 0)

    # 4. echelle metrique : emprise du maillage contre la bbox geodesique
    xs = [v.co.x for v in bm.verts] or [0.0]
    ys = [v.co.y for v in bm.verts] or [0.0]
    # Overpass rend les chemins qui INTERSECTENT la bbox, avec toute leur
    # geometrie : le maillage deborde donc legitimement. On compare a l'etendue
    # des points REELLEMENT recus, pas a la bbox demandee.
    lats = [la for e in emp for la, lo in e["points"]]
    lons = [lo for e in emp for la, lo in e["points"]]
    largeur_geo = geodesique((lat0, min(lons)), (lat0, max(lons)))
    hauteur_geo = geodesique((min(lats), lon0), (max(lats), lon0))
    el = abs((max(xs) - min(xs)) - largeur_geo) / largeur_geo
    eh = abs((max(ys) - min(ys)) - hauteur_geo) / hauteur_geo
    juge("echelle metrique contre la geodesique", max(el, eh) < 1e-4,
         [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)],
         [round(largeur_geo, 3), round(hauteur_geo, 3)],
         "ecarts relatifs %.2e et %.2e" % (el, eh))

    res = {"source": info, "batiments": len(fiches), "rejets": rejets,
           "sommets": len(bm.verts), "faces": len(bm.faces),
           "criteres": crit, "vert": all(c["vert"] for c in crit),
           "pire_paire": paire}
    return res, bm, fiches
