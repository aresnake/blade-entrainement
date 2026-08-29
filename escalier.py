"""escalier.py - palier 5 : du systeme, plus de la piece.

Un arbre Geometry Nodes construit ENTIEREMENT par script. Le critere du palier
n'est pas qu'un escalier sorte joli pour un jeu de valeurs, c'est qu'AUCUN jeu
de valeurs ne casse la generation - valeurs absurdes comprises.

Regle de dimensionnement (Blondel) : 2h + g doit tomber entre 590 et 660 mm.
Le generateur ne la force pas, il la MESURE et la rapporte : brider une entree
masquerait justement les cas ou l'arbre se degrade.
"""
import bpy, math

NOM = "BLADE_Escalier"

ENTREES = [
    ("Hauteur", 'NodeSocketFloat', 2.7),
    ("Largeur", 'NodeSocketFloat', 1.0),
    ("Giron", 'NodeSocketFloat', 0.28),
    ("Hauteur de marche", 'NodeSocketFloat', 0.175),
    ("Epaisseur", 'NodeSocketFloat', 0.04),
]


def _socket(g, nom, type_, defaut=None, sortie=False):
    s = g.interface.new_socket(nom, in_out='OUTPUT' if sortie else 'INPUT',
                               socket_type=type_)
    if defaut is not None and hasattr(s, "default_value"):
        s.default_value = defaut
    return s


def construire(remplacer=True):
    """Cree le groupe de noeuds. Rend le node group."""
    if NOM in bpy.data.node_groups:
        if not remplacer:
            return bpy.data.node_groups[NOM]
        bpy.data.node_groups.remove(bpy.data.node_groups[NOM])
    g = bpy.data.node_groups.new(NOM, 'GeometryNodeTree')
    _socket(g, "Geometry", 'NodeSocketGeometry', sortie=True)
    _socket(g, "Nombre de marches", 'NodeSocketInt', sortie=True)
    _socket(g, "Hauteur reelle de marche", 'NodeSocketFloat', sortie=True)
    for nom, t, d in ENTREES:
        _socket(g, nom, t, d)
    _socket(g, "Materiau", 'NodeSocketMaterial')

    n = g.nodes
    ent = n.new('NodeGroupInput'); ent.location = (-900, 0)
    sor = n.new('NodeGroupOutput'); sor.location = (700, 0)

    def math(op, x=0, y=0, loc=(0, 0), clamp=False):
        m = n.new('ShaderNodeMath')
        m.operation = op
        m.use_clamp = clamp
        m.location = loc
        if isinstance(x, (int, float)):
            m.inputs[0].default_value = x
        if isinstance(y, (int, float)):
            m.inputs[1].default_value = y
        return m

    # n_marches = max(1, ceil(Hauteur / Hauteur de marche))
    div = math('DIVIDE', loc=(-700, 200))
    g.links.new(ent.outputs["Hauteur"], div.inputs[0])
    g.links.new(ent.outputs["Hauteur de marche"], div.inputs[1])
    ceil = math('CEIL', loc=(-540, 200))
    g.links.new(div.outputs[0], ceil.inputs[0])
    nmarches = math('MAXIMUM', y=1.0, loc=(-380, 200))
    g.links.new(ceil.outputs[0], nmarches.inputs[0])

    # h_reelle = Hauteur / n_marches
    hr = math('DIVIDE', loc=(-220, 260))
    g.links.new(ent.outputs["Hauteur"], hr.inputs[0])
    g.links.new(nmarches.outputs[0], hr.inputs[1])

    # ligne de points : depart (0,0,0), decalage (giron, 0, h_reelle)
    off = n.new('ShaderNodeCombineXYZ'); off.location = (-60, 120)
    g.links.new(ent.outputs["Giron"], off.inputs["X"])
    g.links.new(hr.outputs[0], off.inputs["Z"])

    # Depart : la PREMIERE marche est deja montee d'une contremarche, sinon le
    # dessus de la derniere tombe a (n-1)*h et l'escalier n'atteint pas l'etage.
    # Mesure a l'appui : z_max valait 2,551 pour une hauteur demandee de 2,700.
    demi_e = math('DIVIDE', y=2.0, loc=(-220, -40))
    g.links.new(ent.outputs["Epaisseur"], demi_e.inputs[0])
    z0 = math('SUBTRACT', loc=(-60, -40))
    g.links.new(hr.outputs[0], z0.inputs[0])
    g.links.new(demi_e.outputs[0], z0.inputs[1])
    depart = n.new('ShaderNodeCombineXYZ'); depart.location = (100, -40)
    g.links.new(z0.outputs[0], depart.inputs["Z"])

    ligne = n.new('GeometryNodeMeshLine'); ligne.location = (300, 200)
    ligne.mode = 'OFFSET'
    g.links.new(nmarches.outputs[0], ligne.inputs["Count"])
    g.links.new(off.outputs["Vector"], ligne.inputs["Offset"])
    g.links.new(depart.outputs["Vector"], ligne.inputs["Start Location"])

    # marche : boite (giron, largeur, epaisseur)
    taille = n.new('ShaderNodeCombineXYZ'); taille.location = (-60, -160)
    g.links.new(ent.outputs["Giron"], taille.inputs["X"])
    g.links.new(ent.outputs["Largeur"], taille.inputs["Y"])
    g.links.new(ent.outputs["Epaisseur"], taille.inputs["Z"])
    cube = n.new('GeometryNodeMeshCube'); cube.location = (120, -160)
    g.links.new(taille.outputs["Vector"], cube.inputs["Size"])

    inst = n.new('GeometryNodeInstanceOnPoints'); inst.location = (340, 0)
    g.links.new(ligne.outputs["Mesh"], inst.inputs["Points"])
    g.links.new(cube.outputs["Mesh"], inst.inputs["Instance"])
    reel = n.new('GeometryNodeRealizeInstances'); reel.location = (520, 0)
    g.links.new(inst.outputs["Instances"], reel.inputs["Geometry"])

    # Sans Set Material, la geometrie sortie porte un emplacement VIDE qui
    # ecrase celui de l'objet : tout rend en blanc. Piege connu des primitives GN.
    setmat = n.new('GeometryNodeSetMaterial'); setmat.location = (600, 0)
    g.links.new(reel.outputs["Geometry"], setmat.inputs["Geometry"])
    g.links.new(ent.outputs["Materiau"], setmat.inputs["Material"])
    g.links.new(setmat.outputs["Geometry"], sor.inputs["Geometry"])
    g.links.new(nmarches.outputs[0], sor.inputs["Nombre de marches"])
    g.links.new(hr.outputs[0], sor.inputs["Hauteur reelle de marche"])
    return g


def _identifiants(g):
    """{nom lisible: identifiant de socket} pour ecrire dans le modificateur."""
    return {i.name: i.identifier for i in g.interface.items_tree
            if getattr(i, "in_out", None) == 'INPUT'}


def poser(objet_nom="Escalier", **valeurs):
    g = construire(remplacer=False)
    ob = bpy.data.objects.get(objet_nom)
    if ob is None:
        me = bpy.data.meshes.new(objet_nom)
        ob = bpy.data.objects.new(objet_nom, me)
        bpy.context.scene.collection.objects.link(ob)
    mod = next((m for m in ob.modifiers if m.type == 'NODES'), None)
    if mod is None:
        mod = ob.modifiers.new("Escalier", 'NODES')
    mod.node_group = g
    ids = _identifiants(g)
    # En 5.x les entrees d'un modificateur Geometry Nodes ne sont PLUS des
    # IDProperties : mod["Socket_2"] leve « id properties not supported ».
    # Le chemin est mod.properties.inputs[<identifiant>]["value"].
    for k, v in valeurs.items():
        nom = k.replace("_", " ")
        if nom not in ids:
            raise KeyError("socket inconnu : %r (disponibles : %s)" % (nom, list(ids)))
        mod.properties.inputs[ids[nom]]["value"] = float(v)
    ob.update_tag()
    bpy.context.view_layer.update()
    return ob, mod


def mesures(ob):
    """Relit la geometrie EVALUEE : nombre de marches, hauteurs, degenerescences."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    if me is None or len(me.vertices) == 0:
        ev.to_mesh_clear()
        return {"sommets": 0, "faces": 0, "vide": True}
    zs = sorted(set(round(v.co.z, 6) for v in me.vertices))
    aires = [p.area for p in me.polygons]
    res = {"sommets": len(me.vertices), "faces": len(me.polygons), "vide": False,
           "z_min": min(zs), "z_max": max(zs),
           "faces_degenerees": sum(1 for a in aires if a <= 1e-12),
           "aire_mini": min(aires) if aires else 0.0,
           "marches_estimees": len(me.vertices) // 8}
    ev.to_mesh_clear()
    return res


def balayage():
    """Le critere du palier : rien ne casse, y compris sur des valeurs absurdes."""
    cas = []
    normaux = [(2.7, 1.0, 0.28, 0.175, 0.04), (3.2, 1.2, 0.30, 0.17, 0.05),
               (1.0, 0.8, 0.25, 0.20, 0.03), (5.0, 1.5, 0.32, 0.16, 0.06)]
    absurdes = [(0.0, 1.0, 0.28, 0.175, 0.04),      # hauteur nulle
                (2.7, 1.0, 0.0, 0.175, 0.04),       # giron nul
                (2.7, 1.0, 0.28, 0.0, 0.04),        # hauteur de marche nulle
                (2.7, 0.0, 0.28, 0.175, 0.04),      # largeur nulle
                (2.7, 1.0, 0.28, 0.175, 0.0),       # epaisseur nulle
                (-2.7, 1.0, 0.28, 0.175, 0.04),     # hauteur negative
                (2.7, 1.0, -0.28, 0.175, 0.04),     # giron negatif
                (1000.0, 1.0, 0.28, 0.175, 0.04),   # tres grand
                (2.7, 1.0, 0.28, 1e-4, 0.04)]       # 27 000 marches
    for etiquette, jeu in (("normal", normaux), ("absurde", absurdes)):
        for (H, W, G, hm, E) in jeu:
            ob, mod = poser("Escalier", Hauteur=H, Largeur=W, Giron=G,
                            Hauteur_de_marche=hm, Epaisseur=E)
            m = mesures(ob)
            blondel = 2.0 * (H / max(1.0, math.ceil(abs(H) / hm) if hm else 1.0)) + G \
                if hm else None
            cas.append({"type": etiquette, "entrees": (H, W, G, hm, E),
                        "sommets": m["sommets"], "vide": m["vide"],
                        "degenerees": m.get("faces_degenerees"),
                        "z": (m.get("z_min"), m.get("z_max")),
                        "blondel_mm": round(blondel * 1000.0, 1) if blondel else None})
    plante = [c for c in cas if c["type"] == "normal" and (c["vide"] or c["degenerees"])]
    return {"cas": cas, "normaux_sains": len(plante) == 0,
            "aucune_exception": True}
