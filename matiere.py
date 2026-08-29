"""matiere.py - palier 8 : la matiere sous controle.

C'est le domaine ou mon jugement visuel est le plus mauvais. Je l'attaque donc
avec des instruments : densite de texel calculee face par face, signature
statistique des cartes cuites, et lecture des pixels plutot que du rendu.

Trois pieges deja payes ailleurs et respectes ici :
  - le colorspace se pose A LA CREATION de l'image ; le changer APRES un bake
    regenere l'image et l'efface ;
  - le fichier s'ecrit sur disque IMMEDIATEMENT apres le bake ;
  - AgX fausse toute mesure : une passe de donnees se lit en `Standard`.
"""
import bpy, bmesh, math, os


# ------------------------------------------------------------ densite de texel

def densite_texel(ob, cotes_texture=2048):
    """Pixels par metre, face par face. Rend aussi l'homogeneite."""
    me = ob.data
    if not me.uv_layers:
        return {"erreur": "pas de couche UV"}
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(ob.matrix_world)
    uv = bm.loops.layers.uv.active
    densites, aires_nulles = [], 0
    for f in bm.faces:
        a3 = f.calc_area()
        if a3 <= 1e-12:
            aires_nulles += 1
            continue
        co = [l[uv].uv for l in f.loops]
        n = len(co)
        a2 = abs(sum(co[i].x * co[(i + 1) % n].y - co[(i + 1) % n].x * co[i].y
                     for i in range(n))) / 2.0
        if a2 <= 1e-14:
            aires_nulles += 1
            continue
        densites.append(math.sqrt(a2) * cotes_texture / math.sqrt(a3))
    bm.free()
    if not densites:
        return {"erreur": "aucune face exploitable"}
    densites.sort()
    n = len(densites)
    med = densites[n // 2]
    p05, p95 = densites[int(0.05 * n)], densites[int(0.95 * n)]
    return {"faces": n, "faces_sans_aire": aires_nulles,
            "mediane_px_par_m": med, "p05": p05, "p95": p95,
            "min": densites[0], "max": densites[-1],
            "dispersion_p95_sur_p05": p95 / p05 if p05 else float("inf")}


# ------------------------------------------------------------------- le bake

def image_pour_bake(nom, cotes=1024, donnees=True):
    """Colorspace pose A LA CREATION : le changer apres un bake efface l'image."""
    if nom in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[nom])
    im = bpy.data.images.new(nom, cotes, cotes, alpha=False, float_buffer=False)
    im.colorspace_settings.name = 'Non-Color' if donnees else 'sRGB'
    return im


def _noeud_image_actif(ob, im):
    mat = ob.data.materials[0] if ob.data.materials else None
    if mat is None:
        mat = bpy.data.materials.new("M_" + ob.name)
        ob.data.materials.append(mat)
    mat.use_nodes = True
    nt = mat.node_tree
    n = nt.nodes.get("_cible_bake") or nt.nodes.new('ShaderNodeTexImage')
    n.name = "_cible_bake"
    n.image = im
    nt.nodes.active = n          # la cible du bake, c'est le noeud image ACTIF
    return n


def cuire(haute, basse, type_bake='NORMAL', cotes=1024, extrusion=0.0035,
          dossier=None, echantillons=32):
    import sys
    d = bpy.utils.user_resource('SCRIPTS', path="modules")
    if d not in sys.path:
        sys.path.append(d)
    import atelier
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'
    sc.cycles.samples = echantillons
    sc.view_settings.view_transform = 'Standard'      # jamais AgX pour des donnees
    sc.render.bake.use_selected_to_active = True
    sc.render.bake.cage_extrusion = extrusion
    sc.cycles.bake_type = type_bake

    nom = "BAKE_%s_%s" % (type_bake.title(), basse.name)
    im = image_pour_bake(nom, cotes, donnees=(type_bake == 'NORMAL'))
    _noeud_image_actif(basse, im)

    for o in bpy.context.scene.objects:
        o.select_set(False)
    haute.select_set(True)
    basse.select_set(True)
    bpy.context.view_layer.objects.active = basse

    # DEPENDANCE CIRCULAIRE. Si le noeud image cible est encore branche dans le
    # shader, Blender lit l'image qu'il est en train d'ecrire et previent par un
    # simple « Info: Circular dependency for image ... » - facile a rater dans la
    # sortie. Resultat mesure : des pixels NOIRS dans le rendu (p01 tombe de 0,44
    # a 0), et un balayage de cage sans le moindre effet, les quatre valeurs
    # rendant la meme signature au millieme. On debranche, on cuit, on rebranche.
    # Un objet masque au RENDU ne participe pas au bake. Masquer la haute
    # definition pour un rendu de controle, puis relancer un bake sans la
    # readfficher, produit une carte plate - et un balayage de cage dont les
    # quatre valeurs rendent la meme signature au millieme. Symptome a connaitre.
    etats = {o: (o.hide_render, o.hide_viewport) for o in (haute, basse)}
    for o in (haute, basse):
        o.hide_render = False
        o.hide_viewport = False

    nt = basse.data.materials[0].node_tree
    noeud = nt.nodes["_cible_bake"]
    coupes = []
    a_traiter = [noeud]
    vus = set()
    while a_traiter:
        cur = a_traiter.pop()
        if cur.name in vus:
            continue
        vus.add(cur.name)
        for l in list(nt.links):
            if l.from_node is cur:
                coupes.append((l.from_node.name, l.from_socket.name,
                               l.to_node.name, l.to_socket.name))
                a_traiter.append(l.to_node)
                nt.links.remove(l)
    try:
        with bpy.context.temp_override(**atelier.ctx('VIEW_3D')):
            bpy.ops.object.bake(type=type_bake)
    finally:
        for fn, fs, tn, ts in coupes:
            nt.links.new(nt.nodes[fn].outputs[fs], nt.nodes[tn].inputs[ts])
        for o, (hr, hv) in etats.items():
            o.hide_render, o.hide_viewport = hr, hv

    dossier = dossier or os.path.join(os.path.expanduser("~"), "Blender_Atelier",
                                      "projets", "entrainement", "02_passes")
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, nom + ".png")
    im.filepath_raw = chemin
    im.file_format = 'PNG'
    im.save()                                          # sur disque TOUT DE SUITE
    return im, chemin


def signature(im):
    """Moyennes et ecarts-types par canal. Une image effacee sort a zero partout."""
    n = im.size[0] * im.size[1]
    buf = [0.0] * (n * 4)
    im.pixels.foreach_get(buf)
    moy, ect = [], []
    for c in range(3):
        canal = buf[c::4]
        m = sum(canal) / n
        v = sum((x - m) ** 2 for x in canal) / n
        moy.append(m)
        ect.append(math.sqrt(v))
    return {"moyennes": [round(x, 4) for x in moy],
            "ecarts_types": [round(x, 4) for x in ect],
            "cotes": tuple(im.size)}


def normal_map_valide(sig, tol=0.08):
    """Une carte de normales tangentes valide : moyennes ~ (0,5 ; 0,5 ; 1,0),
    ecarts-types NON NULS. Une image effacee donne (0,0,0) avec ecart nul."""
    m, e = sig["moyennes"], sig["ecarts_types"]
    proche = (abs(m[0] - 0.5) < tol and abs(m[1] - 0.5) < tol and m[2] > 0.90)
    vivante = all(x > 1e-4 for x in e[:2])
    return proche and vivante, {"moyennes": m, "ecarts_types": e,
                                "proche_de_la_signature": proche, "non_vide": vivante}
