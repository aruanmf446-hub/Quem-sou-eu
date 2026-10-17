"""Roupas e calçados do catálogo. Cada função gera uma peça .glb compatível com qualquer avatar."""
from __future__ import annotations

import numpy as np

import cloth
import garments as G
from items import ItemBuilder
from raster import fbm, smoothstep, value_noise

TORSO = ('Hips', 'Spine', 'Spine1', 'Spine2', 'LeftShoulder', 'RightShoulder', 'Neck')


_nipples = {}


def nipple_centers(model):
    """Centros dos mamilos (máscara CC0 do MakeHuman) para o tecido não marcá-los."""
    if 'c' not in _nipples:
        from skin_textures import load_mask, sample
        from bodyuv import BodyLayout
        layout = BodyLayout(model)
        mask = load_mask('aureolae')
        vs, ws = [], []
        for mat, corners in layout.faces:
            if mat != 'body':
                continue
            for v, uv in corners:
                vs.append(v)
                ws.append(sample(mask, uv[None])[0])
        vs, ws = np.array(vs), np.array(ws)
        P = model.coords[vs]
        out = []
        for side in (1, -1):
            w = ws * (P[:, 0] * side > 0)
            out.append((P * w[:, None]).sum(0) / max(w.sum(), 1e-9))
        _nipples['c'] = np.array(out)
    return _nipples['c']


def classify_loops(s):
    out = {'neck': [], 'sleeve': [], 'hem': [], 'leg': [], 'other': []}
    for loop in G.loops(s):
        c = s.pos[loop].mean(0)
        out.setdefault('all', []).append(loop)
        if abs(c[0]) > .17:
            out['sleeve'].append(loop)
        elif c[1] > 1.35:
            out['neck'].append(loop)
        elif c[1] < .8 and abs(c[0]) > .04:
            out['leg'].append(loop)
        else:
            out['hem'].append(loop)
    return out


def shirt_surface(model, layout, A: G.Anatomy, sleeve=.52, hem=.055, neck_drop=.012, v_neck=0.0, ease=.006, sleeve_ease=(.008, .012),
                  drape=1.0, long_sleeve=False):
    neck_y = A.h['Neck'][1]
    hips_y = A.h['Hips'][1]
    c = model.coords

    def ok(v):
        b = A.bone[v]
        torso = np.isin(b, TORSO)
        arm = np.isin(b, ('LeftArm', 'RightArm')) & (A.t[v] < sleeve if not long_sleeve else True)
        fore = np.isin(b, ('LeftForeArm', 'RightForeArm')) & (A.t[v] < sleeve) if long_sleeve else np.zeros(len(v), bool)
        y, x, z = c[v, 1], c[v, 0], c[v, 2]
        neck_cut = neck_y + .012 - neck_drop * (z > 0) - v_neck * np.clip(1 - np.abs(x) / .05, 0, 1) * (z > 0)
        keep = (torso | arm | fore) & (y < neck_cut) & (y > hips_y - hem)
        return keep.all()
    s = G.surface(model, G.select(layout, ok))
    v = s.vid
    arm = np.isin(A.bone[v], ('LeftArm', 'RightArm', 'LeftForeArm', 'RightForeArm'))
    t = np.clip(A.t[v], 0, 1)
    hips_y = A.h['Hips'][1]
    low = smoothstep(A.h['Spine'][1] + .05, hips_y - hem, s.pos[:, 1])
    amount = np.where(arm, sleeve_ease[0] + (sleeve_ease[1] - sleeve_ease[0]) * t, ease + .007 * low)
    G.offset(model, s, amount)
    G.flatten(s, nipple_centers(model), .028)
    G.smooth(s, 14, weights=np.where(arm, .6, 1.0), keep_boundary=True)
    torso = ~arm
    if drape:
        G.drape(model, s, torso & (s.pos[:, 1] < A.h['Spine2'][1] + .05), amount=drape, slope=.14)
    G.push_out(model, s, .004, skip=np.min([np.linalg.norm(s.ref - c, axis=1) for c in nipple_centers(model)], axis=0) < .04)
    # Barra, punhos e gola em linhas retas.
    loops = classify_loops(s)
    for loop in loops['hem']:
        G.straighten(s, loop, np.array([0, hips_y - hem + .012, 0]), [0, 1, 0])
    for loop in loops['sleeve']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        a, f = A.h[f'{side}Arm'], A.h[f'{side}ForeArm']
        axis = (f - a) / np.linalg.norm(f - a)
        G.straighten(s, loop, a + (f - a) * (sleeve - .04), axis)
    for loop in loops['neck']:
        G.straighten(s, loop, s.pos[loop].mean(0) + np.array([0, .004, 0]), [0, 1, .45])
    G.smooth(s, 3, keep_boundary=True)
    nip = nipple_centers(model)
    near = np.min([np.linalg.norm(s.ref - c, axis=1) for c in nip], axis=0) < .04
    G.push_out(model, s, .0015, skip=near)
    G.flatten(s, nip, .03)
    return s


def jersey_camisa10(model, layout, item_id='top_jersey_10', base='#f4d21c', trim='#14733c', accent='#0f5c2f', number='10'):
    A = G.Anatomy(model)
    G.reset_strips()
    s = shirt_surface(model, layout, A)
    from wardrobe2 import clear_bottoms
    clear_bottoms(model, layout, A, s)
    G.reset_strips()
    L = classify_loops(s)
    neck_c = A.h['Neck']
    for loop in L['neck']:
        G.band(s, loop, lambda P: np.array([0, 1, 0]) + (neck_c - P) * np.array([1.2, 0, 1.2]), .011, rows=3, part=1)
    for loop in L['sleeve']:
        side = np.sign(s.pos[loop, 0].mean())
        arm = A.h['LeftForeArm' if side > 0 else 'RightForeArm'] - A.h['LeftArm' if side > 0 else 'RightArm']

        def out_dir(P, arm=arm):
            return np.broadcast_to(arm / np.linalg.norm(arm), P.shape).copy()
        G.band(s, loop, out_dir, .016, rows=3, part=1, flare=.0008)
    G.solidify(s, .0022)
    b = ItemBuilder(model, item_id, 'top')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    yellow, green, dark = cloth.srgb(base), cloth.srgb(trim), cloth.srgb(accent)
    is_trim = part > .5
    inner = part > 1.5
    # Painéis laterais em malha perfurada e costuras raglan.
    side_panel = smoothstep(.115, .13, np.abs(x)) * (np.abs(n[:, 0]) > .35) * (y < A.h['Spine2'][1] + .02) * (y > A.h['Hips'][1] - .08)
    sh = A.h['LeftArm']
    neck = A.h['Neck']
    raglan = np.zeros(len(p))
    for sgn in (1, -1):
        # Linha da gola até a axila.
        ax, ay = neck[0] + sgn * .055, neck[1] - .01
        bx, by = sh[0] * sgn * 1.02, sh[1] - .09
        dx, dy = bx - ax, by - ay
        tt = np.clip(((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy), 0, 1)
        d = np.hypot(x - ax - dx * tt, y - ay - dy * tt)
        raglan = np.maximum(raglan, smoothstep(.0028, .0008, d) * (np.abs(x) < np.abs(bx) + .02))
    # Escudo no peito esquerdo (lado +x do personagem).
    front = (z > .05) & (n[:, 2] > .2)
    back = (z < .0) & (n[:, 2] < -.2)
    cx, cy = .085, A.h['Spine2'][1] + .085
    shield = cloth.sd_polygon(x, y, [(cx - .026, cy + .028), (cx + .026, cy + .028), (cx + .026, cy - .004), (cx, cy - .034), (cx - .026, cy - .004)])
    crown = cloth.sd_polygon(x, y, [(cx - .02, cy + .031), (cx - .02, cy + .046), (cx - .01, cy + .037), (cx, cy + .05), (cx + .01, cy + .037), (cx + .02, cy + .046), (cx + .02, cy + .031)])
    inner_shield = cloth.sd_polygon(x, y, [(cx - .018, cy + .02), (cx + .018, cy + .02), (cx + .018, cy - .003), (cx, cy - .024), (cx - .018, cy - .003)])
    diamond = np.abs(x - cx) / .011 + np.abs(y - cy + .002) / .015 - 1
    crest = front * cloth.fill(np.minimum(shield, crown))
    crest_inner = front * cloth.fill(inner_shield) * (1 - cloth.fill(diamond * .012))
    # Número nas costas.
    num_y = A.h['Spine1'][1] + .035
    digits = back * cloth.fill(cloth.sd_number(number, -x, y, 0, num_y, .2))
    outline = back * cloth.fill(cloth.sd_number(number, -x, y, 0, num_y, .2) - .004) - digits
    sub = cloth.diamond(x, y, .03) / .00006
    albedo = yellow * (1 - .018 * sub)[:, None]
    albedo = albedo * (1 - .06 * side_panel)[:, None]
    albedo = cloth.lin_mix(albedo, yellow * .82, raglan * .7)
    albedo = cloth.lin_mix(albedo, green, crest)
    albedo = cloth.lin_mix(albedo, yellow, crest_inner)
    albedo = cloth.lin_mix(albedo, green, digits)
    albedo = cloth.lin_mix(albedo, dark, np.clip(outline, 0, 1))
    albedo = np.where(is_trim[:, None], green * (.92 + .08 * fbm(p, 300, 2, 2)[:, None]), albedo)
    albedo = np.where(inner[:, None], albedo * .72, albedo)
    var = 1 + .04 * (fbm(p, 25, 3, 7) - .5)
    albedo = albedo * var[:, None]
    rough = np.where(is_trim, .78, .62 - .1 * crest - .12 * digits)
    is_trim_c, side_c, crest_c, digits_c = is_trim, side_panel, crest, digits
    hips_y, arm_y = A.h['Hips'][1], A.h['LeftArm'][1] - .1

    def height(q):
        base_h = cloth.triplanar(q, n, cloth.knit)
        h = base_h + cloth.triplanar(q, n, cloth.perforated) * side_c
        h = h + crest_c * .00025 + digits_c * .0002
        h = np.where(is_trim_c, cloth.triplanar(q, n, cloth.rib), h)
        # Dobras do tecido: cintura (horizontais), axilas (diagonais) e variação suave.
        h = h + (fbm(q, 40, 3, 11) - .5) * .0012 * (1 - is_trim_c)
        waist = smoothstep(.09, .15, np.abs(q[:, 0])) * smoothstep(hips_y + .2, hips_y + .05, q[:, 1]) * smoothstep(hips_y - .06, hips_y + .0, q[:, 1])
        h = h + waist * np.sin(q[:, 1] * 2 * np.pi * 28 + fbm(q, 30, 2, 4) * 5) * .0011
        pit = np.exp(-((np.abs(q[:, 0]) - .16) ** 2 + (q[:, 1] - arm_y) ** 2) / .004)
        h = h + pit * np.sin((np.abs(q[:, 0]) * .7 + q[:, 1]) * 2 * np.pi * 30) * .0012
        return h
    alb, nrm, orm = cloth.finish(bake, np.clip(albedo, 0, 1), np.clip(rough, .3, .95), height)
    mat = b.glb.material('jersey', base=b.glb.texture(alb, fmt='jpeg', quality=90), normal=b.glb.texture(nrm, fmt='webp', quality=90),
                         orm=b.glb.texture(orm, fmt='jpeg', quality=85), roughness=1, sheen=((.35, .33, .25), .6), double=False)
    b.derived('shirt', s, mat)
    return b.save({'hides': ['chest', 'belly', 'upperarm_a', 'upperarm_b']})


def shorts_surface(model, layout, A, length=.5, waist=.05, ease=(.004, .02)):
    c = model.coords
    top = A.h['Hips'][1] + waist

    def ok(v):
        b = A.bone[v]
        legs = np.isin(b, ('LeftUpLeg', 'RightUpLeg')) & (A.t[v] < length + .08)
        hips = np.isin(b, ('Hips', 'Spine'))
        return ((legs | hips) & (c[v, 1] < top)).all()
    s = G.surface(model, G.select(layout, ok))
    v = s.vid
    knee = A.h['LeftLeg'][1]
    hem_y = A.h['LeftUpLeg'][1] - (A.h['LeftUpLeg'][1] - knee) * length
    k = smoothstep(top, hem_y, s.pos[:, 1])
    G.offset(model, s, ease[0] + (ease[1] - ease[0]) * k ** 1.3)
    G.smooth(s, 12, keep_boundary=True)
    G.push_out(model, s, ease[0])
    L = classify_loops(s)
    for loop in L['leg']:
        G.straighten(s, loop, np.array([0, hem_y, 0]), [0, 1, 0])
    for loop in L['hem']:
        G.straighten(s, loop, np.array([0, top, 0]), [0, 1, .12])
    G.smooth(s, 3, keep_boundary=True)
    G.push_out(model, s, .003)
    return s, hem_y, top


def shorts_camisa10(model, layout, item_id='bottom_shorts_10', base='#1f2c66', piping='#169a4a', logo='#f2cf1d'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, hem_y, top = shorts_surface(model, layout, A)
    L = classify_loops(s)
    for loop in L['hem']:
        G.band(s, loop, lambda P: np.array([0, 1, 0]) + P * np.array([0, 0, 0]), .026, rows=3, part=1, inward=.002)
    G.solidify(s, .0022)
    b = ItemBuilder(model, item_id, 'bottom')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    navy, green, yellow = cloth.srgb(base), cloth.srgb(piping), cloth.srgb(logo)
    waist = part > .5
    # Vivos verdes: linha lateral que desce do quadril e cruza a barra na frente.
    hip_x = .15
    piping_d = np.abs(np.abs(x) - (hip_x - (top - y) * .18)) + 0 * z
    line = smoothstep(.0035, .0015, piping_d) * (n[:, 2] > -.3) * (y < top - .03)
    hemline = smoothstep(.003, .0012, np.abs(y - hem_y - .012)) * (np.abs(n[:, 1]) < .7)
    # Losango amarelo na perna esquerda, perto da barra.
    lx, ly = .125, hem_y + .045
    dia = (np.abs(x - lx) / .012 + np.abs(y - ly) / .016 - 1) * .012
    logo_m = cloth.fill(dia) * (z > 0) * (1 - cloth.fill(dia + .003))
    pattern = cloth.diamond(x, y, .028) / .00006
    albedo = navy * (1 + .05 * pattern)[:, None] * (1 + .05 * (fbm(p, 25, 3, 3) - .5))[:, None]
    albedo = cloth.lin_mix(albedo, green, np.clip(line + hemline * .9, 0, 1))
    albedo = cloth.lin_mix(albedo, yellow, logo_m)
    albedo = np.where(waist[:, None], navy * .9, albedo)
    albedo = np.where((part > 1.5)[:, None], albedo * .7, albedo)
    rough = np.where(waist, .8, .6)
    line_c, waist_c = line, waist

    def height(q):
        h = cloth.triplanar(q, n, cloth.knit) * .8 + cloth.triplanar(q, n, cloth.diamond) * 2
        h = np.where(waist_c, cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .004)), h)
        h = h + line_c * .00015
        crotch = np.exp(-((np.abs(q[:, 0]) - .05) ** 2 / .002 + (q[:, 1] - top + .2) ** 2 / .004))
        h = h + (fbm(q, 35, 3, 13) - .5) * .0016 + crotch * np.sin((q[:, 0] * .5 - q[:, 1]) * 2 * np.pi * 25) * .0012
        return h
    alb, nrm, orm = cloth.finish(bake, np.clip(albedo, 0, 1), rough, height)
    mat = b.glb.material('shorts', base=b.glb.texture(alb, fmt='jpeg', quality=90), normal=b.glb.texture(nrm, fmt='webp', quality=90),
                         orm=b.glb.texture(orm, fmt='jpeg', quality=85), roughness=1, sheen=((.25, .3, .45), .6))
    b.derived('shorts', s, mat)
    return b.save({'hides': ['hips', 'thigh_a', 'thigh_b']})


def socks_football(model, layout, item_id='socks_football_10', base='#f1f1ec', stripe='#169a4a', height_t=.16):
    """Meião: camada justa sobre a pele (pés e canelas) com punho e listras."""
    A = G.Anatomy(model)
    G.reset_strips()
    c = model.coords

    def ok(v):
        b = A.bone[v]
        shin = np.isin(b, ('LeftLeg', 'RightLeg')) & (A.t[v] > height_t)
        foot = np.isin(b, ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'))
        return (shin | foot).all()
    s = G.surface(model, G.select(layout, ok))
    v = s.vid
    shin_guard = np.isin(A.bone[v], ('LeftLeg', 'RightLeg')) & (model.normals[v, 2] > .3) & (A.t[v] > .25) & (A.t[v] < .75)
    off = .0018 + .0035 * shin_guard * np.clip(model.normals[v, 2], 0, 1)
    G.offset(model, s, off)
    G.smooth(s, 2, keep_boundary=True)
    top_y = c[v, 1].max()
    for loop in G.loops(s):
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (k - a) / np.linalg.norm(k - a)
        G.straighten(s, loop, s.pos[loop].mean(0), axis, rings=2)
    G.solidify(s, .0018)
    b = ItemBuilder(model, item_id, 'socks')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    white, green = cloth.srgb(base), cloth.srgb(stripe)
    y = p[:, 1]
    knee_y = A.h['LeftLeg'][1]
    ankle_y = A.h['LeftFoot'][1]
    sock_top = knee_y - (knee_y - ankle_y) * height_t
    stripes = np.zeros(len(p))
    for off_y in (.038, .056):
        stripes = np.maximum(stripes, smoothstep(.0075, .0055, np.abs(y - (sock_top - off_y))))
    albedo = white * (1 - .03 * (fbm(p, 30, 2, 4) - .5))[:, None]
    albedo = cloth.lin_mix(albedo, green, stripes)
    cuff = (y > sock_top - .028) & (part < 1.5)
    albedo = np.where((part > 1.5)[:, None], albedo * .8, albedo)
    rough = np.full(len(p), .85)
    cuff_c = cuff

    def height(q):
        h = cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .0024)) * 1.2
        h = h + cuff_c * cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .0032)) * 1.5
        return h + (fbm(q, 60, 2, 8) - .5) * .0006 * (q[:, 1] < sock_top - .08)
    alb, nrm, orm = cloth.finish(bake, np.clip(albedo, 0, 1), rough, height)
    mat = b.glb.material('socks', base=b.glb.texture(alb, fmt='jpeg', quality=88), normal=b.glb.texture(nrm, fmt='webp', quality=88),
                         orm=b.glb.texture(orm, fmt='jpeg', quality=80), roughness=1, sheen=((.4, .4, .4), .7))
    b.derived('socks', s, mat, weight_smooth=1)
    return b.save({'hides': ['shin_b', 'shin_c', 'shin_d', 'feet']})


def foot_frame(A, side):
    ankle = A.h[f'{side}Foot']
    toe = A.h[f'{side}ToeBase']
    f = toe - ankle
    f[1] = 0
    f /= np.linalg.norm(f)
    up = np.array([0, 1, 0])
    lat = np.cross(up, f)
    return ankle, f, lat


def shoe_shell(model, layout, A, collar_t=.9, ease=.0055, base_y=.016):
    c = model.coords

    def ok(v):
        b = A.bone[v]
        foot = np.isin(b, ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'))
        ankle = np.isin(b, ('LeftLeg', 'RightLeg')) & (A.t[v] > collar_t)
        return (foot | ankle).all()
    s = G.surface(model, G.select(layout, ok))
    G.offset(model, s, ease)
    # Forma de calçado: projeta concavidades (entre os dedos, peito do pé) no fecho convexo do pé.
    from scipy.spatial import ConvexHull
    nrm = G.vertex_normals_canon(s)
    for sign in (1, -1):
        m = np.sign(s.pos[:, 0]) == sign
        hull = ConvexHull(s.pos[m])
        eq = hull.equations
        P, D = s.pos[m], nrm[m]
        inside = (P @ eq[:, :3].T + eq[:, 3]).max(1) < 0
        num = -(P @ eq[:, :3].T + eq[:, 3])
        den = D @ eq[:, :3].T
        tt = np.where(den > 1e-6, num / np.maximum(den, 1e-6), np.inf).min(1)
        tt = np.where(inside & np.isfinite(tt), np.minimum(tt, .03), 0)
        s.pos[m] = P + D * tt[:, None] * .85
    G.smooth(s, 6, keep_boundary=True)
    s.pos[:, 1] = np.maximum(s.pos[:, 1], base_y)
    for loop in G.loops(s):
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (k - a) / np.linalg.norm(k - a)
        G.straighten(s, loop, s.pos[loop].mean(0) - axis * .004, axis + np.array([0, 0, -.25]), rings=2)
    G.solidify(s, .002)
    return s


def sole_mesh(s, side_sign, y_bottom=-.006, y_top=.019, flare=.004):
    """Solado: prisma com bordas arredondadas seguindo o contorno do pé."""
    from scipy.spatial import ConvexHull
    sel = (np.sign(s.pos[:, 0]) == side_sign) & (s.pos[:, 1] < .03)
    pts = s.pos[sel][:, [0, 2]]
    hull = ConvexHull(pts)
    poly = pts[hull.vertices]
    # Reamostra o contorno uniformemente.
    closed = np.vstack([poly, poly[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, cum[-1], 72, endpoint=False)
    outline = np.stack([np.interp(t, cum, closed[:, 0]), np.interp(t, cum, closed[:, 1])], 1)
    center = outline.mean(0)
    d = outline - center
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    rings = [(y_bottom, -.002), (y_bottom + .002, 0), (y_top - .004, flare * .2 + .001), (y_top - .0015, .0), (y_top, -.003)]
    pos, uv, tris = [], [], []
    u0, v0, u1, v1 = G.strip_rect()
    n = len(outline)
    for r, (y, extra) in enumerate(rings):
        o = outline + d * (flare + extra)
        for i in range(n):
            pos.append((o[i, 0], y, o[i, 1]))
            uv.append((u0 + (u1 - u0) * i / n, v0 + (v1 - v0) * r / (len(rings) - 1)))
    for r in range(len(rings) - 1):
        for i in range(n):
            a, b = r * n + i, r * n + (i + 1) % n
            c2, d2 = a + n, b + n
            tris += [(a, b, c2), (b, d2, c2)]
    # Tampas (fundo e topo).
    for r, flip in ((0, True), (len(rings) - 1, False)):
        ci = len(pos)
        y = rings[r][0]
        pos.append((center[0], y, center[1]))
        uv.append(((u0 + u1) / 2, v0))
        for i in range(n):
            a, b = r * n + i, r * n + (i + 1) % n
            tris.append((ci, b, a) if flip else (ci, a, b))
    pos = np.array(pos)
    tris = np.array(tris)
    if side_sign < 0:
        pass
    # Garante orientação para fora.
    from model import vertex_normals
    nn = vertex_normals(pos, tris)
    if ((pos[:n] - np.array([center[0], 0, center[1]]))[:, [0, 2]] * nn[:n][:, [0, 2]]).sum() < 0:
        tris = tris[:, ::-1]
    return pos, np.array(uv), tris, outline, center


def studs_mesh(outline, center, f, y_top=-.006, depth=.009, radius=.0055):
    """Travas cônicas: 4 na frente, 2 no calcanhar."""
    rel = outline - center
    along = rel @ f[[0, 2]]
    lat = rel @ np.array([-f[2], f[0]])
    front, back = along.max(), along.min()
    width = lat.max() - lat.min()
    spots = [(front - .025, -.022), (front - .025, .022), (front - .07, -.026), (front - .07, .026), (back + .03, -.017), (back + .03, .017)]
    pos, tris = [], []
    k = 10
    for a, l in spots:
        p = center + a * f[[0, 2]] + l * np.array([-f[2], f[0]])
        base = len(pos)
        for j in range(k):
            ang = 2 * np.pi * j / k
            pos.append((p[0] + np.cos(ang) * radius, y_top, p[1] + np.sin(ang) * radius))
            pos.append((p[0] + np.cos(ang) * radius * .6, y_top - depth, p[1] + np.sin(ang) * radius * .6))
        pos.append((p[0], y_top - depth, p[1]))
        tip = len(pos) - 1
        for j in range(k):
            a0, b0 = base + 2 * j, base + 2 * ((j + 1) % k)
            tris += [(a0, b0, a0 + 1), (b0, b0 + 1, a0 + 1), (a0 + 1, b0 + 1, tip)]
    return np.array(pos), np.array(tris)


def cleats_camisa10(model, layout, item_id='shoes_cleats_10', base='#f3f3f0', overlay='#1d4a63', heel='#f2c81d', stud='#178a45'):
    A = G.Anatomy(model)
    G.reset_strips()
    s = shoe_shell(model, layout, A)
    b = ItemBuilder(model, item_id, 'shoes')
    bake = cloth.bake_surface(s, 1024)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    white, navy, yellow, green = cloth.srgb(base), cloth.srgb(overlay), cloth.srgb(heel), cloth.srgb(stud)
    albedo = np.tile(white, (len(p), 1))
    rough = np.full(len(p), .42)
    lace_m = np.zeros(len(p))
    swirl_m = np.zeros(len(p))
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = np.sign(p[:, 0]) == sign
        rel = p - ankle
        fw, lt, up = rel @ f, rel @ lat, p[:, 1]
        lace = (np.abs(lt) < .019) * (fw > .0) * (fw < .11) * (n[:, 1] > .25)
        lace_rows = smoothstep(.3, .12, np.abs((fw / .012) % 1 - .5)) * smoothstep(.016, .011, np.abs(lt))
        eyestay = smoothstep(.003, .0015, np.abs(np.abs(lt) - .019)) * (fw > -.005) * (fw < .115) * (n[:, 1] > .2)
        tongue = (np.abs(lt) < .022) * (fw > -.01) * (fw < .12) * (n[:, 1] > .25)
        wave = .045 + .014 * np.sin(fw * 38 + .5) - fw * .08
        swirl = smoothstep(.012, .008, np.abs(up - wave)) * (np.abs(n[:, 1]) < .85) * (fw > -.06) * (fw < .15)
        swirl = np.maximum(swirl, smoothstep(.004, .002, np.abs(up - wave + .02)) * (np.abs(n[:, 1]) < .85) * (fw > -.04) * (fw < .12))
        heelc = smoothstep(-.035, -.05, fw) * (up < .09)
        albedo[m] = cloth.lin_mix(albedo[m], navy, swirl[m])
        albedo[m] = cloth.lin_mix(albedo[m], yellow, heelc[m] * .95)
        albedo[m] = cloth.lin_mix(albedo[m], white * .9, tongue[m] * .3)
        albedo[m] = cloth.lin_mix(albedo[m], navy, (lace * (1 - lace_rows) * .85 + eyestay)[m].clip(0, 1))
        albedo[m] = cloth.lin_mix(albedo[m], np.array([.97, .97, .96]), (lace * lace_rows)[m])
        toe = smoothstep(.09, .13, fw) * (up < .05)
        albedo[m] = cloth.lin_mix(albedo[m], white * .88, toe[m] * .5)
        lace_m[m] = (lace * lace_rows)[m]
        swirl_m[m] = swirl[m]
    albedo = np.where((part > 1.5)[:, None], yellow * .8, albedo)
    lace_c, swirl_c = lace_m, swirl_m

    def height(q):
        h = (fbm(q, 900, 2, 5) - .5) * .00006 + lace_c * .0012 + swirl_c * .0002
        return h
    alb, nrm, orm = cloth.finish(bake, np.clip(albedo, 0, 1), rough, height)
    mat = b.glb.material('upper', base=b.glb.texture(alb, fmt='jpeg', quality=90), normal=b.glb.texture(nrm, fmt='webp', quality=90),
                         orm=b.glb.texture(orm, fmt='jpeg', quality=85), roughness=1, clearcoat=(.35, .3))
    b.derived('upper', s, mat, weight_smooth=2)
    sole_mat = b.glb.material('sole', color=(*[c ** 2.2 for c in white], 1), roughness=.55)
    stud_mat = b.glb.material('studs', color=(*[c ** 2.2 for c in green], 1), roughness=.45)
    for side, sign in (('Left', 1), ('Right', -1)):
        pos, uv, tris, outline, center = sole_mesh(s, sign)
        b.bound(f'sole_{side}', pos, tris, uv, sole_mat, bone=f'{side}Foot')
        _, f, _ = foot_frame(A, side)
        sp, st = studs_mesh(outline, center, f)
        b.bound(f'studs_{side}', sp, st, np.zeros((len(sp), 2)), stud_mat, bone=f'{side}Foot')
    return b.save({'hides': ['feet'], 'lift': .012})
