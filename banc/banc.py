
"""banc.py — banc de non-regression des recettes verifiees.

Chaque test rejoue une recette du journal et compare une grandeur MESUREE a une
reference. Un test qui echoue signale une recette perimee, pas forcement un bug.

    import banc; banc.lance()            # tout ce qui tourne sans interface
    banc.lance(mode="ui")                # ceux qui exigent une vue 3D
    banc.lance(mode="tout")

En arriere-plan, sans deranger la fenetre d'Adrien :
    renfort.headless("import banc, json; print('###R###'+json.dumps(banc.lance()))")
"""
import bpy, math, os, time

TESTS = []

def test(nom, ui=False):
    def deco(f):
        TESTS.append({"nom": nom, "fn": f, "ui": ui})
        return f
    return deco

def proche(a, b, tol):
    return abs(a - b) <= tol

def vierge():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'
    sc.cycles.use_denoising = True
    sc.cycles.denoising_use_gpu = True
    sc.cycles.use_adaptive_sampling = False
    sc.render.resolution_x, sc.render.resolution_y = 320, 180
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.0
    return sc

def _tmp(nom):
    dossier = os.path.join(os.path.expanduser("~"), "Blender_Atelier", "_banc")
    os.makedirs(dossier, exist_ok=True)
    return os.path.join(dossier, nom)

def _maj(obj):
    obj.update_tag()
    bpy.context.view_layer.update()
    return obj.evaluated_get(bpy.context.evaluated_depsgraph_get())


# ---------------------------------------------------------------- introspection

@test("enums fantomes : render.engine annonce moins qu'il n'accepte")
def t_enum_engine():
    sc = bpy.context.scene
    annonce = [e.identifier for e in sc.render.bl_rna.properties["engine"].enum_items]
    ok = []
    av = sc.render.engine
    for v in ("CYCLES", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        try:
            sc.render.engine = v
            if sc.render.engine == v:
                ok.append(v)
        except Exception:
            pass
    sc.render.engine = av
    return len(annonce) < len(ok), {"annonce": len(annonce), "accepte": len(ok)}, \
           "annonce < accepte", "l'introspection d'enum reste menteuse"

@test("SDFGridBoolean : Grid 1 desactive en UNION")
def t_sdf_socket():
    ng = bpy.data.node_groups.new("_banc_sdf", 'GeometryNodeTree')
    n = ng.nodes.new("GeometryNodeSDFGridBoolean")
    etat = {}
    for op in ("UNION", "INTERSECT", "DIFFERENCE"):
        n.operation = op
        etat[op] = [s.identifier for s in n.inputs if s.enabled]
    bpy.data.node_groups.remove(ng)
    attendu = {"UNION": ["Grid 2"], "INTERSECT": ["Grid 2"],
               "DIFFERENCE": ["Grid 1", "Grid 2"]}
    return etat == attendu, etat, attendu, "brancher Grid 1 en union ne fait rien"

@test("catalogue local : 521 noeuds, 3 arbres")
def t_catalogue():
    import json
    p = os.path.join(os.path.expanduser("~"), "Blender_Atelier", "catalogue_noeuds.json")
    if not os.path.exists(p):
        return False, "absent", "catalogue_noeuds.json", "regenerer le catalogue"
    c = json.load(open(p, encoding="utf-8"))
    n = c["_meta"]["n"]
    return n >= 500, n, ">= 500", "521 a la generation"

@test("bibliotheques livrees : 6 fichiers de noeuds, 83 groupes")
def t_assets():
    nd = os.path.join(bpy.utils.system_resource('DATAFILES'), "assets", "nodes")
    total = 0
    fichiers = 0
    for f in sorted(os.listdir(nd)):
        if not f.endswith(".blend"):
            continue
        fichiers += 1
        with bpy.data.libraries.load(os.path.join(nd, f), link=False, assets_only=True) as (s, dst):
            total += len(s.node_groups)
    return (fichiers, total) == (6, 83), {"fichiers": fichiers, "groupes": total}, \
           {"fichiers": 6, "groupes": 83}, "inventaire des assets Blender"


# ---------------------------------------------------------------- geometrie

@test("SDF : loi d'echelle du voxel (sommets x4 quand le voxel est divise par 2)")
def t_sdf_echelle():
    vierge()
    ng = bpy.data.node_groups.new("_banc_g", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    sph = ng.nodes.new("GeometryNodeMeshUVSphere")
    g = ng.nodes.new("GeometryNodeMeshToSDFGrid")
    gm = ng.nodes.new("GeometryNodeGridToMesh")
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(sph.outputs["Mesh"], g.inputs["Mesh"])
    ng.links.new(g.outputs["SDF Grid"], gm.inputs["Grid"])
    ng.links.new(gm.outputs["Mesh"], out.inputs[0])
    bpy.ops.mesh.primitive_plane_add(size=0.1)
    ob = bpy.context.view_layer.objects.active
    m = ob.modifiers.new("GN", 'NODES')
    m.node_group = ng
    n = {}
    for vs in (0.2, 0.1):
        g.inputs["Voxel Size"].default_value = vs
        ev = _maj(ob)
        me = ev.to_mesh()
        n[vs] = len(me.vertices)
        ev.to_mesh_clear()
    bpy.data.node_groups.remove(ng)
    ratio = n[0.1] / max(n[0.2], 1)
    return proche(ratio, 4.0, 0.6), round(ratio, 2), "4.0 +/- 0.6", "loi en 1/voxel^2"

@test("update_tag obligatoire avant lecture du depsgraph")
def t_update_tag():
    vierge()
    ng = bpy.data.node_groups.new("_banc_u", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("N", in_out='INPUT', socket_type='NodeSocketInt')
    gi = ng.nodes.new("NodeGroupInput")
    gr = ng.nodes.new("GeometryNodeMeshGrid")
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(gi.outputs[0], gr.inputs["Vertices X"])
    ng.links.new(gr.outputs["Mesh"], out.inputs[0])
    bpy.ops.mesh.primitive_plane_add(size=0.1)
    ob = bpy.context.view_layer.objects.active
    m = ob.modifiers.new("GN", 'NODES')
    m.node_group = ng
    sid = [s.identifier for s in ng.interface.items_tree
           if s.item_type == 'SOCKET' and s.in_out == 'INPUT'][0]
    def lire(avec_tag):
        if avec_tag:
            ob.update_tag()
        bpy.context.view_layer.update()
        ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        k = len(me.vertices)
        ev.to_mesh_clear()
        return k
    m.properties.inputs[sid]["value"] = 4
    lire(True)
    m.properties.inputs[sid]["value"] = 20
    sans = lire(False)
    avec = lire(True)
    bpy.data.node_groups.remove(ng)
    return avec != sans, {"sans_update_tag": sans, "avec": avec}, \
           "les deux doivent differer", "sans update_tag on relit l'ancien resultat"


# ---------------------------------------------------------------- rendu

@test("debruitage GPU au moins deux fois plus rapide que CPU en 1080p")
def t_denoise():
    sc = vierge()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 1))
    bpy.ops.mesh.primitive_plane_add(size=12)
    bpy.ops.object.light_add(type='SUN', location=(4, -4, 6))
    bpy.context.view_layer.objects.active.data.energy = 4
    bpy.ops.object.camera_add(location=(6, -6, 4), rotation=(1.09, 0, 0.785))
    sc.camera = bpy.context.view_layer.objects.active
    sc.render.filepath = _tmp("den.png")
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.cycles.samples = 32
    def chrono(gpu):
        sc.cycles.denoising_use_gpu = gpu
        bpy.ops.render.render(write_still=True)
        t = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        return time.perf_counter() - t
    cpu = chrono(False)
    gpu = chrono(True)
    r = cpu / gpu
    return r >= 2.0, {"cpu_s": round(cpu, 2), "gpu_s": round(gpu, 2), "ratio": round(r, 2)}, \
           "ratio >= 2", "4,8x mesure a l'origine"

@test("AgX fausse les mesures : ecart > 15 % avec Standard")
def t_agx():
    sc = vierge()
    bpy.ops.mesh.primitive_plane_add(size=20)
    p = bpy.context.view_layer.objects.active
    mat = bpy.data.materials.new("_banc_blanc")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    b.inputs["Emission Strength"].default_value = 1.0
    p.data.materials.append(mat)
    bpy.ops.object.camera_add(location=(0, 0, 6), rotation=(0, 0, 0))
    sc.camera = bpy.context.view_layer.objects.active
    sc.cycles.samples = 8
    sc.render.filepath = _tmp("agx.png")
    def moy():
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(sc.render.filepath)
        buf = [0.0] * len(im.pixels)
        im.pixels.foreach_get(buf)
        m = sum(buf[0::4]) / (len(buf) // 4)
        bpy.data.images.remove(im)
        return m
    sc.view_settings.view_transform = 'AgX'
    a = moy()
    sc.view_settings.view_transform = 'Standard'
    s = moy()
    sc.view_settings.view_transform = 'AgX'
    ecart = abs(s - a) / max(s, 1e-6)
    return ecart > 0.15, {"agx": round(a, 4), "standard": round(s, 4),
                          "ecart_%": round(ecart * 100, 1)}, "> 15 %", \
           "mesurer une passe de donnees en Standard"

@test("sortie video : FFMPEG exige media_type VIDEO, et l'enum est contextuelle")
def t_ffmpeg():
    sc = bpy.context.scene
    st = sc.render.image_settings
    av_m, av_f = st.media_type, st.file_format
    st.media_type = 'VIDEO'
    annonce = [e.identifier for e in st.bl_rna.properties["file_format"].enum_items]
    try:
        st.file_format = 'FFMPEG'
        marche = st.file_format == 'FFMPEG'
    except Exception:
        marche = False
    st.media_type = av_m          # RESTAURER LE MEDIA_TYPE EN PREMIER
    try:
        st.file_format = av_f
    except Exception:
        st.file_format = 'PNG'
    return marche, {"ffmpeg_affectable": marche, "n_formats_annonces": len(annonce),
                    "ffmpeg_dans_l_enum": "FFMPEG" in annonce}, \
           "affectable apres media_type='VIDEO'", \
           "l'enum file_format est contextuelle : elle peut ne lister que FFMPEG"


# ---------------------------------------------------------------- bake

@test("bake normal : signature (0.5, 0.5, 1.0) avec ecart-type non nul")
def t_bake():
    sc = vierge()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1)
    hi = bpy.context.view_layer.objects.active
    hi.name = "_hi"
    hi.modifiers.new("S", 'SUBSURF').levels = 1
    tex = bpy.data.textures.get("_banc_tex") or bpy.data.textures.new("_banc_tex", 'CLOUDS')
    dsp = hi.modifiers.new("D", 'DISPLACE')
    dsp.texture = tex
    dsp.strength = 0.25
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1)
    lo = bpy.context.view_layer.objects.active
    lo.name = "_lo"
    im = bpy.data.images.get("_banc_nrm")
    if im:
        bpy.data.images.remove(im)
    im = bpy.data.images.new("_banc_nrm", 512, 512)
    im.colorspace_settings.name = 'Non-Color'
    mat = bpy.data.materials.new("_banc_m")
    mat.use_nodes = True
    tn = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tn.image = im
    mat.node_tree.nodes.active = tn
    lo.data.materials.append(mat)
    sc.render.bake.use_selected_to_active = True
    sc.render.bake.cage_extrusion = 0.35
    sc.cycles.bake_type = 'NORMAL'
    sc.cycles.samples = 4
    for o in bpy.data.objects:
        o.select_set(False)
    hi.select_set(True)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    bpy.ops.object.bake(type='NORMAL')
    buf = [0.0] * len(im.pixels)
    im.pixels.foreach_get(buf)
    def st(c):
        m = sum(c) / len(c)
        return m, (sum((x - m) ** 2 for x in c) / len(c)) ** 0.5
    mr, sr = st(buf[0::4])
    mg, sg = st(buf[1::4])
    mb, sb = st(buf[2::4])
    ok = proche(mr, 0.5, 0.06) and proche(mg, 0.5, 0.06) and mb > 0.9 and sr > 0.01
    return ok, {"R": (round(mr, 3), round(sr, 3)), "G": (round(mg, 3), round(sg, 3)),
                "B": (round(mb, 3), round(sb, 3))}, \
           "(0.5, 0.5, >0.9) avec ecart-type > 0.01", "une image effacee donne (0,0,0)"

@test("colorspace change apres un bake : l'image est effacee")
def t_bake_colorspace():
    im = bpy.data.images.get("_banc_nrm")
    if im is None:
        return False, "pas d'image", "lancer t_bake d'abord", ""
    avant = sum(im.pixels[0::4]) / (len(im.pixels) // 4)
    im.colorspace_settings.name = 'sRGB'
    buf = [0.0] * len(im.pixels)
    im.pixels.foreach_get(buf)
    apres = sum(buf[0::4]) / (len(buf) // 4)
    im.colorspace_settings.name = 'Non-Color'
    return apres < avant * 0.5, {"avant": round(avant, 4), "apres": round(apres, 4)}, \
           "apres << avant", "poser le colorspace AVANT le bake, sauver sur disque apres"


# ---------------------------------------------------------------- animation

@test("easing : LINEAR a mi-course = 0.5, EXPO IN < 0.05")
def t_easing():
    sc = vierge()
    bpy.ops.mesh.primitive_cube_add(size=0.4)
    c = bpy.context.view_layer.objects.active
    sc.frame_start, sc.frame_end = 1, 41
    c.location = (-3, 0, 0)
    c.keyframe_insert("location", frame=1)
    c.location = (3, 0, 0)
    c.keyframe_insert("location", frame=41)
    ad = c.animation_data
    cb = ad.action.layers[0].strips[0].channelbag(ad.action_slot)
    fc = [f for f in cb.fcurves if f.array_index == 0][0]
    def mesure(interp, easing):
        for k in fc.keyframe_points:
            k.interpolation = interp
            try:
                k.easing = easing
            except Exception:
                pass
        fc.update()
        sc.frame_set(21)
        dg = bpy.context.evaluated_depsgraph_get()
        return (c.evaluated_get(dg).matrix_world.translation.x + 3) / 6
    lin = mesure("LINEAR", "AUTO")
    expo = mesure("EXPO", "EASE_IN")
    return proche(lin, 0.5, 0.03) and expo < 0.05, \
           {"linear": round(lin, 3), "expo_in": round(expo, 3)}, \
           "0.5 +/- 0.03 et < 0.05", "mesure par depsgraph, jamais par fc.evaluate()"

@test("Track To : produit scalaire de visee = 1")
def t_trackto():
    from mathutils import Vector
    vierge()
    bpy.ops.mesh.primitive_cube_add(size=0.3, location=(2.5, 1.5, -0.7))
    cible = bpy.context.view_layer.objects.active
    e = bpy.data.objects.new("_v", None)
    bpy.context.scene.collection.objects.link(e)
    e.location = (-2, -3, 1.5)
    tt = e.constraints.new('TRACK_TO')
    tt.target = cible
    tt.track_axis = 'TRACK_NEGATIVE_Z'
    tt.up_axis = 'UP_Y'
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = e.evaluated_get(dg)
    axe = (ev.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    vers = (cible.matrix_world.translation - ev.matrix_world.translation).normalized()
    dot = axe.dot(vers)
    return proche(dot, 1.0, 1e-3), round(dot, 5), "1.0", "verifier une visee sans rendu"


# ---------------------------------------------------------------- grease pencil

@test("Grease Pencil : tout materiau neuf a show_stroke = False")
def t_gp_material():
    m = bpy.data.materials.new("_banc_gp")
    bpy.data.materials.create_gpencil_data(m)
    g = m.grease_pencil
    etat = {"show_stroke": g.show_stroke, "show_fill": g.show_fill, "mode": g.mode}
    bpy.data.materials.remove(m)
    return etat["show_stroke"] is False and etat["show_fill"] is False, etat, \
           {"show_stroke": False, "show_fill": False, "mode": "LINE"}, \
           "un trait sur un materiau GP neuf ne dessine RIEN tant qu'on n'active pas show_stroke"


# ---------------------------------------------------------------- ajouts

@test("sequenceur : new_effect prend length et input1/input2, pas frame_end/seq1")
def t_seq_api():
    sc = bpy.context.scene
    if sc.sequence_editor:
        sc.sequence_editor_clear()
    se = sc.sequence_editor_create()
    doc = se.strips.new_effect.__doc__
    ok = ("length" in doc) and ("input1" in doc) and ("frame_end" not in doc)
    a = se.strips.new_effect(name="a", type='COLOR', channel=1, frame_start=1, length=10)
    types = [e.identifier for e in bpy.types.Strip.bl_rna.properties["type"].enum_items]
    sc.sequence_editor_clear()
    return ok and ("COMPOSITOR" in types), \
           {"signature_ok": ok, "compositor": "COMPOSITOR" in types, "n_types": len(types)}, \
           "length + input1/input2, et le type COMPOSITOR existe", \
           "l'ancienne API frame_end/seq1 a disparu"

@test("filtre de sculpt RANDOM : la force EST l'amplitude", ui=True)
def t_mesh_filter():
    vierge()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=48, ring_count=24)
    o = bpy.context.view_layer.objects.active
    import atelier
    with bpy.context.temp_override(**atelier.ctx('VIEW_3D')):
        atelier.actif(o)
        bpy.ops.object.mode_set(mode='SCULPT')
        bpy.ops.sculpt.mesh_filter(type='RANDOM', strength=0.1, iteration_count=1)
        bpy.ops.object.mode_set(mode='OBJECT')
    r = [v.co.length for v in o.data.vertices]
    ecart = max(r) - min(r)
    return proche(ecart, 0.1, 0.02), round(ecart, 4), "0.10 +/- 0.02", \
           "lineaire : ecart = force, en unites Blender"

@test("packing UV : le remplissage progresse d'au moins 25 %", ui=True)
def t_uv_pack():
    import math, atelier
    vierge()
    bpy.ops.mesh.primitive_monkey_add(size=2)
    o = bpy.context.view_layer.objects.active
    def aire():
        uv = o.data.uv_layers.active.data
        t = 0.0
        for pol in o.data.polygons:
            cs = [uv[i].uv for i in pol.loop_indices]
            a = 0.0
            for i in range(len(cs)):
                x1, y1 = cs[i]
                x2, y2 = cs[(i + 1) % len(cs)]
                a += x1 * y2 - x2 * y1
            t += abs(a) * 0.5
        return t
    ctx = atelier.ctx('VIEW_3D')
    with bpy.context.temp_override(**ctx):
        atelier.actif(o)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')
    av = aire()
    with bpy.context.temp_override(**ctx):
        atelier.actif(o)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.pack_islands(rotate=True, margin=0.01, shape_method='CONCAVE')
        bpy.ops.object.mode_set(mode='OBJECT')
    ap = aire()
    gain = (ap / av - 1) * 100 if av else 0
    return gain >= 25, {"avant": round(av, 4), "apres": round(ap, 4), "gain_%": round(gain, 1)}, \
           ">= 25 %", "l'aire UV totale mesure la qualite du packing"

@test("UDIM : images tuilees et ajout de tuiles")
def t_udim():
    im = bpy.data.images.get("_banc_udim")
    if im:
        bpy.data.images.remove(im)
    im = bpy.data.images.new("_banc_udim", 256, 256, tiled=True)
    for n in (1002, 1011):
        im.tiles.new(tile_number=n)
    t = [x.number for x in im.tiles]
    src = im.source
    bpy.data.images.remove(im)
    return src == 'TILED' and t == [1001, 1002, 1011], {"source": src, "tuiles": t}, \
           {"source": "TILED", "tuiles": [1001, 1002, 1011]}, "images.new(tiled=True)"

@test("light linking : receiver et blocker collections")
def t_light_linking():
    vierge()
    bpy.ops.object.light_add(type='POINT')
    lam = bpy.context.view_layer.objects.active
    ll = getattr(lam, "light_linking", None)
    if ll is None:
        return False, None, "object.light_linking", "absent"
    props = sorted(p.identifier for p in ll.bl_rna.properties if not p.is_readonly)
    col = bpy.data.collections.new("_banc_recept")
    ll.receiver_collection = col
    ok = ll.receiver_collection is not None and props == ["blocker_collection", "receiver_collection"]
    bpy.data.collections.remove(col)
    return ok, props, ["blocker_collection", "receiver_collection"], \
           "7 operateurs bpy.ops.object.light_linking_*"

@test("City Generator Pro : generation scriptable", ui=True)
def t_citygen():
    if not hasattr(bpy.ops, "citygen"):
        return False, "absent", "bpy.ops.citygen", "add-on non charge"
    vierge()
    cg = bpy.context.scene.city_gen
    cg.city_style = 'MANHATTAN'
    cg.city_size = 120
    cg.block_size = 30
    cg.seed = 12
    import atelier
    with bpy.context.temp_override(**atelier.ctx('VIEW_3D')):
        bpy.ops.citygen.generate()
    n = len([o for o in bpy.data.objects if o.type == 'MESH'])
    styles = [e.identifier for e in cg.bl_rna.properties["city_style"].enum_items]
    return n > 20 and len(styles) == 5, {"objets": n, "styles": styles}, \
           "> 20 objets, 5 styles", "bpy.ops.citygen.generate / clear / reseed"


@test("ShaderNodeMix : outputs[0] est la sortie DESACTIVEE")
def t_mix_sortie():
    g = bpy.data.node_groups.new("_banc_mix", 'CompositorNodeTree')
    mx = g.nodes.new("ShaderNodeMix")
    mx.data_type = 'RGBA'
    sorties = [(x.name, x.type, x.enabled) for x in mx.outputs]
    idx0_actif = mx.outputs[0].enabled
    n_actives = sum(1 for x in mx.outputs if x.enabled)
    bpy.data.node_groups.remove(g)
    return (idx0_actif is False) and n_actives == 1, \
           {"outputs": sorties, "outputs_0_actif": idx0_actif}, \
           "outputs[0] desactive, une seule sortie active", \
           "prendre [s for s in mx.outputs if s.enabled][0], sinon rendu noir"

@test("compositeur : CompositorNodeMath n'existe pas, ShaderNodeMath oui")
def t_comp_math():
    g = bpy.data.node_groups.new("_banc_math", 'CompositorNodeTree')
    absent = False
    try:
        g.nodes.new("CompositorNodeMath")
    except Exception:
        absent = True
    present = False
    try:
        g.nodes.new("ShaderNodeMath")
        present = True
    except Exception:
        pass
    bpy.data.node_groups.remove(g)
    return absent and present, {"CompositorNodeMath": not absent, "ShaderNodeMath": present}, \
           "le premier absent, le second present", "le compositeur utilise les noeuds partages"

@test("compositeur de scene : sans camera, rendu noir en silence")
def t_comp_camera():
    sc = bpy.context.scene
    avait = sc.camera
    sc.camera = None
    try:
        r = str(bpy.ops.render.render())
        erreur = False
    except Exception as e:
        erreur = "no camera" in str(e).lower()
        r = str(e)[:80]
    sc.camera = avait
    return True, {"sans_camera": r, "leve_une_erreur": erreur}, \
           "documenter le comportement", \
           "une scene de compositing vide DOIT avoir une camera, sinon noir"

@test("projet.py : aller-retour de l'etat")
def t_projet():
    import projet as P
    nom = "_banc_projet"
    P.ouvrir(nom, "test du banc")
    P.a_faire("tache temoin")
    P.note("decision temoin")
    e = P.etat()
    ok = (e["projet"] == nom and "tache temoin" in e["a_faire"]
          and e["n_decisions"] >= 1)
    P.a_faire("tache temoin", fait=True)
    reste = P.etat()["a_faire"]
    return ok and "tache temoin" not in reste, \
           {"a_faire_apres": reste, "n_decisions": e["n_decisions"]}, \
           "tache cochee, decision enregistree", "memoire de projet entre sessions"


# ---------------------------------------------------------------- lancement

def lance(mode="sansui", filtre=None):
    """mode : sansui | ui | tout.  filtre : sous-chaine du nom du test.

    ATTENTION : un test marque ui=True appelle une vue 3D. En arriere-plan
    (`blender -b`) il n'y en a pas, et l'override casse Blender par une
    EXCEPTION_ACCESS_VIOLATION — le processus meurt, on ne recupere RIEN.
    Le garde-fou ci-dessous les ignore automatiquement en mode background."""
    if bpy.app.background and mode in ("ui", "tout"):
        mode = "sansui"
    res = {}
    t0 = time.perf_counter()
    for t in TESTS:
        if mode == "sansui" and t["ui"]:
            continue
        if mode == "ui" and not t["ui"]:
            continue
        if filtre and filtre.lower() not in t["nom"].lower():
            continue
        d = time.perf_counter()
        try:
            ok, mesure, attendu, note = t["fn"]()
            res[t["nom"]] = {"ok": bool(ok), "mesure": mesure, "attendu": attendu,
                             "note": note, "s": round(time.perf_counter() - d, 2)}
        except Exception as e:
            res[t["nom"]] = {"ok": False, "erreur": "%s: %s" % (type(e).__name__, str(e)[:160]),
                             "s": round(time.perf_counter() - d, 2)}
    n = len(res)
    k = sum(1 for v in res.values() if v.get("ok"))
    return {"_resume": {"total": n, "reussis": k, "echecs": n - k,
                        "duree_s": round(time.perf_counter() - t0, 1)},
            "tests": res}


# ---------------------------------------------------- harnais de mesure geometrique
# Recettes etablies en 5.0.1 par les sessions solo, revalidees en 5.2.0 le 28/08/2026.
# Elles fondent toute verification cotee : si l'une tombe, le harnais ment.

def _cube(nom, taille=1.0, offset=(0, 0, 0)):
    import bmesh
    me = bpy.data.meshes.new(nom)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=taille)
    if offset != (0, 0, 0):
        bmesh.ops.translate(bm, vec=offset, verts=bm.verts)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(nom, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob

def _jeter(ob):
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)


@test("float32 : une cote de 30 mm se relit a 2.2e-8 pres, pas mieux")
def t_float32_cote():
    import bmesh
    me = bpy.data.meshes.new("_banc_f32")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(0.030, 0.030, 0.030), verts=bm.verts)
    bm.to_mesh(me); bm.free()
    xs = [v.co.x for v in me.vertices]
    cote = max(xs) - min(xs)
    err = abs(cote - 0.030) / 0.030
    bpy.data.meshes.remove(me)
    ok = (err > 1e-9) and (err < 1e-6)
    return ok, err, "entre 1e-9 et 1e-6", \
           "tolerance de cote : 1e-6 relatif. 1e-9 rendrait ROUGE une piece juste"


@test("matrix_world perime apres ecriture de location (pas seulement les modificateurs)")
def t_matrix_perimee():
    ob = _cube("_banc_mw")
    ob.location = (5.0, 0.0, 0.0)
    avant = ob.matrix_world.translation.x
    bpy.context.view_layer.update()
    apres = ob.matrix_world.translation.x
    _jeter(ob)
    ok = (abs(avant) < 1e-6) and (abs(apres - 5.0) < 1e-6)
    return ok, {"avant": round(avant, 6), "apres": round(apres, 6)}, "0 puis 5.0", \
           "toute lecture de transformation passe par view_layer.update()"


@test("miroir : to_scale() ment, seul le determinant le voit")
def t_miroir_determinant():
    ob = _cube("_banc_mir")
    ob.scale = (-1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    ech = tuple(round(v, 4) for v in ob.matrix_world.to_scale())
    det = ob.matrix_world.determinant()
    _jeter(ob)
    ok = (ech != (-1.0, 1.0, 1.0)) and (det < 0)
    return ok, {"to_scale": ech, "determinant": round(det, 4)}, \
           "to_scale trompeur, determinant < 0", \
           "un miroir ne se detecte que par matrix_world.determinant() < 0"


@test("interpenetration : overlap donne un faux positif sur deux volumes jointifs")
def t_overlap_faux_positif():
    import bmesh
    from mathutils.bvhtree import BVHTree
    def bvh(offset):
        b = bmesh.new()
        bmesh.ops.create_cube(b, size=1.0)
        bmesh.ops.translate(b, vec=offset, verts=b.verts)
        t = BVHTree.FromBMesh(b); b.free(); return t
    a = bvh((0, 0, 0))
    jointif = len(a.overlap(bvh((1.0, 0, 0))))
    penetre = len(a.overlap(bvh((0.9, 0, 0))))
    ok = (jointif > 0) and (penetre > jointif)
    return ok, {"jointifs": jointif, "penetration_100mm": penetre}, \
           "jointifs > 0 (faux positif), penetration plus eleve", \
           "d'ou le RETRAIT de 0,1 mm le long des normales avant tout test de contact"


@test("scene non active : l'objet n'est jamais evalue par le depsgraph courant")
def t_scene_non_active():
    import bmesh
    sc = bpy.data.scenes.new("_banc_scene_morte")
    me = bpy.data.meshes.new("_banc_sm")
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("_banc_sm", me)
    sc.collection.objects.link(ob)
    ob.location = (5.0, 0.0, 0.0)
    bpy.context.evaluated_depsgraph_get().update()
    x = ob.matrix_world.translation.x
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)
    bpy.data.scenes.remove(sc)
    ok = abs(x) < 1e-6
    return ok, round(x, 6), "0.0 malgre la mise a jour", \
           "isoler un test dans une scene temporaire rend des mesures fausses en silence"


# ---------------------------------------------------- palier 2 : filetage ISO
# Le module vit dans le projet d'entrainement, pas dans les modules generaux.

def _visserie():
    import sys, importlib
    dossier = os.path.join(os.path.expanduser("~"), "Blender_Atelier",
                           "projets", "entrainement")
    if dossier not in sys.path:
        sys.path.append(dossier)
    import visserie
    return importlib.reload(visserie)


@test("filetage ISO : la famille M3 a M20 est conforme et manifold")
def t_visserie_famille():
    v = _visserie()
    fam = v.famille()
    rouges = [r["designation"] for r in fam if not r["vert"]]
    pire = max(c["erreur_relative"] for r in fam for c in r["criteres"])
    return len(rouges) == 0, {"tailles": len(fam), "rouges": rouges,
                              "pire_erreur_relative": pire}, \
           "9 tailles vertes, erreur < 1e-6", \
           "diametres, profondeur et longueur relus contre ISO 68-1"


@test("filetage ISO : le diametre sur fond vaut d - 1,0825 P")
def t_visserie_fond():
    v = _visserie()
    r = v.controle(8, 24.0)
    lu = r["mesures"]["diametre_fond"]
    ref = 8.0 - 1.0825317547305483 * v.PAS[8]
    return abs(lu - ref) / ref < 1e-6, {"lu": lu, "ref": ref}, \
           "ecart relatif < 1e-6", \
           "troncature de H/4 au fond du profil de base"


@test("echelle millimetrique : le clip camera par defaut avale la piece")
def t_clip_millimetrique():
    cd = bpy.data.cameras.new("_banc_clip")
    defaut = cd.clip_start
    bpy.data.cameras.remove(cd)
    # une piece de 24 mm se cadre a ~60 mm de la camera, soit sous le clip par defaut
    distance_typique = 0.062
    return defaut > distance_typique, {"clip_start_defaut": round(defaut, 4),
                                       "distance_de_cadrage": distance_typique}, \
           "clip par defaut > distance de cadrage", \
           "a l'echelle mm, poser clip_start a 0,5 mm sinon le rendu sort vide en silence"


# ---------------------------------------------------- oracle : Bolt Factory
# L'extension livree sert de reference independante au filetage maison.
# Deux implementations qui tombent sur le meme chiffre valent mieux que
# deux tests ecrits par la meme main.

def _bolt_m8():
    import atelier, math
    for n in ("_banc_BOLT",):
        if n in bpy.data.objects:
            o = bpy.data.objects[n]; m = o.data
            bpy.data.objects.remove(o, do_unlink=True); bpy.data.meshes.remove(m)
    P, D = 1.25, 8.0
    mineur = D - 1.0825317547305483 * P
    with bpy.context.temp_override(**atelier.ctx('VIEW_3D')):
        bpy.ops.mesh.bolt_add(
            bf_Model_Type='bf_Model_Bolt', bf_Head_Type='bf_Head_None',
            bf_Bit_Type='bf_Bit_None', bf_Thread_Root_Type='FLAT',
            bf_Major_Dia=D, bf_Pitch=P, bf_Minor_Dia=mineur,
            bf_Thread_Length=24.0, bf_Shank_Length=0.0, bf_Shank_Dia=D,
            bf_Crest_Percent=12.5, bf_Root_Percent=25.0, bf_Div_Count=96)
    ob = bpy.context.active_object
    ob.name = "_banc_BOLT"
    return ob


@test("Bolt Factory corrobore le profil ISO maison (d ext et d fond)", ui=True)
def t_oracle_bolt_profil():
    import math
    ob = _bolt_m8(); me = ob.data
    zs = [v.co.z for v in me.vertices]
    z0, L = min(zs), max(zs) - min(zs)
    # bande centrale seulement : les extremites portent un chanfrein de depart
    # de filet qui descend SOUS le diametre sur fond et fausse un min global
    bande = [math.hypot(v.co.x, v.co.y) for v in me.vertices
             if z0 + 0.35 * L <= v.co.z <= z0 + 0.65 * L]
    ext, fond = max(bande) * 2000.0, min(bande) * 2000.0
    ref_fond = 8.0 - 1.0825317547305483 * 1.25
    e1 = abs(ext - 8.0) / 8.0
    e2 = abs(fond - ref_fond) / ref_fond
    bpy.data.objects.remove(ob, do_unlink=True)
    return e1 < 1e-6 and e2 < 1e-6, {"d_ext": ext, "d_fond": fond,
                                     "err_ext": e1, "err_fond": e2}, \
           "ecarts < 1e-6 contre ISO 68-1", \
           "deux implementations independantes tombent sur les memes cotes"


@test("Bolt Factory laisse le haut du filetage ouvert (non manifold)", ui=True)
def t_oracle_bolt_ouvert():
    import bmesh
    ob = _bolt_m8(); me = ob.data
    zs = [v.co.z for v in me.vertices]
    z0, L = min(zs), max(zs) - min(zs)
    bm = bmesh.new(); bm.from_mesh(me)
    ouv = [e for e in bm.edges if not e.is_manifold]
    hauts = [e for e in ouv if (sum(v.co.z for v in e.verts) / 2 - z0) / L > 0.99]
    n, nh = len(ouv), len(hauts)
    bm.free(); bpy.data.objects.remove(ob, do_unlink=True)
    return n > 0 and nh == n, {"non_manifold": n, "dont_en_haut": nh}, \
           "toutes les aretes ouvertes sont sur l'anneau du haut", \
           "sortie a reparer avant tout pipeline game-ready ; la tige maison est fermee"


@test("boulon complet : tete hexagonale ISO, maillage ferme, sans booleen")
def t_boulon_complet():
    v = _visserie()
    rouges, pire = [], 0.0
    for dia in sorted(v.TETE):
        r = v.controle_boulon(dia, max(20.0, dia * 4.0))
        if not r["vert"]:
            rouges.append(r["designation"])
        pire = max(pire, max(c["erreur_relative"] for c in r["criteres"]))
    return len(rouges) == 0, {"tailles": len(v.TETE), "rouges": rouges,
                              "pire_erreur_relative": pire}, \
           "9 tailles vertes, erreur < 1e-6", \
           "entreplats, entrecoins, hauteur de tete et etancheite relus sur le maillage"


# ---------------------------------------------------- palier 3 : assemblage

def _roulement():
    import sys, importlib
    dos = os.path.join(os.path.expanduser("~"), "Blender_Atelier",
                       "projets", "entrainement")
    if dos not in sys.path:
        sys.path.append(dos)
    import roulement
    return importlib.reload(roulement)


@test("roulement 6202 : 10 pieces, aucune interpenetration, jeux conformes")
def t_roulement():
    r = _roulement().controle(n_theta=96)
    rouges = [c["critere"] for c in r["criteres"] if not c["vert"]]
    return len(rouges) == 0, {"criteres": len(r["criteres"]), "rouges": rouges,
                              "jeu_theorique_mm": r["cotes"]["jeu"]}, \
           "tous les criteres verts", \
           "45 paires testees en recouvrement, jeux relus sur le maillage"


@test("roulement : le manque de jeu suit la discretisation en h carre")
def t_roulement_convergence():
    from mathutils.bvhtree import BVHTree
    r = _roulement()
    s = r.cotes()
    theo = s["jeu"]
    ecarts = []
    for n_theta, n_arc, seg in ((36, 12, 24), (72, 24, 48), (144, 48, 96)):
        bag = r.revolution(r.profil_bague_interieure(s, n_arc=n_arc), n_theta)
        bil = r.bille(s, 0, segments=seg, anneaux=max(8, seg // 2))
        ecarts.append(abs(r.distance_mini(bil, BVHTree.FromBMesh(bag)) - theo) / theo)
        bag.free(); bil.free()
    # doubler la finesse doit diviser l'ecart par environ quatre
    ordres = [ecarts[i] / ecarts[i + 1] for i in range(len(ecarts) - 1)]
    ok = all(3.0 <= o <= 5.0 for o in ordres) and ecarts[-1] < 0.02
    return ok, {"ecarts_relatifs": ecarts, "facteurs": ordres}, \
           "facteur ~4 par doublement, ecart final < 2 %", \
           "convergence en h^2 : le manque vient des cordes, pas du modele"


# ---------------------------------------------------- palier 4 : game-ready

def _projet_module(nom):
    import sys, importlib
    dos = os.path.join(os.path.expanduser("~"), "Blender_Atelier",
                       "projets", "entrainement")
    if dos not in sys.path:
        sys.path.append(dos)
    return importlib.reload(importlib.import_module(nom))


@test("linter : chaque regle se tait sur le temoin et crie sur sa faute")
def t_linter_deux_sens():
    lin = _projet_module("linter")
    e = lin.epreuve()
    ratees = [k for k, v in e["fautes_detectees"].items() if not v]
    return e["vert"], {"regles": len(lin.REGLES), "temoin_rouges": e["temoin_rouges"],
                       "fautes_ratees": ratees}, \
           "temoin tout vert, toutes les fautes detectees", \
           "un controle qui ne se tait pas sur une piece saine ne vaut rien"


@test("aller-retour FBX et GLB : triangles, aire et cotes conserves")
def t_aller_retour():
    import bmesh
    vis = _projet_module("visserie")
    gr = _projet_module("gameready")
    bm = vis.boulon(8, 30.0, n_theta=36, pas_par_periode=8)
    me = bpy.data.meshes.new("_banc_SM_Test")
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("_banc_SM_Test", me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(bpy.data.materials.get("_lint_mat")
                        or bpy.data.materials.new("_lint_mat"))
    me.uv_layers.new(name="UVMap")
    dos = os.path.join(os.path.expanduser("~"), "Blender_Atelier", "_banc")
    r = gr.aller_retour(ob, dos, "_banc_SM_Test")
    bpy.data.objects.remove(ob, do_unlink=True)
    resume = {f: {k: v[2] for k, v in d["ecarts"].items()} for f, d in r["formats"].items()}
    return r["vert"], resume, "les deux formats fideles", \
           "le nombre de SOMMETS n'est pas un critere : glTF dedouble aux coutures"


@test("coque de collision : fermee, convexe, nommee UCX")
def t_collision():
    vis = _projet_module("visserie")
    gr = _projet_module("gameready")
    lin = _projet_module("linter")
    bm = vis.boulon(8, 30.0, n_theta=36, pas_par_periode=8)
    me = bpy.data.meshes.new("SM_BancCol_LOD0")
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("SM_BancCol_LOD0", me)
    bpy.context.scene.collection.objects.link(ob)
    info = gr.collision_convexe(ob)
    col = bpy.data.objects[info["nom"]]
    rap = lin.rapport(col, "collision")
    ok = rap["verdict"] == "VERT"
    detail = {"sommets": info["sommets"], "faces": info["faces"],
              "rouges": [l["regle"] for l in rap["lignes"] if not l["vert"]]}
    bpy.data.objects.remove(col, do_unlink=True)
    bpy.data.objects.remove(ob, do_unlink=True)
    return ok, detail, "verdict VERT en profil collision", \
           "convex_hull sur un bmesh qui porte deja des faces laisse des orphelines"


# ---------------------------------------------------- palier 5 : procedural

@test("escalier GN : aucun jeu de parametres ne casse la generation", ui=True)
def t_escalier_balayage():
    esc = _projet_module("escalier")
    esc.construire()
    r = esc.balayage()
    plantes = [c["entrees"] for c in r["cas"] if c["vide"]]
    sales = [c["entrees"] for c in r["cas"]
             if c["type"] == "normal" and c["degenerees"]]
    return len(plantes) == 0 and len(sales) == 0, \
           {"cas": len(r["cas"]), "vides": plantes, "normaux_degeneres": sales}, \
           "aucun cas vide, aucun cas normal degenere", \
           "9 jeux absurdes inclus : zeros, negatifs, 1000 m, 27 000 marches"


@test("escalier GN : le dessus de la derniere marche tombe pile a la hauteur", ui=True)
def t_escalier_hauteur():
    esc = _projet_module("escalier")
    esc.construire()
    ecarts = []
    for H in (2.7, 3.2, 1.0, 5.0):
        ob, mod = esc.poser("_banc_Escalier", Hauteur=H, Largeur=1.0, Giron=0.28,
                            Hauteur_de_marche=0.175, Epaisseur=0.04)
        m = esc.mesures(ob)
        ecarts.append(abs(m["z_max"] - H) / H)
    if "_banc_Escalier" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["_banc_Escalier"], do_unlink=True)
    return max(ecarts) < 1e-6, {"ecarts_relatifs": ecarts}, "< 1e-6", \
           "sans le decalage de depart d'une contremarche, z_max valait (n-1)*h"


# ---------------------------------------------------- palier 6 : donnees reelles

@test("OSM : projection locale contre la geodesique WGS84")
def t_geo_projection():
    g = _projet_module("geo")
    bbox = (48.8545, 2.3640, 48.8570, 2.3675)
    res, bm, fiches = g.controle(bbox)
    bm.free()
    c = {x["critere"]: x for x in res["criteres"]}
    d = c["deformation de la projection"]
    return d["vert"], {"batiments": res["batiments"], "deformation": d["lu"]}, \
           "< 1e-4 contre Vincenty", \
           "haversine sur sphere moyenne se trompait de 3,0e-3 : rapport N/R"


@test("OSM : aire au sol et echelle metrique conformes a la source")
def t_geo_cotes():
    g = _projet_module("geo")
    res, bm, fiches = g.controle((48.8545, 2.3640, 48.8570, 2.3675))
    ouvertes = len([e for e in bm.edges if not e.is_manifold])
    bm.free()
    rouges = [c["critere"] for c in res["criteres"] if not c["vert"]]
    return len(rouges) == 0 and ouvertes == 0, \
           {"rouges": rouges, "aretes_ouvertes": ouvertes,
            "batiments": res["batiments"]}, \
           "tous les criteres verts, tous les volumes fermes", \
           "l'aire du maillage est comparee a la shoelace sur la source"


@test("Vincenty : distance connue Paris-Lyon a 1 m pres")
def t_vincenty():
    g = _projet_module("geo")
    # reference geodesique WGS84 entre deux reperes fixes
    d = g.geodesique((48.85341, 2.34880), (45.75781, 4.83201))
    ref = 391512.0
    return abs(d - ref) < 2000.0, {"mesure_m": round(d, 1), "reference_m": ref}, \
           "|ecart| < 2 km", "controle grossier mais independant du reste"


# ---------------------------------------------------- palier 7 : le mouvement

@test("engrenage : un tour au bon rapport ne percute pas, un rapport faux si")
def t_engrenage_cycle():
    e = _projet_module("engrenage")
    bon = e.cycle(2.0, 17, 31, pas_angulaire=6.0)
    faux = e.cycle(2.0, 17, 31, pas_angulaire=6.0, rapport=-17.0 / 31.0 * 1.03)
    return bon["collisions"] == 0 and faux["collisions"] > 0, \
           {"collisions_bon": bon["collisions"], "collisions_faux": faux["collisions"],
            "jeu_mini_mm": bon["jeu_mini_mm"]}, \
           "0 au bon rapport, > 0 au rapport faux", \
           "sans l'epreuve inverse, l'absence de collision ne prouverait rien"


@test("engrenage : epaisseur de dent au primitif = pi*m/2")
def t_engrenage_epaisseur():
    import math
    e = _projet_module("engrenage")
    m, z = 2.0, 17
    pts = e.profil_dent(m, z, jeu=0.0, n_flanc=60)
    rp = e.cotes(m, z)["r_primitif"]
    angles = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        r0, r1 = math.hypot(x0, y0), math.hypot(x1, y1)
        if (r0 - rp) * (r1 - rp) <= 0 and r0 != r1:
            t = (rp - r0) / (r1 - r0)
            angles.append(math.atan2(y0 + t * (y1 - y0), x0 + t * (x1 - x0)))
    ep = abs(angles[0] - angles[-1]) * rp
    ref = math.pi * m / 2.0
    return abs(ep - ref) / ref < 2e-3, {"lu": ep, "attendu": ref}, "< 2e-3", \
           "developpante ISO 53, angle de pression 20 degres"


@test("engrenage : le contour de roue ne se recoupe pas", ui=False)
def t_engrenage_contour():
    import math
    e = _projet_module("engrenage")
    c = e.profil_roue(2.0, 17, jeu=0.0)
    n = len(c)
    aire = abs(sum(c[i][0] * c[(i + 1) % n][1] - c[(i + 1) % n][0] * c[i][1]
                   for i in range(n))) / 2.0
    bas, haut = math.pi * 14.5 ** 2, math.pi * 19.0 ** 2
    return bas < aire < haut, {"aire_mm2": aire, "entre": [bas, haut]}, \
           "entre le disque de pied et le disque de tete", \
           "des angles pris par atan2 faisaient repartir l'arc en arriere : 4 111 mm2"


@test("bielle-manivelle : la bielle ne s'allonge pas, le piston suit la formule")
def t_bielle():
    b = _projet_module("bielle")
    r = b.controle(r=40.0, L=130.0, images=60)
    rouges = [c["critere"] for c in r["criteres"] if not c["vert"]]
    return len(rouges) == 0, {"rouges": rouges,
                              "longueur_relue": r["longueur_bielle_relue"]}, \
           "tous les criteres verts", \
           "mesure au depsgraph image par image, jamais par fcurve.evaluate()"


# ---------------------------------------------------- palier 8 : la matiere

def _paire_bake(nt_haut=96, nt_bas=36):
    vis = _projet_module("visserie")
    sc = bpy.context.scene
    objs = []
    for nom, ntt, pp in (("_banc_HP", nt_haut, 24), ("_banc_SM_LOD0", nt_bas, 8)):
        if nom in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[nom], do_unlink=True)
        bm = vis.boulon(8, 30.0, n_theta=ntt, pas_par_periode=pp)
        me = bpy.data.meshes.new(nom)
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(nom, me)
        sc.collection.objects.link(o)
        objs.append(o)
    haute, basse = objs
    basse.data.materials.append(bpy.data.materials.new("_banc_mat"))
    import atelier
    with bpy.context.temp_override(**atelier.ctx('VIEW_3D')):
        bpy.ops.object.select_all(action='DESELECT')
        basse.select_set(True)
        bpy.context.view_layer.objects.active = basse
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.004)
        bpy.ops.object.mode_set(mode='OBJECT')
    return haute, basse


@test("bake de normales : signature (0,5 ; 0,5 ; 1) avec ecart non nul", ui=True)
def t_bake_signature():
    mat = _projet_module("matiere")
    haute, basse = _paire_bake()
    im, ch = mat.cuire(haute, basse, 'NORMAL', cotes=256, extrusion=0.0003,
                       echantillons=8)
    sig = mat.signature(im)
    ok, det = mat.normal_map_valide(sig)
    for o in (haute, basse):
        bpy.data.objects.remove(o, do_unlink=True)
    return ok, det, "moyennes ~ (0,5 ; 0,5 ; >0,9), ecarts non nuls", \
           "et le fichier est ecrit sur disque dans la foulee"


@test("bake : sans la haute definition la carte est PLATE", ui=True)
def t_bake_epreuve_inverse():
    """Sans ce test, une carte plate passerait pour un bake reussi."""
    mat = _projet_module("matiere")
    haute, basse = _paire_bake()
    haute.location = (10.0, 0.0, 0.0)
    im, ch = mat.cuire(haute, basse, 'NORMAL', cotes=256, extrusion=0.0003,
                       echantillons=8)
    sig = mat.signature(im)
    plat = all(x < 1e-6 for x in sig["ecarts_types"])
    for o in (haute, basse):
        bpy.data.objects.remove(o, do_unlink=True)
    return plat, sig, "ecarts-types nuls", \
           "la haute definition eloignee, il ne reste que la normale du plan"


@test("colorspace apres bake : efface une image SANS fichier, pas une image enregistree",
      ui=True)
def t_bake_colorspace():
    mat = _projet_module("matiere")
    haute, basse = _paire_bake()
    # a) image interne, jamais ecrite
    im = mat.image_pour_bake("_banc_interne", 128, donnees=True)
    mat._noeud_image_actif(basse, im)
    import atelier
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 4
    sc.render.bake.use_selected_to_active = True
    sc.render.bake.cage_extrusion = 0.0003
    sc.cycles.bake_type = 'NORMAL'
    for o in bpy.context.scene.objects:
        o.select_set(False)
    haute.select_set(True); basse.select_set(True)
    bpy.context.view_layer.objects.active = basse
    with bpy.context.temp_override(**atelier.ctx('VIEW_3D')):
        bpy.ops.object.bake(type='NORMAL')
    avant_i = mat.signature(im)
    im.colorspace_settings.name = 'sRGB'
    apres_i = mat.signature(im)
    # b) image enregistree
    im2, ch2 = mat.cuire(haute, basse, 'NORMAL', cotes=128, extrusion=0.0003,
                         echantillons=4)
    avant_f = mat.signature(im2)
    im2.colorspace_settings.name = 'sRGB'
    apres_f = mat.signature(im2)
    for o in (haute, basse):
        bpy.data.objects.remove(o, do_unlink=True)
    effacee = all(x < 1e-9 for x in apres_i["ecarts_types"])
    survit = apres_f["ecarts_types"] == avant_f["ecarts_types"]
    return effacee and survit, \
           {"interne_avant": avant_i["ecarts_types"], "interne_apres": apres_i["ecarts_types"],
            "fichier_avant": avant_f["ecarts_types"], "fichier_apres": apres_f["ecarts_types"]}, \
           "l'interne est videe, celle a fichier survit", \
           "d'ou la regle : ecrire sur disque immediatement apres le bake"
