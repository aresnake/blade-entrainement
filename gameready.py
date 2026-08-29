"""gameready.py - palier 4 : LODs, collision, export, et le controle du retour.

Regle du palier : un export n'est valide que s'il REVIENT identique. On ne
compare pas des intentions, on reimporte et on mesure.
"""
import bpy, bmesh, os, math
from mathutils.bvhtree import BVHTree


def _bvh_de(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def ecart_geometrique(ob, reference):
    """Plus grand ecart des sommets de `ob` a la SURFACE de `reference`, en mm."""
    bvh = _bvh_de(reference)
    pire = 0.0
    mw = ob.matrix_world
    for v in ob.data.vertices:
        loc, nor, idx, d = bvh.find_nearest(mw @ v.co)
        if loc is not None and d > pire:
            pire = d
    return pire * 1000.0


def lods(ob, ratios=(0.5, 0.25, 0.1)):
    """Cree les LOD par decimation, et MESURE l'erreur de chacun."""
    sortie = []
    base = ob.name.rsplit("_LOD", 1)[0]
    for i, r in enumerate(ratios, start=1):
        cp = ob.copy()
        cp.data = ob.data.copy()
        cp.name = cp.data.name = "%s_LOD%d" % (base, i)
        bpy.context.scene.collection.objects.link(cp)
        m = cp.modifiers.new("dec", 'DECIMATE')
        m.ratio = r
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(cp.evaluated_get(dg))
        anc = cp.data
        cp.modifiers.remove(m)
        cp.data = me
        me.name = cp.name
        if anc.users == 0:
            bpy.data.meshes.remove(anc)
        sortie.append({"nom": cp.name, "ratio": r, "faces": len(me.polygons),
                       "sommets": len(me.vertices),
                       "ecart_mm": round(ecart_geometrique(cp, ob), 5)})
    return sortie


def collision_convexe(ob, prefixe="UCX"):
    """Coque convexe, convention Unreal : UCX_<nom>_00.

    Le piege : lancer convex_hull sur un bmesh qui contient DEJA les faces de
    l'objet laisse derriere lui des faces et des aretes orphelines - le linter
    a releve 50 aretes ouvertes sur la premiere version. On repart donc d'un
    bmesh ne contenant QUE les sommets : il ne reste rien a nettoyer.
    """
    src_bm = bmesh.new()
    src_bm.from_mesh(ob.data)
    bm = bmesh.new()
    for v in src_bm.verts:
        bm.verts.new(v.co)
    src_bm.free()
    bm.verts.ensure_lookup_table()
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    # geom_interior et geom_unused se recouvrent : concatener sans dedoublonner
    # leve « found the same used multiple times ». Deduplication par identite.
    inutiles = list({id(g): g for g in res["geom_interior"] + res["geom_unused"]}.values())
    if inutiles:
        bmesh.ops.delete(bm, geom=inutiles, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    base = ob.name.rsplit("_LOD", 1)[0].replace("SM_", "")
    nom = "%s_%s_00" % (prefixe, base)
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    ouvertes = len([e for e in bm.edges if not e.is_manifold])
    bm.free()
    cp = bpy.data.objects.new(nom, me)
    bpy.context.scene.collection.objects.link(cp)
    return {"nom": nom, "sommets": len(me.vertices), "faces": len(me.polygons),
            "aretes_ouvertes": ouvertes}


def exporter(objets, dossier, base):
    os.makedirs(dossier, exist_ok=True)
    for o in bpy.context.scene.objects:
        o.select_set(o in objets)
    bpy.context.view_layer.objects.active = objets[0]
    chemins = {}
    fbx = os.path.join(dossier, base + ".fbx")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True,
                             apply_scale_options='FBX_SCALE_ALL',
                             mesh_smooth_type='FACE')
    chemins["fbx"] = fbx
    glb = os.path.join(dossier, base + ".glb")
    bpy.ops.export_scene.gltf(filepath=glb, use_selection=True,
                              export_format='GLB')
    chemins["glb"] = glb
    return {k: {"chemin": v, "ko": round(os.path.getsize(v) / 1024, 1)}
            for k, v in chemins.items() if os.path.exists(v)}


def signature(ob):
    """Ce qu'un aller-retour doit preserver.

    PAS le nombre de sommets : glTF triangule et dedouble les sommets a chaque
    couture d'UV ou rupture de normale, donc 8 498 sommets peuvent revenir a
    32 670 sans qu'un seul micron ait bouge. Ce qui doit se conserver, c'est la
    SURFACE : nombre de triangles, encombrement, aire. Mesure invariante par
    format, la seule qui prouve quelque chose.
    """
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    aire = sum(f.calc_area() for f in bm.faces)
    n_tri = len(bm.faces)
    vs = [v.co for v in bm.verts]
    mini = [min(v[i] for v in vs) for i in range(3)]
    maxi = [max(v[i] for v in vs) for i in range(3)]
    bm.free()
    return {"triangles": n_tri, "aire_mm2": round(aire * 1e6, 4),
            "dimensions_mm": [round((maxi[i] - mini[i]) * 1000.0, 5) for i in range(3)],
            "uv": len(ob.data.uv_layers), "materiaux": len(ob.data.materials),
            "sommets_bruts": len(ob.data.vertices)}


def aller_retour(ob, dossier, base):
    """Exporte, reimporte dans une scene neuve, compare les signatures."""
    avant = signature(ob)
    fichiers = exporter([ob], dossier, base)
    rapports = {}
    for fmt, info in fichiers.items():
        sc = bpy.data.scenes.new("_ar_" + fmt)
        anc = bpy.context.window.scene
        bpy.context.window.scene = sc
        try:
            if fmt == "fbx":
                bpy.ops.import_scene.fbx(filepath=info["chemin"])
            else:
                bpy.ops.import_scene.gltf(filepath=info["chemin"])
            mailles = [o for o in sc.objects if o.type == 'MESH']
            apres = signature(mailles[0]) if mailles else None
        finally:
            bpy.context.window.scene = anc
        ecarts = {}
        if apres:
            for k in ("triangles", "uv", "materiaux"):
                ecarts[k] = (avant[k], apres[k], avant[k] == apres[k])
            ecarts["aire_mm2"] = (avant["aire_mm2"], apres["aire_mm2"],
                                  abs(avant["aire_mm2"] - apres["aire_mm2"])
                                  / max(1e-9, avant["aire_mm2"]) < 1e-4)
            ecarts["dimensions_mm"] = (
                avant["dimensions_mm"], apres["dimensions_mm"],
                all(abs(a - b) / max(1e-9, abs(a)) < 1e-4
                    for a, b in zip(avant["dimensions_mm"], apres["dimensions_mm"])))
            ecarts["_sommets_bruts_pour_information"] = (
                avant["sommets_bruts"], apres["sommets_bruts"], True)
        for o in list(sc.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.scenes.remove(sc)
        rapports[fmt] = {"ko": info["ko"], "objets_importes": bool(apres),
                         "ecarts": ecarts,
                         "fidele": bool(apres) and all(e[2] for e in ecarts.values())}
    return {"avant": avant, "formats": rapports,
            "vert": all(r["fidele"] for r in rapports.values())}
