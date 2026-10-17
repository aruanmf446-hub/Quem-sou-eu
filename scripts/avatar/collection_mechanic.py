"""Coleção estilizada: Mecânica dos Céus. Registra as peças no REGISTRY de build_items.

Jaqueta coral cropped de mangas dobradas sobre camisa creme e colete, calça cargo
azul-marinho com joelheiras, botas de cano alto com punho coral e engrenagem,
luvas sem dedos, cinturão de ferramentas com bolsas, bússola e cristal, lenço ao
vento com broche alado, óculos de aviador de latão e chave inglesa.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

import cloth
import garments as G
import overlays
from accessories import cylinder, head_ring, merge, torus
from items import ItemBuilder
from model import vertex_normals
from raster import Bake, fbm, smoothstep
from wardrobe import TORSO, classify_loops, foot_frame, nipple_centers, sole_mesh
from wardrobe2 import (arm_axis, clear_bottoms, fabric_height, flat_material, hem_ease, lin, long_top_surface, neutral,
                       sphere_mesh, tex_material)

CORAL = '#e0694e'
CREAM = '#efe2c4'
BROWN = '#6a3f26'
DARK_BROWN = '#3e2617'
NAVY = '#252f4a'
BRASS = '#c9973f'


# --------------------------------------------------------------------- utilidades

def stitch(d, along, width=.0007, period=.0055, duty=.25):
    """Pesponto: traço tracejado sobre a linha d=0 (d e along em metros)."""
    dash = smoothstep(duty - .12, duty + .12, np.cos(along * 2 * np.pi / period) * .5 + .5)
    return smoothstep(width * 1.6, width * .6, np.abs(d)) * dash


def leather_height(q, grain=.00005, wrinkle=.0004):
    return (fbm(q, 700, 2, 9) - .5) * grain + (fbm(q, 60, 3, 4) - .5) * wrinkle


def leather_albedo(p, hexstr, var=.12):
    base = cloth.srgb(hexstr)
    k = 1 + var * (fbm(p, 18, 3, 2) - .5) + .05 * (fbm(p, 160, 2, 7) - .5)
    return np.clip(base[None] * k[:, None], 0, 1)


def mix(a, hexstr, t):
    return cloth.lin_mix(a, cloth.srgb(hexstr), np.clip(t, 0, 1))


def brass_material(b, name='brass', rough=.32):
    return b.glb.material(name, color=(*lin(BRASS), 1), metallic=.92, roughness=rough)


def frames(path, up):
    """Referenciais por transporte paralelo ao longo do caminho."""
    T = np.gradient(path, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    N = np.zeros_like(path)
    n = np.asarray(up, float) - T[0] * (np.asarray(up, float) @ T[0])
    n /= np.linalg.norm(n)
    for i in range(len(path)):
        n = n - T[i] * (n @ T[i])
        n /= np.linalg.norm(n)
        N[i] = n
    B = np.cross(T, N)
    return T, N, B


def sweep(path, profile, up, closed=False, caps=True, scale=None, twist=None, normals=None):
    """Varre um perfil 2D fechado (M,2) ao longo do caminho. Retorna pos, nrm, uv, tris."""
    path = np.asarray(path, float)
    K, M = len(path), len(profile)
    T, N, B = frames(path, up)
    if normals is not None:
        N = normals - T * (normals * T).sum(1, keepdims=True)
        N /= np.linalg.norm(N, axis=1, keepdims=True)
        B = np.cross(T, N)
    sc = np.ones((K, 2)) if scale is None else np.broadcast_to(np.asarray(scale, float).reshape(K, -1), (K, 2))
    pos = []
    for k in range(K):
        a = 0 if twist is None else twist[k]
        n_ = N[k] * np.cos(a) + B[k] * np.sin(a)
        b_ = -N[k] * np.sin(a) + B[k] * np.cos(a)
        pr = profile * sc[k]
        pos.append(path[k] + np.outer(pr[:, 0], n_) + np.outer(pr[:, 1], b_))
    pos = np.vstack(pos)
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    per = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(np.vstack([profile, profile[:1]]), axis=0), axis=1))])
    uv = np.stack([np.tile(per[:-1], K), np.repeat(L, M)], 1)
    tris = []
    rng = K if closed else K - 1
    for k in range(rng):
        k2 = (k + 1) % K
        for i in range(M):
            j = (i + 1) % M
            a, b_, c, d = k * M + i, k * M + j, k2 * M + i, k2 * M + j
            tris += [(a, c, b_), (b_, c, d)]
    tris = np.array(tris)
    if caps and not closed:
        cap_t = []
        for k, flip in ((0, True), (K - 1, False)):
            ci = len(pos)
            pos = np.vstack([pos, path[k]])
            uv = np.vstack([uv, [0, L[k]]])
            for i in range(M):
                j = (i + 1) % M
                cap_t.append((ci, k * M + i, k * M + j) if flip else (ci, k * M + j, k * M + i))
        tris = np.vstack([tris, np.array(cap_t)])
    nrm = vertex_normals(pos, tris)
    # Orienta para fora (pelo centro do caminho).
    c = path.mean(0)
    if ((pos[:K * M] - c) * nrm[:K * M]).sum() < 0 and closed:
        tris = tris[:, ::-1]
        nrm = -nrm
    return pos, nrm, uv, tris


def rounded_rect(w, h, r, n=6):
    """Perfil de retângulo com cantos arredondados (M,2), sentido anti-horário."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n):
            a = np.radians(a0 + 90 * k / (n - 1))
            pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    return np.array(pts)


def oriented(pos, nrm, tris, center):
    """Garante normais apontando para fora de `center` (malhas convexas)."""
    if ((pos - center) * nrm).sum() < 0:
        return pos, -nrm, tris[:, ::-1]
    return pos, nrm, tris


def superbox(center, axes, half, e=4.0, seg=20, rings=14):
    """Caixa arredondada (superelipsoide) com eixos (3,3) e meias-medidas (3,)."""
    th = np.linspace(0, np.pi, rings + 1)
    ph = np.linspace(0, 2 * np.pi, seg + 1)[:-1]
    T, P = np.meshgrid(th, ph, indexing='ij')

    def sp(x):
        return np.sign(x) * np.abs(x) ** (2 / e)
    x = sp(np.sin(T)) * sp(np.cos(P))
    y = sp(np.cos(T))
    z = sp(np.sin(T)) * sp(np.sin(P))
    loc = np.stack([x, y, z], -1).reshape(-1, 3) * half
    pos = center + loc @ axes
    tris = []
    for r in range(rings):
        for s in range(seg):
            a, b = r * seg + s, r * seg + (s + 1) % seg
            c, d = a + seg, b + seg
            tris += [(a, b, c), (b, d, c)]
    tris = np.array(tris)
    nrm = vertex_normals(pos, tris)
    pos, nrm, tris = oriented(pos, nrm, tris, center)
    return pos, nrm, tris, loc / half


def gear_mesh(center, axis, r_out=.016, r_in=.0125, teeth=10, thick=.004, hole=.004):
    """Engrenagem: disco dentado extrudado com furo central."""
    axis = axis / np.linalg.norm(axis)
    ref = np.array([0, 1., 0]) if abs(axis[1]) < .9 else np.array([1., 0, 0])
    u = np.cross(axis, ref)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    n = teeth * 8
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ph = (ang * teeth / (2 * np.pi)) % 1
    tooth = smoothstep(.12, .22, ph) * (1 - smoothstep(.55, .65, ph))
    R = r_in + (r_out - r_in) * tooth
    outer = np.stack([np.cos(ang) * R, np.sin(ang) * R], 1)
    inner = np.stack([np.cos(ang) * hole, np.sin(ang) * hole], 1)
    pos, tris = [], []
    for h in (-thick / 2, thick / 2):
        for ring in (outer, inner):
            for x, y in ring:
                pos.append(center + u * x + v * y + axis * h)
    # índices: [face0 outer, face0 inner, face1 outer, face1 inner]
    o0, i0, o1, i1 = 0, n, 2 * n, 3 * n
    for k in range(n):
        j = (k + 1) % n
        tris += [(o1 + k, o1 + j, i1 + k), (o1 + j, i1 + j, i1 + k)]  # frente
        tris += [(o0 + k, i0 + k, o0 + j), (o0 + j, i0 + k, i0 + j)]  # trás
        tris += [(o0 + k, o0 + j, o1 + k), (o0 + j, o1 + j, o1 + k)]  # borda externa
        tris += [(i0 + k, i1 + k, i0 + j), (i0 + j, i1 + k, i1 + j)]  # furo
    pos, tris = np.array(pos), np.array(tris)
    # Vértices duplicados por face para arestas nítidas.
    P = pos[tris].reshape(-1, 3)
    T = np.arange(len(P)).reshape(-1, 3)
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    N = np.repeat(fn, 3, 0)
    # Orienta: faces da frente para +axis.
    front = (fn @ axis)
    if front.max() < .5:
        T = T[:, ::-1]
        N = -N
    return P, N, T


def flip_normals_out(pos, nrm, tris, center):
    return oriented(pos, nrm, tris, center)


def garment_bake(s, size=2048):
    """Como cloth.bake_surface, mas padrões calculados na posição final da peça (linhas sem serrilhado)."""
    n = G.vertex_normals_canon(s)
    part = s.part if s.part is not None else np.zeros(len(s.pos))
    t = s.tris[(part[s.tris] < 1.5).all(1)]
    return Bake(size, s.uv[t], s.pos[t], n[t], {'part': part[t][..., None].astype(np.float32)})


def mesh_bake(pos, nrm, uv, tris, size=1024, extra=None):
    ex = {k: v[tris] if v.ndim > 1 else v[tris][..., None] for k, v in (extra or {}).items()}
    return Bake(size, uv[tris], pos[tris], nrm[tris], ex)


def pack_uv(parts, pad=.01):
    """Distribui ilhas UV (cada uma com uv em metros) num atlas único, na mesma escala."""
    sizes = [(u[:, 0].max() - u[:, 0].min(), u[:, 1].max() - u[:, 1].min()) for u in parts]
    # Prateleiras simples.
    order = np.argsort([-h for _, h in sizes])
    total = sum(w * h for w, h in sizes)
    side = np.sqrt(total) * 1.25
    x = y = row_h = 0
    place = {}
    for i in order:
        w, h = sizes[i]
        if x + w > side:
            x, y, row_h = 0, y + row_h + pad, 0
        place[i] = (x, y)
        x += w + pad
        row_h = max(row_h, h)
    extent = max(side, y + row_h) + pad
    out = []
    for i, u in enumerate(parts):
        ox, oy = place[i]
        out.append(((u - u.min(0)) + [ox + pad / 2, oy + pad / 2]) / extent)
    return out, extent


# --------------------------------------------------------------------- jaqueta

_cache = {}


def jacket_surface(model, layout, A):
    key = 'jacket'
    if key in _cache:
        return _cache[key].copy()
    G.reset_strips()
    s = long_top_surface(model, layout, A, ease=.011, sleeve_ease=(.013, .026), hem=-.025, sleeve_end=.42, drape=.9, neck_up=.004)
    L = classify_loops(s)
    neck_c = A.h['Neck']
    for loop in L['hem']:
        G.band(s, loop, lambda P: np.tile([0., -1, 0], (len(P), 1)), .026, rows=3, part=1.15)
    for loop in L['sleeve']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        _, _, axis = arm_axis(A, side, upper=False)
        top = G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .018, rows=2, part=1.3, flare=.01)
        G.band(s, top, lambda P, axis=axis: np.broadcast_to(-axis, P.shape).copy(), .022, rows=3, part=1.3, flare=.002)
    for loop in L['neck']:
        def collar_dir(P):
            out = (P - neck_c) * np.array([1, 0, 1])
            out /= np.linalg.norm(out, axis=1, keepdims=True)
            return out * .55 + np.array([0, .85, 0])
        G.band(s, loop, collar_dir, .032, rows=4, part=1, flare=.006)
    G.solidify(s, .0028)
    _cache[key] = s.copy()
    return s


def wing_badge(a, b, scale=1.0):
    """Emblema alado (coordenadas locais em metros): retorna (disco, anel, asas)."""
    a, b = a / scale, b / scale
    r = np.hypot(a, b)
    disc = smoothstep(.0105, .0095, r)
    ring = smoothstep(.0012, .0005, np.abs(r - .0085))
    wings = np.zeros_like(a)
    for sgn in (1, -1):
        for i in range(4):
            cx = sgn * (.013 + i * .0062)
            cy = .002 + i * .0018 - (i * i) * .0004
            ang = sgn * (.25 + i * .18)
            x, y = a - cx, b - cy
            xr = x * np.cos(ang) + y * np.sin(ang)
            yr = -x * np.sin(ang) + y * np.cos(ang)
            e = (xr / (.0085 - i * .0012)) ** 2 + (yr / (.0034 - i * .0004)) ** 2
            wings = np.maximum(wings, smoothstep(1.1, .9, e))
    return disc, ring, wings * (1 - disc)


def top_aviator_jacket(model, layout, item_id='top_aviator_jacket'):
    A = G.Anatomy(model)
    s = jacket_surface(model, layout, A)
    b = ItemBuilder(model, item_id, 'top')
    bake = garment_bake(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    neck_y, hips_y = A.h['Neck'][1], A.h['Hips'][1]
    body = part < .5
    collar = (part > .5) & (part < 1.1)
    hemb = (part > 1.1) & (part < 1.2)
    cuff = (part > 1.2) & (part < 1.5)
    inner = part > 1.5
    front = (z > .0) & (n[:, 2] > -.2) & (np.abs(x) < .16)

    # Abertura frontal: camisa creme ao centro, colete marrom, lapela coral com pesponto.
    yy = np.clip((neck_y + .01 - y) / (neck_y - hips_y), 0, 1)
    w_open = .016 + .05 * np.sqrt(yy)
    w_shirt = w_open * .55
    ax = np.abs(x)
    shirt = body & front & (ax < w_shirt)
    vest = body & front & (ax >= w_shirt) & (ax < w_open)
    edge_d = ax - w_open
    alb = leather_albedo(p, CORAL, .1)
    alb = np.where(shirt[:, None], neutral(p, 1, .03) * cloth.srgb(CREAM), alb)
    alb = np.where(vest[:, None], leather_albedo(p, '#5a3624', .2), alb)
    # Sombra dentro da lapela e linha de pesponto na borda.
    lapel_shadow = body & front & (edge_d < 0) & (edge_d > -.006)
    alb = np.where(lapel_shadow[:, None], alb * (.55 + .45 * smoothstep(-.006, 0, edge_d))[:, None], alb)
    st = stitch(edge_d - .005, y) * body * front * (edge_d > 0)
    alb = mix(alb, '#f3d9c4', st * .9)
    # Botões da camisa e do colete.
    btn = np.zeros(len(p))
    for k in range(7):
        by = neck_y - .045 - k * .045
        btn = np.maximum(btn, smoothstep(.0042, .0032, np.hypot(x, y - by)))
        for sg in (1, -1):
            btn = np.maximum(btn, smoothstep(.0038, .0028, np.hypot(x - sg * (w_open - .009), y - by - .02)) * 2 * (vest > 0))
    btn = btn * front * body
    alb = np.where((btn > 1.1)[:, None], mix(alb, BRASS, np.clip(btn - 1, 0, 1)), mix(alb, '#d8ccb2', np.clip(btn, 0, 1)))
    # Bolsos de peito com lapela e botão.
    pocket = np.zeros(len(p))
    pocket_st = np.zeros(len(p))
    for sg in (1, -1):
        cx, cy = sg * .092, neck_y - .17
        d_box = cloth.sd_box(x, y, cx, cy, .037, .016, .004)
        flap = smoothstep(.0006, -.0006, d_box) * front * body * (ax > w_open + .01)
        pocket = np.maximum(pocket, flap)
        pocket_st = np.maximum(pocket_st, stitch(d_box + .0035, x + y) * flap)
        under = smoothstep(.006, 0, cy - .016 - y) * (y < cy - .016) * (np.abs(x - cx) < .037) * front * body
        alb = np.where(under[:, None] > 0, alb * (1 - .25 * under)[:, None], alb)
        bt = smoothstep(.0045, .0035, np.hypot(x - cx, y - (cy - .008))) * flap
        alb = mix(alb, BRASS, bt)
        pocket = np.maximum(pocket, bt * 2)
    alb = np.where((pocket > .5)[:, None] & (pocket < 1.5)[:, None], alb * .9, alb)
    alb = mix(alb, '#f3d9c4', pocket_st * .9)
    # Emblema alado na manga esquerda (lado de fora do braço).
    sh, el, axis = arm_axis(A, 'Left', upper=True)
    c0 = sh + (el - sh) * .38
    out = np.array([1., .35, 0])
    out -= axis * (out @ axis)
    out /= np.linalg.norm(out)
    side = np.cross(axis, out)
    rel = p - c0
    on = (rel @ out > 0) & (np.linalg.norm(rel - np.outer(rel @ axis, axis), axis=1) < .09) & (np.abs(rel @ axis) < .05) & body
    disc, ring, wings = wing_badge(rel @ side, -(rel @ axis), 1.15)
    badge = (disc + wings) * on
    alb = mix(alb, '#2b2f4a', disc * on)
    alb = mix(alb, '#e9c46a', (ring + wings) * on)
    # Partes: gola creme, barra canelada coral escura, punho dobrado (avesso mais claro).
    alb = np.where(collar[:, None], neutral(p, 1, .1) * cloth.srgb(CREAM) * (.92 + .08 * fbm(p, 400, 2, 5))[:, None], alb)
    alb = np.where(hemb[:, None], leather_albedo(p, '#b84a35', .06), alb)
    alb = np.where(cuff[:, None], leather_albedo(p, '#f08a6a', .08), alb)
    alb = np.where(inner[:, None], leather_albedo(p, '#8e3b2c', .05), alb)
    # Pesponto na barra das mangas e na gola.
    rough = np.where(shirt | collar, .75, .62)
    rough = np.where(btn > .5, .35, rough)
    metal = np.where((btn > 1.1) | (badge * 0 > 1), .8, 0)
    knee_like = A.h['LeftForeArm']
    trim = hemb | cuff | collar
    hfold = fabric_height(n, 'satin', .0024)
    elbow_y = A.h['LeftForeArm'][1]

    def height(q):
        h = hfold(q)
        # Franzido nos cotovelos e na cintura.
        h = h + np.exp(-((q[:, 1] - elbow_y) / .05) ** 2) * (np.abs(q[:, 0]) > .3) * np.sin(q[:, 1] * 2 * np.pi * 30 + fbm(q, 18, 2, 4) * 5) * .0014
        h = h + np.where(trim & ~collar, cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .005)) * 1.5, 0)
        h = h + np.where(collar, cloth.fleece(q, n) * 4, 0)
        qx = np.abs(q[:, 0])
        ed = qx - w_open
        h = h + np.where(body & front, smoothstep(-.001, .0015, ed) * .0011 + smoothstep(w_shirt - .001, w_shirt + .001, qx) * .0005, 0)
        h = h + pocket * .0007 + btn * .0005 - pocket_st * .00025 - st * .0002 + (wings + ring) * on * .0004
        return h
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=metal)
    mat = tex_material(b, 'jacket', a, nm, orm, sheen=((.6, .4, .35), .55))
    b.derived('jacket', s, mat)
    return b.save({'hides': ['chest', 'belly', 'upperarm_a', 'upperarm_b', 'upperarm_c', 'upperarm_d', 'forearm_a']})


# ----------------------------------------------------------------------- calça

def cargo_surface(model, layout, A, end_t=.66):
    key = 'cargo'
    if key in _cache:
        return _cache[key]
    G.reset_strips()
    c = model.coords
    top = A.h['Hips'][1] + .05

    def ok(v):
        b = A.bone[v]
        legs = np.isin(b, ('LeftUpLeg', 'RightUpLeg'))
        shin = np.isin(b, ('LeftLeg', 'RightLeg')) & (A.t[v] < end_t)
        hips = np.isin(b, ('Hips', 'Spine'))
        return ((legs | hips | shin) & (c[v, 1] < top)).all()
    s = G.surface(model, G.select(layout, ok))
    v = s.vid
    shin = np.isin(A.bone[v], ('LeftLeg', 'RightLeg'))
    thigh = np.isin(A.bone[v], ('LeftUpLeg', 'RightUpLeg'))
    t = np.clip(A.t[v], 0, 1)
    knee = .045
    # Folgada até a canela e presa (enfiada na bota) abaixo dela.
    shin_amt = knee - .004 * t / .3 - (knee - .012) * smoothstep(.28, .42, t)
    amount = np.where(shin, shin_amt, np.where(thigh, .014 + (knee - .014) * t ** .7, .011))
    G.offset(model, s, amount)
    G.smooth(s, 12, keep_boundary=True)
    kn, an = A.h['LeftLeg'][1], A.h['LeftFoot'][1]
    leg_drape(A, s, .85, .2, A.h['LeftUpLeg'][1] - .1, kn - .3 * (kn - an))
    G.smooth(s, 4, keep_boundary=True)
    G.push_out(model, s, .004)
    L = classify_loops(s)
    for loop in L['leg']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (k - a) / np.linalg.norm(k - a)
        G.straighten(s, loop, k + (a - k) * (end_t - .02), axis)
    for loop in L['hem']:
        G.straighten(s, loop, np.array([0, top, 0]), [0, 1, .12])
    G.smooth(s, 3, keep_boundary=True)
    G.push_out(model, s, .004)
    for loop in classify_loops(s)['hem']:
        G.band(s, loop, lambda P: np.tile([0., 1, 0], (len(P), 1)), .03, rows=3, part=1, inward=.001)
    # Relevo de joelheiras e bolsos laterais (geometria, antes da espessura).
    nrm = G.vertex_normals_canon(s)
    bump = np.zeros(len(s.pos))
    ref = s.ref
    for side, sg in (('Left', 1), ('Right', -1)):
        kp = A.h[f'{side}Leg']
        dx, dy = (ref[:, 0] - kp[0]) / .052, (ref[:, 1] - kp[1] - .01) / .07
        e = np.abs(dx) ** 3 + np.abs(dy) ** 3
        frontal = smoothstep(kp[2] - .01, kp[2] + .03, ref[:, 2])
        bump = np.maximum(bump, .0065 * np.sqrt(np.clip(1 - e, 0, 1)) ** .5 * frontal)
        hip = A.h[f'{side}UpLeg']
        py = hip[1] - .27
        out_side = smoothstep(.02, .05, ref[:, 0] * sg - abs(hip[0]))
        dz, dyy = (ref[:, 2] - .01) / .06, (ref[:, 1] - py) / .075
        e2 = np.abs(dz) ** 4 + np.abs(dyy) ** 4
        bump = np.maximum(bump, .006 * np.clip(1 - e2, 0, 1) ** .3 * out_side * (np.sign(ref[:, 0]) == sg))
    part = s.part if s.part is not None else np.zeros(len(s.pos))
    s.pos = s.pos + nrm * (bump * (part < .5))[:, None]
    G.smooth(s, 1, keep_boundary=True)
    G.solidify(s, .0026)
    _cache[key] = s
    return s


def leg_drape(A, s, amount=.8, slope=.22, y_top=.9, y_low=0.0):
    """Pernas largas: o tecido cai reto da coxa (não acompanha a cintura do joelho e da canela)."""
    P = s.pos
    for side, sg in (('Left', 1), ('Right', -1)):
        hip, knee, ankle = A.h[f'{side}UpLeg'], A.h[f'{side}Leg'], A.h[f'{side}Foot']
        ys = np.array([ankle[1], knee[1], hip[1]])
        cx = np.interp(P[:, 1], ys, [ankle[0], knee[0], hip[0]])
        cz = np.interp(P[:, 1], ys, [ankle[2], knee[2], hip[2]])
        m = (np.sign(P[:, 0]) == sg) & (P[:, 1] < y_top)
        rx, rz = P[:, 0] - cx, P[:, 2] - cz
        r = np.hypot(rx, rz)
        th = np.arctan2(rx * sg, rz)
        nb, dy = 36, .01
        ti = ((th + np.pi) / (2 * np.pi) * nb).astype(int) % nb
        yi = np.floor(P[:, 1] / dy).astype(int)
        y0, y1 = yi[m].min(), yi[m].max()
        R = np.zeros((y1 - y0 + 1, nb))
        np.maximum.at(R, (yi[m] - y0, ti[m]), r[m])
        env = R.copy()
        for k in range(len(R) - 2, -1, -1):
            env[k] = np.maximum(R[k], env[k + 1] - slope * dy)
        env = (np.roll(env, 1, 1) + 2 * env + np.roll(env, -1, 1)) / 4
        target = env[np.clip(yi - y0, 0, len(R) - 1), ti]
        # Lado de dentro (entre as pernas) cai menos para não colidir.
        inner = smoothstep(.3, -.6, np.sin(th))
        k = np.where(m, amount * (1 - .75 * inner) * smoothstep(y_top, y_top - .12, P[:, 1]) * smoothstep(y_low, y_low + .07, P[:, 1]), 0)
        newr = np.maximum(r, r + (target - r) * k)
        sc = np.where(r > 1e-6, newr / np.maximum(r, 1e-6), 1)
        P = np.stack([np.where(m, cx + rx * sc, P[:, 0]), P[:, 1], np.where(m, cz + rz * sc, P[:, 2])], 1)
    s.pos = P


def bottom_cargo_navy(model, layout, item_id='bottom_cargo_navy'):
    A = G.Anatomy(model)
    s = cargo_surface(model, layout, A)
    top = A.h['Hips'][1] + .05
    b = ItemBuilder(model, item_id, 'bottom')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    body = part < .5
    band = (part > .5) & (part < 1.5)
    alb = neutral(p, 1, .06) * cloth.srgb(NAVY)
    rough = np.full(len(p), .82)
    metal = np.zeros(len(p))
    raised = np.zeros(len(p))
    grooves = np.zeros(len(p))
    for side, sg in (('Left', 1), ('Right', -1)):
        m = np.sign(x) == sg
        kp = A.h[f'{side}Leg']
        hip = A.h[f'{side}UpLeg']
        # Costura lateral dupla (pesponto caramelo) no lado de fora da perna.
        ctr_x = hip[0] + (kp[0] - hip[0]) * np.clip((hip[1] - y) / (hip[1] - kp[1]), 0, 1.6)
        th = np.arctan2(z - .01, (x - ctr_x) * sg)
        dseam = th * .085
        st = (stitch(dseam - .003, y) + stitch(dseam + .003, y)) * m * body * (y < top - .03) * (y > .2)
        alb = mix(alb, '#c99a5c', st * .85)
        grooves = np.maximum(grooves, smoothstep(.0012, 0, np.abs(dseam)) * m * body)
        # Joelheira de couro com pesponto e tiras.
        dx, dy = (x - kp[0]) / .052, (y - kp[1] - .01) / .07
        e = np.abs(dx) ** 3 + np.abs(dy) ** 3
        frontal = (z > kp[2] - .005) * m * body
        pad = smoothstep(1.02, .96, e) * frontal
        pst = smoothstep(.05, .02, np.abs(e - .72)) * frontal * stitch(0, np.arctan2(dy, dx) * .05, period=.006) * 0
        ring_st = stitch((e ** (1 / 3) - .86) * .05, np.arctan2(dy, dx) * .05) * frontal
        alb = np.where(pad[:, None] > 0, cloth.lin_mix(alb, leather_albedo(p, '#6b4129', .25), pad), alb)
        alb = mix(alb, '#e5c08a', ring_st * pad)
        # Quadrados acolchoados na joelheira.
        quilt = smoothstep(.0012, .0, np.abs(x - kp[0])) + smoothstep(.0012, 0, np.abs(y - kp[1] - .01))
        grooves = np.maximum(grooves, np.clip(quilt, 0, 1) * pad * (e < .7))
        raised = np.maximum(raised, pad)
        for dy_ in (.085, -.07):
            sy = kp[1] + .01 + dy_
            strap = smoothstep(.009, .007, np.abs(y - sy)) * m * body
            alb = np.where(strap[:, None] > 0, cloth.lin_mix(alb, leather_albedo(p, DARK_BROWN, .2), strap), alb)
            alb = mix(alb, '#d8b07a', (stitch(y - sy - .006, x + z) + stitch(y - sy + .006, x + z)) * strap)
            raised = np.maximum(raised, strap * .7)
            # Fivela na lateral de fora.
            bk = cloth.sd_box(z, y, kp[2] - .0, sy, .009, .009, .002)
            fr = smoothstep(.0012, .0, np.abs(bk + .0005)) * (np.sign(x) == sg) * ((x - kp[0]) * sg > .03)
            alb = mix(alb, BRASS, fr)
            metal = np.maximum(metal, fr * .9)
            raised = np.maximum(raised, fr * 1.4)
        # Bolso cargo na lateral da coxa com lapela e botão.
        py = hip[1] - .27
        side_m = m * body * ((x * sg) > abs(hip[0]) + .03)
        dbox = cloth.sd_box(z, y, .01, py, .058, .078, .008)
        pocket = smoothstep(.0008, -.0008, dbox) * side_m
        pst = stitch(dbox + .004, z + y) * pocket
        flap_d = cloth.sd_box(z, y, .01, py + .06, .062, .024, .006)
        flap = smoothstep(.0008, -.0008, flap_d) * side_m
        fst = stitch(flap_d + .0035, z + y) * flap
        pleat = smoothstep(.0012, 0, np.abs(z - .01)) * pocket * (1 - flap)
        alb = mix(alb, '#2d3857', pocket * .6)
        shadow = smoothstep(.008, 0, (py + .036) - y) * (y < py + .036) * pocket
        alb = alb * (1 - .35 * shadow)[:, None]
        alb = mix(alb, '#2f3a5c', flap)
        alb = mix(alb, '#c99a5c', (pst + fst) * .85)
        btn = smoothstep(.0055, .0045, np.hypot(z - .01, y - (py + .047))) * flap
        alb = mix(alb, BRASS, btn)
        metal = np.maximum(metal, btn * .9)
        raised = np.maximum(raised, flap * .8 + btn)
        grooves = np.maximum(grooves, np.maximum(pleat, (pst + fst) * .3))
    # Cós com passadores e braguilha pespontada.
    loops_m = band * (np.abs(((np.arctan2(x, z - .01) / (2 * np.pi) * 9) % 1) - .5) < .07)
    alb = np.where(band[:, None], alb * .85, alb)
    alb = np.where(loops_m[:, None], alb * 1.1, alb)
    fly = body * (z > 0) * stitch(np.where(y > top - .1, x - .022, np.hypot(x, y - (top - .1)) - .022), y + x) * (y > top - .13) * (x > -.003)
    alb = mix(alb, '#c99a5c', fly * .85)
    knee_y = A.h['LeftLeg'][1]
    ankle_y = A.h['LeftFoot'][1]

    def extra(q):
        knee = np.exp(-((q[:, 1] - knee_y + .05) / .06) ** 2) * np.sin(q[:, 1] * 2 * np.pi * 28 + fbm(q, 20, 2, 3) * 4) * .0016
        bunch = smoothstep(knee_y - .1, knee_y - .2, q[:, 1]) * np.sin(q[:, 1] * 2 * np.pi * 34 + fbm(q, 25, 2, 6) * 6) * .0024
        return knee + bunch
    hfn = fabric_height(n, 'satin', .0024, extra)
    seam_c, raised_c, groove_c = grooves, raised, grooves

    def height(q):
        h = hfn(q) * (1 - .7 * raised_c)
        h = h + np.where(band, loops_m * .0012, 0)
        return h + raised_c * .0008 - groove_c * .0005 + (leather_height(q, .00006, .0) * raised_c)
    rough = np.where(raised > .5, .58, rough)
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=metal)
    mat = tex_material(b, 'cargo', a, nm, orm, sheen=((.3, .32, .4), .7))
    b.derived('cargo', s, mat)
    return b.save({'hides': ['hips', 'thigh_a', 'thigh_b', 'thigh_c', 'thigh_d', 'shin_a', 'shin_b']})


# ------------------------------------------------------------------------ botas

def boot_shell(model, layout, A, collar_t=.44):
    if 'boot' in _cache:
        return _cache['boot'].copy()
    G.reset_strips()

    def ok(v):
        b = A.bone[v]
        foot = np.isin(b, ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'))
        ankle = np.isin(b, ('LeftLeg', 'RightLeg')) & (A.t[v] > collar_t)
        return (foot | ankle).all()
    s = G.surface(model, G.select(layout, ok))
    v = s.vid
    shin = np.isin(A.bone[v], ('LeftLeg', 'RightLeg'))
    t = np.clip(A.t[v], 0, 1)
    amount = np.where(shin, .019 - .009 * smoothstep(collar_t, .9, t), .0085)
    G.offset(model, s, amount)
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
        tt = np.where(inside & np.isfinite(tt), np.minimum(tt, .035), 0)
        s.pos[m] = P + D * tt[:, None] * .9
    # Bico arredondado e alto (bota robusta): a frente é projetada num superelipsoide liso e
    # relaxada sobre ele (desfaz as dobras entre os dedos).
    c = np.array([.1, 0., .042])
    rad = np.array([.142, .056, .05])
    e_ = 2.6
    frames_ = {}
    k = np.zeros(len(s.pos))
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = np.sign(s.pos[:, 0]) == sign
        frames_[side] = (m, ankle, f, lat)
        rel = s.pos[m] - ankle
        k[m] = smoothstep(.0, .09, rel @ f) * smoothstep(.12, .07, s.pos[m, 1])

    def project():
        for side, (m, ankle, f, lat) in frames_.items():
            P = s.pos[m]
            rel = P - ankle
            loc = np.stack([rel @ f, rel @ lat, P[:, 1]], 1)
            d = (loc - c) / rad
            norm = (np.abs(d) ** e_).sum(1) ** (1 / e_)
            target = d / np.maximum(norm, 1e-6)[:, None] * rad + c
            new = loc * (1 - k[m, None]) + target * k[m, None]
            new[:, 2] = np.maximum(new[:, 2], .018)
            s.pos[m] = ankle * [1, 0, 1] + np.outer(new[:, 0], f) + np.outer(new[:, 1], lat) + np.outer(new[:, 2], [0, 1, 0])
    project()
    for _ in range(40):
        G.smooth(s, 1, lam=.6, mu=-.1, weights=k, keep_boundary=True)
        project()
    G.smooth(s, 4, keep_boundary=True)
    s.pos[:, 1] = np.maximum(s.pos[:, 1], .018)
    for loop in G.loops(s):
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (k - a) / np.linalg.norm(k - a)
        G.straighten(s, loop, s.pos[loop].mean(0), axis + np.array([0, 0, -.12]), rings=2)
    for loop in G.loops(s):
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (k - a) / np.linalg.norm(k - a)
        G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .036, rows=5, part=1, flare=.011)
    G.solidify(s, .0024)
    _cache['boot'] = s.copy()
    return s


def shoes_lace_boots(model, layout, item_id='shoes_lace_boots'):
    A = G.Anatomy(model)
    s = boot_shell(model, layout, A)
    b = ItemBuilder(model, item_id, 'shoes')
    bake = garment_bake(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    cuff = (part > .5) & (part < 1.5)
    inner = part > 1.5
    alb = leather_albedo(p, BROWN, .22)
    rough = np.full(len(p), .5)
    metal = np.zeros(len(p))
    raised = np.zeros(len(p))
    groove = np.zeros(len(p))
    lace_h = np.zeros(len(p))
    cuff_y = s.pos[s.part == 1][:, 1].min()
    hw_parts = []
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = (np.sign(p[:, 0]) == sign) & ~cuff & ~inner
        rel = p - ankle
        fw, lt, up = rel @ f, rel @ lat, p[:, 1]
        # Coordenada ao longo do cadarço: sobe pela frente da canela e desce pelo peito do pé.
        front_dir = n @ f
        on_shaft = (up > ankle[1] + .01) & (front_dir > .35)
        on_foot = (n[:, 1] > .3) & (fw > -.01) & (fw < .065) & (up < ankle[1] + .03)
        lace_zone = (on_shaft | on_foot) & (np.abs(lt) < .024) & (up < cuff_y - .004)
        q = np.where(on_shaft, up, ankle[1] + .01 - (fw - .0))
        P = .042
        ph = (q / P) % 1
        tri = np.abs(ph * 2 - 1) * 2 - 1
        w = .012
        lace = np.maximum(smoothstep(.0036, .0024, np.abs(lt - w * tri)), smoothstep(.0036, .0024, np.abs(lt + w * tri)))
        lace = lace * lace_zone * (np.abs(lt) < w + .001) * (q > ankle[1] - .085)
        tongue = smoothstep(.02, .016, np.abs(lt)) * lace_zone
        alb[m] = cloth.lin_mix(alb[m], leather_albedo(p[m], '#4a2d1b', .1), (tongue * .8)[m])
        alb[m] = cloth.lin_mix(alb[m], cloth.srgb('#d9c7a0') * (1 + .1 * np.sin(q * 900))[m, None] * 0 + cloth.srgb('#d9c7a0'), lace[m])
        lace_h[m] = lace[m]
        # Ilhoses de latão nas bordas do cadarço.
        eye = np.zeros(len(p))
        for sg in (1, -1):
            qe = np.round(q / (P / 2)) * (P / 2)
            eye = np.maximum(eye, smoothstep(.0034, .0024, np.hypot(lt - sg * (w + .0035), q - qe)) * lace_zone)
        alb[m] = cloth.lin_mix(alb[m], cloth.srgb(BRASS), eye[m])
        metal[m] = np.maximum(metal, eye)[m]
        raised[m] = np.maximum(raised, eye * 1.2)[m]
        # Pesponto ao lado do cadarço, biqueira e contraforte.
        es = (stitch(np.abs(lt) - (w + .009), q) * lace_zone)
        toe_d = fw - (.125 + .02 * (lt / .045) ** 2)
        toe = stitch(toe_d, lt + up) * (up < ankle[1] + .02)
        heel_d = fw - (-.03 - .03 * smoothstep(.04, .12, up))
        heel = stitch(heel_d, up) * (up < .13)
        st = es + toe + heel
        alb[m] = cloth.lin_mix(alb[m], cloth.srgb('#e3c792'), (st * .85)[m])
        toe_cap = smoothstep(-.002, .004, toe_d) * (up < ankle[1] + .02)
        alb[m] = (alb * (1 - .18 * toe_cap)[:, None])[m]
        groove[m] = np.maximum(groove, st * .4 + smoothstep(.0015, 0, np.abs(toe_d)) + smoothstep(.0015, 0, np.abs(heel_d)) * (up < .13))[m]
        # Tiras com fivela em volta do cano.
        for sy in (cuff_y - .03, ankle[1] + .055):
            strap = smoothstep(.0085, .0065, np.abs(up - sy - lt * .0)) * (front_dir < .35)
            alb[m] = cloth.lin_mix(alb[m], leather_albedo(p[m], DARK_BROWN, .2), strap[m])
            alb[m] = cloth.lin_mix(alb[m], cloth.srgb('#d8b07a'), ((stitch(up - sy - .0055, fw + lt) + stitch(up - sy + .0055, fw + lt)) * strap)[m])
            raised[m] = np.maximum(raised, strap * .9)[m]
            hw_parts.append((side, sign, sy))
    # Punho coral dobrado com pesponto.
    alb = np.where(cuff[:, None], leather_albedo(p, CORAL, .08), alb)
    cst = (stitch(p[:, 1] - (cuff_y + .005), p[:, 0] + p[:, 2]) + stitch(p[:, 1] - (cuff_y + .03), p[:, 0] + p[:, 2])) * cuff
    alb = mix(alb, '#fbe2cf', cst)
    alb = np.where(inner[:, None], alb * .55, alb)
    rough = np.where(cuff, .7, rough)
    lace_c, raised_c, groove_c = lace_h, raised, groove

    def height(q):
        return leather_height(q, .00006, .00012) + lace_c * .0014 + raised_c * .0009 - groove_c * .0004 + \
            np.where(cuff, cloth.triplanar(q, n, cloth.twill) * 1.4, 0)
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=metal)
    upper = tex_material(b, 'upper', a, nm, orm, clearcoat=(.35, .3))
    b.derived('upper', s, upper, weight_smooth=2)
    # Solado: entressola caramelo, sola escura separada em salto e frente (arco vazado).
    mid_mat = flat_material(b, 'welt', '#8a5a34', roughness=.55)
    out_mat = flat_material(b, 'outsole', '#2a1e18', roughness=.85)
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        pos, uv, tris, _, _ = sole_mesh(s, sign, y_bottom=-.004, y_top=.033, flare=.0068)
        b.bound(f'welt_{side}', pos, tris, uv, mid_mat, bone=f'{side}Foot')
        sel = (np.sign(s.pos[:, 0]) == sign) & (s.pos[:, 1] < .03)
        fw = (s.pos - ankle) @ f
        for nm_, cond in (('heel', fw < .0), ('front', fw > .055)):
            fake = SimpleNamespace(pos=s.pos[sel & cond])
            pos, uv, tris, _, _ = sole_mesh(fake, sign, y_bottom=-.019, y_top=-.002, flare=.0072)
            b.bound(f'{nm_}_{side}', pos, tris, uv, out_mat, bone=f'{side}Foot')
    # Fivelas de latão (lado de fora) e engrenagem no tornozelo.
    brass = brass_material(b)
    parts = {'Left': [], 'Right': []}
    nrm_s = G.vertex_normals_canon(s)
    outer_m = (s.part is not None) & (s.part < .5)
    for side, sign, sy in hw_parts:
        ankle, f, lat = foot_frame(A, side)
        outward = -lat * sign if (lat * sign)[0] < 0 else lat * sign
        outward = np.array([sign, 0, 0]) * 1.0
        m = (np.sign(s.pos[:, 0]) == sign) & outer_m & (np.abs(s.pos[:, 1] - sy) < .006)
        if not m.any():
            continue
        idx = np.flatnonzero(m)[np.argmax((s.pos[m] - ankle) @ outward)]
        c, nn = s.pos[idx], nrm_s[idx]
        frame = rounded_rect(.02, .017, .004, 4)
        path = []
        up = np.array([0, 1., 0])
        tan = np.cross(up, nn)
        tan /= np.linalg.norm(tan)
        ring = c + nn * .0022 + np.outer(frame[:, 0], tan) + np.outer(frame[:, 1], up)
        ring = np.vstack([ring, ring[:1]])
        prof = rounded_rect(.0026, .0026, .0011, 3)
        pp, pn, pu, pt = sweep(ring[:-1], prof, nn, closed=True, caps=False)
        parts[side].append((pp, pn, pt))
        prong = c + nn * .0025 + np.outer(np.linspace(-.009, .002, 6), tan)
        pp, pn, pu, pt = sweep(prong, rounded_rect(.0018, .0018, .0008, 3), nn)
        parts[side].append((pp, pn, pt))
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = (np.sign(s.pos[:, 0]) == sign) & outer_m & (np.abs(s.pos[:, 1] - (ankle[1] + .012)) < .008) & (np.abs((s.pos - ankle) @ f) < .02)
        idx = np.flatnonzero(m)[np.argmax(s.pos[m, 0] * sign)]
        c, nn = s.pos[idx], nrm_s[idx]
        gp, gn, gt = gear_mesh(c + nn * .0024, nn, .019, .0145, 10, .0042, .0045)
        parts[side].append((gp, gn, gt))
        rp, rn, rt = cylinder(c + nn * .003, nn, .0035, .004, 16)
        parts[side].append((rp, rn, rt))
        g2, n2, t2 = gear_mesh(c + nn * .0022 + np.array([0, .016, 0]) - f * .013, nn, .011, .0082, 8, .0036, .0028)
        parts[side].append((g2, n2, t2))
    for side in ('Left', 'Right'):
        if parts[side]:
            pos, nrm, tris = merge(parts[side])
            b.bound(f'hardware_{side}', pos, tris, np.zeros((len(pos), 2)), brass, nrm=nrm,
                    bone=f'{side}Leg', rigid=False)
    return b.save({'hides': ['feet', 'shin_c', 'shin_d'], 'lift': .019})


# ------------------------------------------------------------------------ luvas

def gloves_fingerless(model, layout, item_id='gloves_fingerless'):
    A = G.Anatomy(model)
    G.reset_strips()

    def ok(v):
        b = A.bone[v]
        hand = np.isin(b, ('LeftHand', 'RightHand'))
        prox = np.array(['1' in x and 'Hand' in x and 'Thumb' not in x for x in b]) & (A.t[v] < .45)
        thumb = np.array(['Thumb1' in x for x in b]) | (np.array(['Thumb2' in x for x in b]) & (A.t[v] < .4))
        wrist = np.isin(b, ('LeftForeArm', 'RightForeArm')) & (A.t[v] > .88)
        return (hand | prox | thumb | wrist).all()
    s = G.surface(model, G.select(layout, ok))
    G.offset(model, s, .0016)
    G.smooth(s, 2, keep_boundary=True)
    for loop in G.loops(s):
        c = s.pos[loop].mean(0)
        if len(loop) > 40:
            side = 'Left' if c[0] > 0 else 'Right'
            a, f = A.h[f'{side}ForeArm'], A.h[f'{side}Hand']
            axis = (f - a) / np.linalg.norm(f - a)
            G.straighten(s, loop, c, axis, rings=1)
            G.band(s, loop, lambda P, axis=axis: np.broadcast_to(-axis, P.shape).copy(), .022, rows=3, part=1, flare=.0035)
        else:
            G.smooth_loop(s, loop, 10, 1)
    G.push_out(model, s, .0012, smooth_body=False)
    G.solidify(s, .0013)
    b = ItemBuilder(model, item_id, 'hands')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    cuff = (part > .5) & (part < 1.5)
    alb = leather_albedo(p, '#5b3622', .25)
    raised = np.zeros(len(p))
    groove = np.zeros(len(p))
    metal = np.zeros(len(p))
    for side, sg in (('Left', 1), ('Right', -1)):
        m = np.sign(p[:, 0]) == sg
        h0, k1 = A.h[f'{side}Hand'], A.h[f'{side}HandMiddle1']
        axis = (k1 - h0) / np.linalg.norm(k1 - h0)
        hv = model.coords[A.bone == f'{side}Hand']
        cc = hv.mean(0)
        _, _, vt = np.linalg.svd(hv - cc)
        back = vt[2] if vt[2] @ (A.h[f'{side}HandThumb2'] - cc) < 0 else -vt[2]
        rel = p - cc
        along = rel @ axis
        dorsal = (n @ back > .3) & m & ~cuff
        # Reforço acolchoado sobre os nós dos dedos com pesponto.
        kn = smoothstep(.006, .0, np.abs(along - .035)) * dorsal
        pad = (along > .018) & (along < .052) & dorsal
        alb = np.where(pad[:, None], alb * .78, alb)
        latd = rel @ np.cross(axis, back)
        st = (stitch(along - .019, latd) + stitch(along - .051, latd)) * dorsal
        alb = mix(alb, '#e2c08c', st * .85)
        raised = np.maximum(raised, pad * 1.0)
        groove = np.maximum(groove, smoothstep(.001, 0, np.abs(along - .035)) * pad + st * .3)
    # Tira do punho com rebite.
    alb = np.where(cuff[:, None], leather_albedo(p, '#3e2617', .2), alb)
    rough = np.where(cuff, .55, .5)

    def height(q):
        return leather_height(q, .00007, .0003) + raised * .0008 - groove * .0004 + np.where(cuff, cloth.triplanar(q, n, cloth.twill), 0)
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=metal)
    mat = tex_material(b, 'gloves', a, nm, orm, clearcoat=(.25, .4))
    b.derived('gloves', s, mat, weight_smooth=0)
    # Rebites de latão no punho (lado de fora do pulso).
    brass = brass_material(b)
    for side, sg in (('Left', 1), ('Right', -1)):
        cm = (s.part == 1) & (np.sign(s.pos[:, 0]) == sg)
        nrm_s = G.vertex_normals_canon(s)
        P = s.pos[cm]
        hv = model.coords[A.bone == f'{side}Hand']
        cc = hv.mean(0)
        _, _, vt = np.linalg.svd(hv - cc)
        back = vt[2] if vt[2] @ (A.h[f'{side}HandThumb2'] - cc) < 0 else -vt[2]
        idx = np.flatnonzero(cm)[np.argmax((P - P.mean(0)) @ back)]
        rp, rn, rt = cylinder(s.pos[idx] - nrm_s[idx] * .0005, nrm_s[idx], .0042, .0028, 16)
        b.bound(f'rivet_{side}', rp, rt, np.zeros((len(rp), 2)), brass, nrm=rn, bone=f'{side}Hand', rigid=True)
    return b.save({})


def register(item):
    item('top_aviator_jacket', 'top')(top_aviator_jacket)
    item('bottom_cargo_navy', 'bottom')(bottom_cargo_navy)
    item('shoes_lace_boots', 'shoes')(shoes_lace_boots)
    item('gloves_fingerless', 'hands')(gloves_fingerless)
