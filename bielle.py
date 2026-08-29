"""bielle.py - palier 7, second volet : cinematique exacte, animee et relue.

Bielle-manivelle. La position du piston se ferme analytiquement :

    x(theta) = r cos(theta) + sqrt(L^2 - r^2 sin^2(theta))

La verification ne compare pas le rendu a une intention : elle pose une vraie
animation par cles, puis relit la geometrie EVALUEE image par image et controle
deux choses qu'aucun reglage ne peut truquer :
  - la bielle ne s'allonge pas (distance entre ses deux axes = L, constante) ;
  - le piston tombe sur la formule fermee.
"""
import bpy, bmesh, math


def cotes(r=40.0, L=130.0, alesage=70.0):
    return {"manivelle_mm": r, "bielle_mm": L, "alesage_mm": alesage,
            "course_mm": 2.0 * r,
            "pmh_mm": r + L, "pmb_mm": L - r,
            "rapport_r_sur_L": r / L}


def position_piston(theta, r, L):
    s = r * math.sin(theta)
    return r * math.cos(theta) + math.sqrt(max(0.0, L * L - s * s))


def _cylindre(nom, rayon_mm, hauteur_mm, segments=32, axe='Z'):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments,
                          radius1=rayon_mm / 1000.0, radius2=rayon_mm / 1000.0,
                          depth=hauteur_mm / 1000.0)
    if axe == 'X':
        bmesh.ops.rotate(bm, verts=bm.verts,
                         matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, 'Y'))
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    bm.free()
    return me


def monter(r=40.0, L=130.0, alesage=70.0, prefixe="MEC"):
    """Trois objets + deux temoins d'axe. Les temoins servent a MESURER."""
    sc = bpy.context.scene
    for o in list(sc.objects):
        if o.name.startswith(prefixe):
            bpy.data.objects.remove(o, do_unlink=True)

    manivelle = bpy.data.objects.new(prefixe + "_Manivelle",
                                     _cylindre("m_manivelle", 18.0, 14.0))
    sc.collection.objects.link(manivelle)
    bras = bpy.data.objects.new(prefixe + "_Bras", _cylindre("m_bras", 9.0, 12.0))
    sc.collection.objects.link(bras)
    bras.parent = manivelle
    bras.location = (r / 1000.0, 0.0, 0.0)

    axe_manivelle = bpy.data.objects.new(prefixe + "_AxeManivelle", None)
    sc.collection.objects.link(axe_manivelle)
    axe_manivelle.parent = manivelle
    axe_manivelle.location = (r / 1000.0, 0.0, 0.0)

    bielle = bpy.data.objects.new(prefixe + "_Bielle",
                                  _cylindre("m_bielle", 7.0, L, axe='X'))
    sc.collection.objects.link(bielle)
    bielle.data.transform(__import__("mathutils").Matrix.Translation(
        (L / 2000.0, 0.0, 0.0)))          # origine sur l'axe cote manivelle

    axe_piston = bpy.data.objects.new(prefixe + "_AxePiston", None)
    sc.collection.objects.link(axe_piston)
    axe_piston.parent = bielle
    axe_piston.location = (L / 1000.0, 0.0, 0.0)

    piston = bpy.data.objects.new(prefixe + "_Piston",
                                  _cylindre("m_piston", alesage / 2.0 - 0.5, 55.0, 48, axe='X'))
    sc.collection.objects.link(piston)
    return {"manivelle": manivelle, "bielle": bielle, "piston": piston,
            "axe_manivelle": axe_manivelle, "axe_piston": axe_piston}


def animer(objets, r, L, images=120):
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, images
    man, bie, pis = objets["manivelle"], objets["bielle"], objets["piston"]
    for o in (man, bie, pis):
        o.animation_data_clear()
    for i in range(images + 1):
        f = 1 + i
        th = 2.0 * math.pi * i / images
        xp = position_piston(th, r, L)
        man.rotation_euler = (0.0, 0.0, th)
        man.keyframe_insert("rotation_euler", frame=f)
        cx, cy = r * math.cos(th) / 1000.0, r * math.sin(th) / 1000.0
        bie.location = (cx, cy, 0.0)
        phi = math.atan2(-r * math.sin(th), xp - r * math.cos(th))
        bie.rotation_euler = (0.0, 0.0, phi)
        bie.keyframe_insert("location", frame=f)
        bie.keyframe_insert("rotation_euler", frame=f)
        pis.location = (xp / 1000.0, 0.0, 0.0)
        pis.keyframe_insert("location", frame=f)
    # vitesse de rotation constante : la manivelle doit tourner en LINEAR
    for o in (man, bie, pis):
        ad = o.animation_data
        if not ad or not ad.action:
            continue
        cb = ad.action.layers[0].strips[0].channelbag(ad.action_slot)
        for fc in cb.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    return images


def controle(r=40.0, L=130.0, images=120, tolerance=1e-6):
    """Relit la geometrie EVALUEE image par image. Aucun chiffre n'est suppose."""
    objets = monter(r, L)
    animer(objets, r, L, images)
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    am, ap = objets["axe_manivelle"], objets["axe_piston"]
    longueurs, ecarts_piston, ecarts_manivelle = [], [], []
    for i in range(images + 1):
        sc.frame_set(1 + i)
        dg = bpy.context.evaluated_depsgraph_get()
        pm = am.evaluated_get(dg).matrix_world.translation
        pp = ap.evaluated_get(dg).matrix_world.translation
        longueurs.append((pp - pm).length * 1000.0)
        th = 2.0 * math.pi * i / images
        attendu = position_piston(th, r, L)
        ecarts_piston.append(abs(pp.x * 1000.0 - attendu))
        # l'axe de manivelle doit rester sur son cercle
        ecarts_manivelle.append(abs(math.hypot(pm.x, pm.y) * 1000.0 - r))
    sc.frame_set(1)

    crit = []

    def juge(nom, ok, lu, attendu, note=""):
        crit.append({"critere": nom, "lu": lu, "attendu": attendu,
                     "vert": bool(ok), "note": note})

    var = max(longueurs) - min(longueurs)
    juge("la bielle ne s'allonge pas", var / L < tolerance, var, 0.0,
         "amplitude sur %d images, en mm" % (images + 1))
    juge("l'axe de manivelle reste sur son cercle",
         max(ecarts_manivelle) / r < tolerance, max(ecarts_manivelle), 0.0)
    juge("le piston suit la formule fermee",
         max(ecarts_piston) / (2 * r) < tolerance, max(ecarts_piston), 0.0)
    c = cotes(r, L)
    course = max(p for p in [position_piston(2 * math.pi * i / images, r, L)
                             for i in range(images + 1)]) \
        - min(position_piston(2 * math.pi * i / images, r, L) for i in range(images + 1))
    juge("course = 2r", abs(course - c["course_mm"]) / c["course_mm"] < 1e-9,
         course, c["course_mm"])
    return {"cotes": c, "criteres": crit, "vert": all(x["vert"] for x in crit),
            "longueur_bielle_relue": (round(min(longueurs), 6), round(max(longueurs), 6))}
