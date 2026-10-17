"""Coleção estilizada: volt (Cientista Voltaico). Registra as peças no REGISTRY de build_items.

Cabelo azul espetado para trás, jaleco longo aberto com gola alta e frisos dourados,
ombreira mecânica, calça cargo escura, botas de fivelas, cinto do raio e braço mecânico
com tubos de vidro azul brilhante.
"""
from __future__ import annotations

import numpy as np

import cloth
import garments as G
import hair
import hair_styled as H
import hair_styles as HS
from accessories import cylinder, merge, torus
from garments import Surface
from items import ItemBuilder
from model import vertex_normals
from raster import fbm, smoothstep
from wardrobe import classify_loops, foot_frame, sole_mesh
from wardrobe2 import (flat_material, hull_fill, lin, long_top_surface, neutral, pants_surface, sphere_mesh,
                       tex_material)

WHITE = '#eeece6'
SHIRT = '#262a35'
GOLD = '#e0b85c'
BRASS = '#c7973f'
BRONZE = '#8a5a2b'
LEATHER = '#141418'
GLOW = (.25, .62, 1.0)


# ------------------------------------------------------------------ utilidades de malha

def basis(axis):
    axis = axis / np.linalg.norm(axis)
    ref = np.array([1., 0, 0]) if abs(axis[0]) < .9 else np.array([0, 0, 1.])
    u = ref - axis * (axis @ ref)
    u /= np.linalg.norm(u)
    return axis, u, np.cross(axis, u)


def profile(P, center, axis, u, v, n=48, slab=.012, pct=100):
    """Raio da seção transversal de uma nuvem de pontos ao redor de um eixo (por ângulo)."""
    rel = P - center
    h = rel @ axis
    m = np.abs(h) < slab
    rel = rel[m] - np.outer(h[m], axis)
    ang = np.arctan2(rel @ v, rel @ u)
    rad = np.linalg.norm(rel, axis=1)
    bins = ((ang + np.pi) / (2 * np.pi) * n).astype(int) % n
    out = np.full(n, np.nan)
    for k in range(n):
        sel = rad[bins == k]
        if len(sel):
            out[k] = np.percentile(sel, pct)
    ok = ~np.isnan(out)
    if not ok.any():
        return np.full(n, .03)
    idx = np.arange(n)
    out = np.interp(idx, np.concatenate([idx[ok] - n, idx[ok], idx[ok] + n]), np.tile(out[ok], 3))
    for _ in range(2):
        out = np.maximum(out, (np.roll(out, 1) + 2 * out + np.roll(out, -1)) / 4)
    return out


def ring_band(center, axis, u, v, radii, height, thick, bevel=.0008):
    """Anel (cinto, tira, aro) seguindo um raio por ângulo; seção retangular chanfrada."""
    n = len(radii)
    hh = height / 2
    sec = [(-hh, -.0004), (-hh, thick - bevel), (-hh + bevel, thick), (hh - bevel, thick), (hh, thick - bevel), (hh, -.0004)]
    pos = []
    for j in range(n):
        a = 2 * np.pi * j / n - np.pi
        d = np.cos(a) * u + np.sin(a) * v
        for h, dr in sec:
            pos.append(center + axis * h + d * (radii[j] + dr))
    m = len(sec)
    tris = []
    for j in range(n):
        for k in range(m):
            a, b = j * m + k, j * m + (k + 1) % m
            c, d = ((j + 1) % n) * m + k, ((j + 1) % n) * m + (k + 1) % m
            tris += [(a, c, b), (b, c, d)]
    pos = np.array(pos)
    tris = np.array(tris)
    nrm = vertex_normals(pos, tris)
    if ((pos - center) * nrm).sum() < 0:
        tris = tris[:, ::-1]
        nrm = -nrm
    return pos, nrm, tris


def box(center, ax, ay, az, sx, sy, sz):
    """Caixa orientada (faces com normais próprias)."""
    pos, nrm, tris = [], [], []
    axes = [np.asarray(ax, float), np.asarray(ay, float), np.asarray(az, float)]
    size = [sx, sy, sz]
    for i in range(3):
        for sgn in (-1, 1):
            nvec = axes[i] * sgn
            a1, a2 = axes[(i + 1) % 3], axes[(i + 2) % 3]
            s1, s2 = size[(i + 1) % 3], size[(i + 2) % 3]
            base = len(pos)
            c = center + nvec * size[i]
            for d1, d2 in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                pos.append(c + a1 * s1 * d1 + a2 * s2 * d2)
                nrm.append(nvec)
            t = [(base, base + 1, base + 2), (base, base + 2, base + 3)]
            if sgn < 0:
                t = [(a, c_, b) for a, b, c_ in t]
            tris += t
    pos, nrm, tris = np.array(pos), np.array(nrm), np.array(tris)
    fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
    bad = (fn * nrm[tris[:, 0]]).sum(1) < 0
    tris[bad] = tris[bad][:, ::-1]
    return pos, nrm, tris


def ear_clip(poly):
    """Triangula um polígono simples (anti-horário)."""
    idx = list(range(len(poly)))
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    guard = 0
    while len(idx) > 3 and guard < 500:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if cross(a, b, c) <= 0:
                continue
            inside = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = poly[j]
                if cross(a, b, p) > 0 and cross(b, c, p) > 0 and cross(c, a, p) > 0:
                    inside = True
                    break
            if not inside:
                tris.append((i0, i1, i2))
                idx.pop(k)
                break
    tris.append(tuple(idx))
    return tris


def extrude(poly, origin, ex, ey, ez, depth):
    """Prisma de um polígono 2D (ex, ey no plano; ez para fora)."""
    poly = np.asarray(poly, float)
    if sum(poly[i - 1, 0] * poly[i, 1] - poly[i, 0] * poly[i - 1, 1] for i in range(len(poly))) < 0:
        poly = poly[::-1]
    cap = ear_clip(poly)
    n = len(poly)
    pos, nrm, tris = [], [], []
    for z, sgn in ((depth, 1), (0, -1)):
        base = len(pos)
        for x, y in poly:
            pos.append(origin + ex * x + ey * y + ez * z)
            nrm.append(ez * sgn)
        tris += [(base + a, base + b, base + c) if sgn > 0 else (base + a, base + c, base + b) for a, b, c in cap]
    for i in range(n):
        p0, p1 = poly[i], poly[(i + 1) % n]
        e = p1 - p0
        out = np.array([e[1], -e[0]]) / (np.linalg.norm(e) + 1e-12)
        nv = ex * out[0] + ey * out[1]
        base = len(pos)
        for (x, y), z in ((p0, 0), (p1, 0), (p1, depth), (p0, depth)):
            pos.append(origin + ex * x + ey * y + ez * z)
            nrm.append(nv)
        tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    pos, nrm, tris = np.array(pos), np.array(nrm), np.array(tris)
    fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
    bad = (fn * nrm[tris[:, 0]]).sum(1) < 0
    tris[bad] = tris[bad][:, ::-1]
    return pos, nrm, tris


def emit_parts(b, name, parts, mat, bone=None, rigid=False):
    pos, nrm, tris = merge(parts)
    b.bound(name, pos, tris, np.zeros((len(pos), 2)), mat, nrm=nrm, bone=bone, rigid=rigid)


def metal(b, name, hexstr, roughness=.32, metallic=1.0, clearcoat=None):
    return b.glb.material(name, color=(*lin(hexstr), 1), metallic=metallic, roughness=roughness, clearcoat=clearcoat)


def pbr(b, name, alb, nrm, orm, sheen=None, clearcoat=None):
    """Material com metal no canal B do ORM (tecido + frisos metálicos na mesma textura)."""
    return b.glb.material(name, color=(1, 1, 1, 1), metallic=1.0, roughness=1.0,
                          base=b.glb.texture(alb, fmt='jpeg', quality=88), normal=b.glb.texture(nrm, fmt='webp', quality=88),
                          orm=b.glb.texture(orm, fmt='jpeg', quality=84), sheen=sheen, clearcoat=clearcoat)


def emit_custom(b, name, s, mat, W, model, normals=None):
    """Superfície com pesos próprios e morphs transferidos pela superfície do corpo mais próxima."""
    ids, bary, _ = model.bind(s.pos)
    morphs = {k: v for k, v in model.bound_morphs(ids, bary).items() if not k.startswith('expr_') and np.abs(v).max() > 5e-4}
    n = G.vertex_normals_canon(s) if normals is None else normals
    b._emit(name, s.pos, n, s.uv, s.tris, mat, W, morphs)


def grid_surface(P, closed_u=False):
    """Superfície (rows, cols) -> Surface com UV própria [0,1]."""
    R, C = P.shape[:2]
    pos = P.reshape(-1, 3)
    uu, vv = np.meshgrid(np.linspace(0, 1, C), np.linspace(0, 1, R))
    uv = np.stack([uu.ravel(), vv.ravel()], 1)
    tris = []
    for r in range(R - 1):
        for c in range(C - 1 + (1 if closed_u else 0)):
            a, b_ = r * C + c, r * C + (c + 1) % C
            tris += [(a, a + C, b_), (b_, a + C, b_ + C)]
    return Surface(pos.copy(), np.zeros(len(pos), int), uv, np.array(tris), pos.copy(), np.zeros(len(pos), int))


# ------------------------------------------------------------------ cabelo

def spiky_hair(model, layout, item_id='hair_spiky'):
    rng = np.random.default_rng(7)
    vol = H.HeadVolume(model)
    L = vol.L
    c, r = vol.center, vol.radii
    b = HS.scalp_base(model, layout, item_id)
    mat = HS.styled_material(b, 'hair', .4, tips=True)

    # Calota penteada para trás e para cima (base das mechas).
    P, N, az = H.roots(model, .0125, lambda P, N, aaz: P[:, 1] > hair.scalp_line(L, aaz) + .002)
    crown = c + np.array([0, r[1] * .8, -r[2] * .45])
    paths, widths = [], []
    for p in P:
        d = (p - c) / r
        tgt = c + r * (d * .35 + (crown - c) / r * .65 + rng.normal(0, .05, 3))
        paths.append(H.cap_path(vol, p, tgt, 12, lift=(.004, .011 + rng.uniform(0, .005))))
        widths.append(H.taper(12, rng.uniform(.02, .026), .6, .5))
    HS.emit(b, 'cap', mat, paths, widths, vol, tip_scale=.2)

    # Espetos largos varridos para trás e para cima (como uma chama).
    paths, widths = [], []

    def spike(el, azd, length, width, sweep=1.0, lift=.0, seed=0):
        e, a = np.radians(el), np.radians(azd)
        u = np.array([np.cos(e) * np.sin(a), np.sin(e), np.cos(e) * np.cos(a)])
        root = c + u * r * .97
        nrm = u / r
        nrm /= np.linalg.norm(nrm)
        d = nrm * .4 + np.array([0, .45 + lift, -1.0]) * sweep
        path = H.free_path(vol, root, d, length, 14, gravity=-.35, stiff=.95, wave=(.0, 1, 0), margin=.006, seed=seed)
        paths.append(path)
        widths.append(H.taper(14, width, .06, .05))

    k = 0
    for el, count, a0, a1, ln, wd in ((12, 13, -165, 165, (.08, .11), (.04, .05)),
                                      (32, 12, -150, 150, (.1, .14), (.045, .056)),
                                      (52, 9, -130, 130, (.11, .15), (.05, .06)),
                                      (72, 5, -100, 100, (.11, .14), (.05, .06))):
        for i in range(count):
            a = a0 + (a1 - a0) * (i + .5 * (el % 2)) / count + rng.uniform(-6, 6)
            if el < 30 and abs(a) < 70:
                continue  # rosto: sem espetos baixos na frente
            spike(el + rng.uniform(-4, 4), a, rng.uniform(*ln), rng.uniform(*wd), seed=k)
            k += 1
    # Topete: mechas que sobem da testa e viram para trás.
    for i in range(6):
        a = -40 + 80 * i / 5 + rng.uniform(-5, 5)
        spike(40 + rng.uniform(-3, 3), a, rng.uniform(.12, .16), rng.uniform(.05, .062), sweep=.8, lift=.8, seed=100 + i)
    HS.emit(b, 'spikes', mat, paths, widths, vol, tip_scale=1, flat=.5)

    # Costeletas: descem rentes à têmpora, na frente da orelha.
    paths, widths = [], []
    rel = P - L.center
    azs = np.degrees(np.arctan2(rel[:, 0], rel[:, 2]))
    for side in (1, -1):
        cand = np.flatnonzero((np.abs(azs) > 74) & (np.abs(azs) < 92) & (np.sign(rel[:, 0]) == side))
        for i in cand[np.argsort(P[cand, 1])][:3]:
            p = P[i]
            tgt = p + np.array([0, -.04, .004])
            tgt = vol.push_out(tgt[None], .0)[0]
            paths.append(H.cap_path(vol, p, tgt, 10, lift=(.003, .005)))
            widths.append(H.taper(10, .017, .25, .3))
    HS.emit(b, 'sideburns', mat, paths, widths, vol, tip_scale=.3)
    return b.save({})


# ------------------------------------------------------------------ jaleco

def lab_coat(model, layout, item_id='top_lab_coat'):
    A = G.Anatomy(model)
    G.reset_strips()
    hips_y, neck_y = A.h['Hips'][1], A.h['Neck'][1]
    s = long_top_surface(model, layout, A, ease=.012, sleeve_ease=(.013, .02), hem=.03, sleeve_end=.9)
    loops0 = classify_loops(s)
    hem_loop = max(loops0['hem'], key=len)
    neck_loop = max(loops0['neck'], key=len)
    hem_pts = s.pos[hem_loop].copy()
    neck_pts = s.pos[neck_loop].copy()
    neck_vid = s.vid[neck_loop].copy()

    # Abertura frontal: a camisa escura fica rente ao corpo; abaixo do cinto entra na calça.
    def open_w(y):
        return np.interp(y, [hips_y - .06, 1.15, 1.4, neck_y + .04], [.08, .066, .05, .03])
    ref = s.ref
    nn = G.vertex_normals_canon(s)
    torso = np.abs(ref[:, 0]) < .14
    front = torso & (nn[:, 2] > .15) & (ref[:, 2] > -.02)
    k = front * smoothstep(open_w(ref[:, 1]) + .009, open_w(ref[:, 1]), np.abs(ref[:, 0]))
    ids, bary, off = model.bind(s.pos, coords=model.smoothed())
    n = (model.normals[ids] * bary[..., None]).sum(1)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    d = (off * n).sum(1)
    cut = hips_y + .045
    target = np.where(ref[:, 1] > cut, .0055, -.012)
    s.pos = s.pos - n * ((d - target) * k)[:, None]

    L = classify_loops(s)
    for loop in L['sleeve']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        a, f = A.h[f'{side}ForeArm'], A.h[f'{side}Hand']
        axis = (f - a) / np.linalg.norm(f - a)
        G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .03, rows=3, part=1, inward=.002, flare=.002)
    G.solidify(s, .0028)

    b = ItemBuilder(model, item_id, 'top')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    nb = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    ax = np.abs(x)
    w = open_w(y)
    fr = (nb[:, 2] > .15) & (ax < .14) & (z > -.02) & (part < .5)
    shirt = fr & (ax < w)
    edge = fr & (ax >= w) & (ax < w + .011)
    pin = fr & (np.abs(ax - (w + .019)) < .0016) & (y < neck_y - .01)
    plates = fr & (np.abs(ax - (w + .034)) < .009) & (((y > 1.27) & (y < 1.3)) | ((y > 1.32) & (y < 1.35)))
    cuff = part > .5
    gold = edge | pin | plates | (cuff & (part < 1.5))
    alb = neutral(p, .9, .05)
    alb = np.where(shirt[:, None], neutral(p, 1, .1) * cloth.srgb(SHIRT), alb)
    btn_y = np.arange(neck_y - .07, cut, -.055)
    btn = np.zeros(len(p))
    for by in btn_y:
        btn = np.maximum(btn, smoothstep(.0062, .0045, np.hypot(x, y - by)) * shirt)
    alb = cloth.lin_mix(alb, cloth.srgb('#111217'), btn)
    alb = np.where(gold[:, None], cloth.srgb(GOLD) * (.9 + .2 * fbm(p, 300, 2, 4)[:, None]), alb)
    alb = np.where((part > 1.5)[:, None], alb * .78, alb)
    rough = np.where(gold, .3, np.where(shirt, .7, .78))
    rough = np.where(btn > .5, .3, rough)
    met = gold.astype(float)
    hfn = cloth.triplanar

    def height(q):
        base = cloth.triplanar(q, nb, cloth.twill) * .8 + (fbm(q, 38, 3, 11) - .5) * .0016
        bump = btn * .0012 + np.where(edge, .0006, 0) + np.where(plates, .0007, 0)
        seam = -smoothstep(.0012, .0004, np.abs(ax - (w + .0115))) * fr * .0005
        return base + bump + seam
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=met)
    mat = pbr(b, 'coat', a, nm, orm, sheen=((.3, .3, .32), .6))
    b.derived('coat', s, mat)

    _coat_collar(b, model, A, neck_pts, neck_vid)
    _coat_skirt(b, model, A, hem_pts, open_w(hips_y - .02))
    _pauldron(b, model, A, s)
    return b.save({'hides': ['chest', 'belly', 'upperarm_a', 'upperarm_b', 'upperarm_c', 'upperarm_d', 'forearm_a', 'forearm_b', 'forearm_c']})


def _sorted_by_angle(P, center_xz):
    th = np.arctan2(P[:, 0] - center_xz[0], P[:, 2] - center_xz[1])
    o = np.argsort(th)
    return th[o], P[o], o


def _trim_texture(b, name, s, eu, ev, edge_u=.011, edge_v=.012, plates=None, size=1024, sheen=True):
    """Textura de tecido branco com frisos dourados nas bordas (eu: dist. da borda livre, ev: da barra)."""
    bake = cloth.bake_surface(s, size, extra={'eu': eu, 'ev': ev})
    p = bake.pos[bake.mask].astype(np.float64)
    nb = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    du, dv = bake.at('eu')[:, 0], bake.at('ev')[:, 0]
    gold = (du < edge_u) | (dv < edge_v) | (np.abs(du - edge_u - .008) < .0016) | (np.abs(dv - edge_v - .009) < .0016)
    if plates is not None:
        gold |= plates(du, dv)
    alb = neutral(p, .9, .05)
    alb = np.where(gold[:, None], cloth.srgb(GOLD) * (.9 + .2 * fbm(p, 300, 2, 4)[:, None]), alb)
    alb = np.where((part > 1.5)[:, None], alb * .78, alb)
    rough = np.where(gold, .3, .78)

    def height(q):
        return cloth.triplanar(q, nb, cloth.twill) * .8 + (fbm(q, 30, 3, 5) - .5) * .0014 + gold * .0005
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=gold.astype(float))
    return pbr(b, name, a, nm, orm, sheen=((.3, .3, .32), .6) if sheen else None)


def _coat_collar(b, model, A, neck_pts, neck_vid):
    """Gola alta levantada, aberta na frente, com friso dourado."""
    nc = neck_pts.mean(0)
    th, P, o = _sorted_by_angle(neck_pts, (nc[0], nc[2]))
    vid = neck_vid[o]
    th0 = np.radians(36)
    cols = 64
    tq = np.linspace(th0, 2 * np.pi - th0, cols)
    tq = np.where(tq > np.pi, tq - 2 * np.pi, tq)
    thx = np.concatenate([th - 2 * np.pi, th, th + 2 * np.pi])
    base = np.stack([np.interp(tq, thx, np.tile(P[:, i], 3)) for i in range(3)], 1)
    vids = vid[np.clip(np.searchsorted(th, tq), 0, len(th) - 1)]
    rows = 7
    back = np.abs(np.cos(tq / 2))  # 1 na frente ... 0 atrás (tq em [-pi, pi])
    Hc = .085 - .035 * back ** 2
    radial = base - np.array([nc[0], base[:, 1].mean(), nc[2]])
    radial[:, 1] = 0
    radial /= np.linalg.norm(radial, axis=1, keepdims=True)
    grid = []
    for r_ in range(rows):
        f = r_ / (rows - 1)
        grid.append(base - radial * .002 + np.array([0, 1, 0]) * (Hc * f)[:, None] + radial * (.04 * f ** 1.5 + .004 * f))
    grid = np.array(grid)
    # Pontas da gola: o canto superior da frente avança para fora.
    s = grid_surface(grid)
    s.vid = np.tile(vids, rows)
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(grid[-1], axis=0), axis=1))])
    eu = np.tile(np.minimum(arc, arc[-1] - arc), rows) * .6
    ev = np.repeat((1 - np.linspace(0, 1, rows)), cols) * Hc.max()
    eu = np.minimum(eu, np.repeat(np.linspace(0, 1, rows), cols) * 0 + 1)
    G.smooth(s, 2, keep_boundary=True)
    G.solidify(s, .003)
    n0 = len(eu)
    eu = np.concatenate([eu, eu])
    ev = np.concatenate([ev, ev])
    mat = _trim_texture(b, 'collar', s, eu, ev, edge_u=.008, edge_v=.009, size=512)
    b.derived('collar', s, mat, weight_smooth=2)


def _coat_skirt(b, model, A, hem_pts, w_hem):
    """Aba longa do jaleco até perto dos joelhos, aberta na frente, com caimento e frisos."""
    hips_y = A.h['Hips'][1]
    cz = (hem_pts[:, 2].max() + hem_pts[:, 2].min()) / 2
    th, P, _ = _sorted_by_angle(hem_pts, (0, cz))
    rh = np.hypot(P[:, 0], P[:, 2] - cz)
    thx = np.concatenate([th - 2 * np.pi, th, th + 2 * np.pi])
    rhx = np.tile(rh, 3)
    hem_y = P[:, 1].mean()
    # Envelope das pernas (com folga da calça) por altura e ângulo.
    legs = np.isin(A.bone, ('Hips', 'LeftUpLeg', 'RightUpLeg', 'LeftLeg', 'RightLeg'))
    Q = model.coords[legs]
    qth = np.arctan2(Q[:, 0], Q[:, 2] - cz)
    qr = np.hypot(Q[:, 0], Q[:, 2] - cz)
    nbt, dy = 72, .02
    y_lo = .4
    env = np.zeros((int((hem_y + .05 - y_lo) / dy) + 2, nbt))
    ti = ((qth + np.pi) / (2 * np.pi) * nbt).astype(int) % nbt
    yi = np.clip(((Q[:, 1] - y_lo) / dy).astype(int), 0, len(env) - 1)
    np.maximum.at(env, (yi, ti), qr)
    for _ in range(3):
        env = np.maximum(env, np.maximum(np.roll(env, 1, 1), np.roll(env, -1, 1)))
    env = np.maximum(env, np.roll(env, 1, 0))
    env = np.maximum(env, np.roll(env, -1, 0))
    th0_top = np.arctan2(w_hem + .004, rh[np.argmin(np.abs(th))]) + .02
    th0_bot = np.radians(40)
    rows, cols = 26, 81
    y_top = hem_y + .022
    grid, EU, EV = [], [], []
    rng = np.random.default_rng(5)
    phase = rng.uniform(0, 6, 4)
    prev = None
    for r_ in range(rows):
        f = r_ / (rows - 1)
        th0 = th0_top + (th0_bot - th0_top) * smoothstep(0, 1, f) ** .8
        tq = np.linspace(th0, 2 * np.pi - th0, cols)
        tq = np.where(tq > np.pi, tq - 2 * np.pi, tq)
        y_bot = .5 + .02 * np.cos(tq)
        yy = y_top + (y_bot - y_top) * f
        base_r = np.interp(tq, thx, rhx) - .004
        ti = ((tq + np.pi) / (2 * np.pi) * nbt).astype(int) % nbt
        yi = np.clip(((yy - y_lo) / dy).astype(int), 0, len(env) - 1)
        need = env[yi, ti] + .048
        flare = base_r * (1 + .2 * f ** 1.3)
        rr = base_r + (np.maximum(flare, need) - base_r) * smoothstep(0, .3, f)
        if prev is not None:
            rr = np.maximum(rr, prev)
        prev = rr
        folds = (np.sin(tq * 9 + phase[0]) * .6 + np.sin(tq * 5 + phase[1]) * .4) * .007 * f ** 1.2
        rr = rr + folds
        grid.append(np.stack([np.sin(tq) * rr, yy, cz + np.cos(tq) * rr], 1))
    grid = np.array(grid)
    s = grid_surface(grid)
    # Distâncias às bordas livres (frente) e à barra, para os frisos.
    arc = np.concatenate([np.zeros((rows, 1)), np.cumsum(np.linalg.norm(np.diff(grid, axis=1), axis=2), axis=1)], 1)
    eu = np.minimum(arc, arc[:, -1:] - arc).ravel()
    down = np.concatenate([np.zeros((1, cols)), np.cumsum(np.linalg.norm(np.diff(grid, axis=0), axis=2), axis=0)], 0)
    ev = (down[-1:] - down).ravel()
    ev = np.where(down.ravel() < .02, np.maximum(ev, 1), ev)
    G.solidify(s, .003)
    eu, ev = np.concatenate([eu, eu]), np.concatenate([ev, ev])
    # Pesos: quadril em cima; embaixo segue em parte a coxa do mesmo lado.
    pos = s.pos
    f = np.clip((y_top - pos[:, 1]) / (y_top - .5), 0, 1)
    kleg = .5 * f ** 1.2
    wl = np.clip(.5 + pos[:, 0] / .1, 0, 1)
    W = np.zeros((len(pos), len(model.bone_names)), np.float32)
    W[:, model.bone_index('Hips')] = 1 - kleg
    W[:, model.bone_index('LeftUpLeg')] = kleg * wl
    W[:, model.bone_index('RightUpLeg')] = kleg * (1 - wl)

    def plates(du, dv):
        return (du > .03) & (du < .05) & (((dv > .045) & (dv < .085)) | ((dv > .1) & (dv < .14)))
    mat = _trim_texture(b, 'skirt', s, eu, ev, plates=plates)
    emit_custom(b, 'skirt', s, mat, W, model)


def _pauldron(b, model, A, coat):
    """Ombreira mecânica em lâminas de latão sobre o ombro direito."""
    C = A.h['RightArm'] + np.array([.01, -.005, 0])
    U = np.array([-.72, .69, -.04])
    U /= np.linalg.norm(U)
    outer = coat.pos[coat.part < 1.5] if coat.part is not None else coat.pos
    rel = outer - C
    dist = np.linalg.norm(rel, axis=1)
    dirs = rel / dist[:, None]
    from scipy.spatial import cKDTree
    tree = cKDTree(dirs)
    _, e1, e2 = basis(U)
    brass = metal(b, 'brass', BRASS, .3)
    bronze = metal(b, 'bronze', BRONZE, .38)
    plates = ((0, 32, .017, brass), (26, 46, .012, bronze), (40, 60, .007, brass))
    rivets = []
    for i, (a0, a1, margin, mat) in enumerate(plates):
        nr, nc_ = 7, 44
        grid = []
        for ri in range(nr):
            al = np.radians(a0 + (a1 - a0) * ri / (nr - 1))
            row = []
            for ci in range(nc_):
                be = 2 * np.pi * ci / nc_
                d = np.cos(al) * U + np.sin(al) * (np.cos(be) * e1 + np.sin(be) * e2)
                nb_ = tree.query_ball_point(d, .16)
                near = dist[nb_][dist[nb_] < .13] if len(nb_) else []
                R = near.max() if len(near) else .07
                row.append(C + d * (R + margin))
            grid.append(row)
        grid = np.array(grid)
        # Suaviza o raio (lâmina lisa) e fecha a calota no topo.
        for _ in range(3):
            grid[1:-1] = .5 * grid[1:-1] + .25 * (grid[:-2] + grid[2:])
            grid = .5 * grid + .25 * (np.roll(grid, 1, 1) + np.roll(grid, -1, 1))
        s = grid_surface(grid, closed_u=True)
        G.solidify(s, .0028)
        tris = s.tris
        b.bound(f'pauldron_{i}', s.pos, tris, np.zeros((len(s.pos), 2)), mat, nrm=G.vertex_normals_canon(s))
        # Rebites ao longo da borda inferior.
        for ci in range(0, nc_, 4):
            pnt = grid[-2, ci]
            nrm_ = pnt - C
            nrm_ /= np.linalg.norm(nrm_)
            rivets.append(sphere_mesh(pnt + nrm_ * .0015, .0028, 8, 6))
    emit_parts(b, 'rivets', rivets, brass)


# ------------------------------------------------------------------ calça cargo

PANTS = dict(end_t=.9, ease_hip=.009, ease_knee=.03, ease_ankle=.016)


def cargo_pants(model, layout, item_id='bottom_cargo_dark'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, top = pants_surface(model, layout, A, **PANTS)
    knee_y = A.h['LeftLeg'][1]
    hip_x = abs(A.h['LeftUpLeg'][0])

    def pocket_mask(P, nrm, grow=0.0):
        side = np.sign(P[:, 0])
        lateral = np.abs(P[:, 0]) > hip_x - .02
        y0, y1 = knee_y + .1, knee_y + .25
        out = nrm[:, 0] * side
        return (lateral * smoothstep(y0 - grow - .008, y0 - grow, P[:, 1]) * smoothstep(y1 + grow + .008, y1 + grow, P[:, 1])
                * smoothstep(.35, .6, out))
    nn = G.vertex_normals_canon(s)
    G.offset(model, s, .007 * pocket_mask(s.ref, nn))
    L = classify_loops(s)
    for loop in L['hem']:
        G.band(s, loop, lambda P: np.tile([0., 1, 0], (len(P), 1)), .032, rows=3, part=1, inward=.001)
    for loop in L['leg']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (a - k) / np.linalg.norm(a - k)
        G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .025, rows=2, part=1, inward=.003)
    G.solidify(s, .0026)
    b = ItemBuilder(model, item_id, 'bottom')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    nb = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    pm = pocket_mask(p, nb)
    flap = pocket_mask(p, nb) * smoothstep(knee_y + .21, knee_y + .215, p[:, 1])
    edge = pocket_mask(p, nb, .006) - pm
    alb = neutral(p, .9, .06)
    alb = np.where((part > .5)[:, None] & (part < 1.5)[:, None], alb * .85, alb)
    alb = np.where((part > 1.5)[:, None], alb * .7, alb)
    alb = alb * (1 - .12 * flap)[:, None]
    stitch_line = np.zeros(len(p))
    rivet = np.zeros(len(p))
    rough = np.full(len(p), .82)
    seam_x = smoothstep(.0015, .0005, np.abs(np.abs(nb[:, 0]) - .97))

    def height(q):
        tw = cloth.triplanar(q, nb, cloth.twill) * 1.4
        folds = (fbm(q, 34, 3, 9) - .5) * .0022
        knee = np.exp(-((q[:, 1] - knee_y) / .05) ** 2) * np.sin(q[:, 1] * 2 * np.pi * 32 + fbm(q, 20, 2, 3) * 4) * .0014
        stitch = (np.sin(q[:, 1] * 2 * np.pi / .004) > .2) * edge * .00025
        return tw + folds + knee + pm * .0006 + flap * .0005 - edge * .0007 + stitch
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    mat = tex_material(b, 'cargo', a, nm, orm, color='#1d1f26', sheen=((.18, .18, .2), .7))
    b.derived('cargo', s, mat)
    # Rebites de latão nas lapelas dos bolsos.
    rivets = []
    for side in (1, -1):
        pts = s.pos[(np.sign(s.pos[:, 0]) == side) & (np.abs(s.pos[:, 1] - (knee_y + .225)) < .006) & (s.part < 1.5)]
        if len(pts):
            pnt = pts[np.argmax(np.abs(pts[:, 0]))]
            rivets.append(sphere_mesh(pnt + np.array([side * .0015, 0, 0]), .0032, 10, 6))
    brass = metal(b, 'brass', BRASS, .35)
    if rivets:
        emit_parts(b, 'rivets', rivets, brass)
    return b.save({'hides': ['hips', 'thigh_a', 'thigh_b', 'thigh_c', 'thigh_d', 'shin_a', 'shin_b']})


# ------------------------------------------------------------------ botas de fivelas

def boot_shell(model, layout, A, collar_t=.42):
    """Bota de cano médio: pé justo, cano com folga para passar por cima da calça."""
    c = model.coords

    def ok(v):
        b = A.bone[v]
        foot = np.isin(b, ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'))
        shin = np.isin(b, ('LeftLeg', 'RightLeg')) & (A.t[v] > collar_t)
        return (foot | shin).all()
    s = G.surface(model, G.select(layout, ok))
    v = s.vid
    t = np.clip(A.t[v], 0, 1)
    shin = np.isin(A.bone[v], ('LeftLeg', 'RightLeg'))
    pants = PANTS['ease_knee'] + (PANTS['ease_ankle'] - PANTS['ease_knee']) * (t / PANTS['end_t']) ** 1.5
    ease = np.where(shin, pants + .012, .0075)
    ease = np.where(shin, ease * smoothstep(.98, .88, t) + .0075 * (1 - smoothstep(.98, .88, t)), ease)
    G.offset(model, s, ease)
    hull_fill(s, .85)
    G.smooth(s, 8, keep_boundary=True)
    s.pos[:, 1] = np.maximum(s.pos[:, 1], .018)
    for loop in G.loops(s):
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (k - a) / np.linalg.norm(k - a)
        G.straighten(s, loop, s.pos[loop].mean(0), axis + np.array([0, 0, .12]), rings=2)
        G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .012, rows=2, part=1, flare=.003)
    G.solidify(s, .0025)
    return s


def buckle_boots(model, layout, item_id='shoes_buckle_boots'):
    A = G.Anatomy(model)
    G.reset_strips()
    collar_t = .42
    s = boot_shell(model, layout, A, collar_t)
    b = ItemBuilder(model, item_id, 'shoes')
    bake = cloth.bake_surface(s, 1024)
    p = bake.pos[bake.mask].astype(np.float64)
    nb = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    alb = np.tile(cloth.srgb(LEATHER), (len(p), 1)) * (.9 + .25 * fbm(p, 40, 3, 2))[:, None]
    stitch = np.zeros(len(p))
    toe = np.zeros(len(p))
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = np.sign(p[:, 0]) == sign
        fw = (p - ankle) @ f
        toe[m] = smoothstep(.085, .095, fw[m])
        stitch[m] = (smoothstep(.002, .0008, np.abs(p[m, 1] - .03)) * (np.sin(fw[m] * 2 * np.pi / .005) > 0)
                     + smoothstep(.0015, .0006, np.abs(fw[m] - .09)) * (p[m, 1] < .07))
    alb = cloth.lin_mix(alb, cloth.srgb('#5a4a3a'), stitch * .6)
    alb = np.where((part > .5)[:, None], alb * .8, alb)
    rough = np.where(part > .5, .5, .42 - .06 * toe)

    def height(q):
        crease = smoothstep(.16, .1, q[:, 1]) * smoothstep(.06, .09, q[:, 1]) * np.sin(q[:, 1] * 2 * np.pi * 70 + fbm(q, 30, 2, 2) * 5) * .0004
        return (fbm(q, 700, 2, 3) - .5) * .00006 + (fbm(q, 60, 2, 5) - .5) * .0003 + crease + stitch * .0003
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    upper = tex_material(b, 'leather', a, nm, orm, clearcoat=(.45, .3))
    b.derived('upper', s, upper, weight_smooth=2)
    sole_mat = flat_material(b, 'sole', '#0d0d10', roughness=.7)
    welt = flat_material(b, 'welt', '#3a2a1e', roughness=.6)
    for side, sign in (('Left', 1), ('Right', -1)):
        pos, uv, tris, _, _ = sole_mesh(s, sign, y_bottom=-.017, y_top=.022, flare=.005)
        b.bound(f'sole_{side}', pos, tris, uv, sole_mat, bone=f'{side}Foot')
        pos2, uv2, tris2, _, _ = sole_mesh(s, sign, y_bottom=.012, y_top=.024, flare=.0062)
        b.bound(f'welt_{side}', pos2, tris2, uv2, welt, bone=f'{side}Foot')

    # Tiras de couro com fivelas douradas ao redor do cano.
    strap = flat_material(b, 'strap', '#1d1b1f', roughness=.45, clearcoat=(.4, .25))
    gold = metal(b, 'buckle', GOLD, .25)
    outer = s.pos[s.part < 1.5]
    for side, sign in (('Left', 1), ('Right', -1)):
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis_v = (k - a) / np.linalg.norm(k - a)
        straps, buckles = [], []
        for i, t in enumerate((.52, .64, .76, .88)):
            center = k + (a - k) * t
            ax, u, v = basis(axis_v)
            pts = outer[np.sign(outer[:, 0]) == sign]
            rad = profile(pts, center, ax, u, v, 48, .008)
            straps.append(ring_band(center, ax, u, v, rad + .0006, .011 if i < 3 else .013, .0024))
            # Fivela no lado de fora da perna.
            ang = np.arctan2((np.array([sign, 0, .25]) @ v), (np.array([sign, 0, .25]) @ u))
            j = int(round((ang + np.pi) / (2 * np.pi) * 48)) % 48
            dirv = np.cos(2 * np.pi * j / 48 - np.pi) * u + np.sin(2 * np.pi * j / 48 - np.pi) * v
            tang = np.cross(ax, dirv)
            bc = center + dirv * (rad[j] + .0035)
            hw, hh, tk = .0095, .0085, .0016
            for off, sx, sy in ((tang * hw, .0016, hh), (-tang * hw, .0016, hh), (ax * hh, hw, .0016), (-ax * hh, hw, .0016)):
                buckles.append(box(bc + off, tang, ax, dirv, sx, sy, tk))
            buckles.append(box(bc, tang, ax, dirv, .0012, hh * .9, tk * .8))
        emit_parts(b, f'straps_{side}', straps, strap)
        emit_parts(b, f'buckles_{side}', buckles, gold)
    return b.save({'hides': ['feet', 'shin_c', 'shin_d'], 'lift': .017})


# ------------------------------------------------------------------ cinto do raio

def bolt_belt(model, layout, item_id='belt_bolt'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, top = pants_surface(model, layout, A, **PANTS)
    b = ItemBuilder(model, item_id, 'belt')
    yc = top - .022
    center = np.array([0, yc, A.h['Hips'][2]])
    ax, u, v = np.array([0, 1., 0]), np.array([0, 0, 1.]), np.array([1., 0, 0])
    rad = profile(s.pos, center, ax, u, v, 72, .02)
    leather = flat_material(b, 'belt', '#2a1d16', roughness=.5, clearcoat=(.3, .3))
    pos, nrm, tris = ring_band(center, ax, u, v, rad + .006, .034, .0042)
    b.bound('belt', pos, tris, np.zeros((len(pos), 2)), leather, nrm=nrm)
    j = 36  # ângulo 0 = frente (+z)
    front = center + u * (rad[j] + .0105)
    brass = metal(b, 'frame', BRASS, .3)
    bolt = b.glb.material('bolt', color=(*lin('#ffd35a'), 1), metallic=1, roughness=.2, emissive=(.35, .22, .02))
    frame = []
    hw, hh = .03, .024
    for off, sx, sy in ((v * hw, .004, hh), (-v * hw, .004, hh), (ax * hh, hw + .004, .004), (-ax * hh, hw + .004, .004)):
        frame.append(box(front + off, v, ax, u, sx, sy, .0035))
    frame.append(box(front - u * .0015, v, ax, u, hw, hh, .0012))
    emit_parts(b, 'frame', frame, brass, bone='Hips', rigid=True)
    poly = np.array([(-.004, .021), (.012, .021), (.004, .004), (.013, .004), (-.008, -.022), (-.002, -.003), (-.011, -.003)])
    emit_parts(b, 'bolt', [extrude(poly, front - u * .0005, v, ax, u, .0055)], bolt, bone='Hips', rigid=True)
    # Passadores e rebites.
    studs = []
    for jj in (16, 26, 46, 56):
        d = np.cos(2 * np.pi * jj / 72 - np.pi) * u + np.sin(2 * np.pi * jj / 72 - np.pi) * v
        studs.append(sphere_mesh(center + d * (rad[jj] + .0105), .0035, 10, 6))
    emit_parts(b, 'studs', studs, brass)
    return b.save({})


# ------------------------------------------------------------------ braço mecânico

def _bone_faces(layout, A, model, bones, extra=None):
    out = []
    for mat, corners in layout.faces:
        if mat != 'body':
            continue
        v = np.array([c[0] for c in corners])
        okb = np.isin(A.bone[v], bones)
        if extra is not None:
            okb = okb | extra(v)
        if okb.all():
            out.append(corners)
    return out


def mech_arm(model, layout, item_id='hands_mech_arm'):
    A = G.Anatomy(model)
    G.reset_strips()
    b = ItemBuilder(model, item_id, 'hands')
    names = model.bone_names
    right = [n for n in names if n.startswith('RightHand')]
    left = [n for n in names if n.startswith('LeftHand')]
    # Luva preta na mão esquerda; luva de borracha escura sob a mecânica da direita.
    glove = flat_material(b, 'glove', '#121215', roughness=.42, clearcoat=(.5, .3))
    faces = _bone_faces(layout, A, model, left, lambda v: (A.bone[v] == 'LeftForeArm') & (A.t[v] > .9))
    b.skin_layer('glove_left', faces, .0013, glove)
    under = flat_material(b, 'under', '#2b2d33', roughness=.4, metallic=.6)
    faces = _bone_faces(layout, A, model, right, lambda v: (A.bone[v] == 'RightForeArm') & (A.t[v] > .9))
    b.skin_layer('under_right', faces, .0013, under)
    cuff = []
    hs, hl = A.h['LeftHand'], A.h['LeftForeArm']
    axl, ul, vl = basis(hs - hl)
    P = model.coords[A.bone == 'LeftForeArm']
    c0 = hl + (hs - hl) * .9
    rad = profile(P, c0, axl, ul, vl, 40, .01)
    cuff.append(ring_band(c0, axl, ul, vl, rad + .002, .016, .003))
    emit_parts(b, 'glove_cuff', cuff, glove)

    brass = metal(b, 'brass', BRASS, .28)
    steel = metal(b, 'steel', '#3b3e46', .35, .9)
    glow = b.glb.material('glow', color=(*GLOW, 1), roughness=.2, emissive=GLOW)
    glass = b.glb.material('glass', color=(.75, .9, 1, .28), roughness=.05, alpha=('BLEND', 0))

    # Manopla no antebraço: casca de aço, aros de latão, tubos de vidro brilhando.
    e, h = A.h['RightForeArm'], A.h['RightHand']
    axf, uf, vf = basis(h - e)
    length = np.linalg.norm(h - e)
    P = model.coords[A.bone == 'RightForeArm']
    shell, rings, tubes, cores, caps = [], [], [], [], []
    ts = np.linspace(.5, .99, 9)
    radii = [profile(P, e + (h - e) * t, axf, uf, vf, 40, .012) for t in ts]
    grid = []
    for t, rad in zip(ts, radii):
        cen = e + (h - e) * t
        rr = rad + .024 + .004 * smoothstep(.5, .6, t)
        row = []
        for j in range(40):
            a = 2 * np.pi * j / 40 - np.pi
            row.append(cen + (np.cos(a) * uf + np.sin(a) * vf) * rr[j])
        grid.append(row)
    sh = grid_surface(np.array(grid), closed_u=True)
    G.solidify(sh, .003)
    b.bound('gauntlet', sh.pos, sh.tris, np.zeros((len(sh.pos), 2)), steel, nrm=G.vertex_normals_canon(sh), bone='RightForeArm')
    for t in (.5, .66, .83, .985):
        cen = e + (h - e) * t
        rad = profile(P, cen, axf, uf, vf, 40, .012)
        rings.append(ring_band(cen, axf, uf, vf, rad + .027 + .004 * (t > .55), .012, .004))
    # Tubos de vidro do lado de fora/cima do antebraço.
    out_dir = np.array([-.3, 1, .1])
    for k, dang in enumerate((-.55, 0, .55)):
        od = out_dir - axf * (out_dir @ axf)
        od /= np.linalg.norm(od)
        side = np.cross(axf, od)
        d = np.cos(dang) * od + np.sin(dang) * side
        rad_at = lambda t: profile(P, e + (h - e) * t, axf, uf, vf, 40, .012).max()
        r0 = rad_at(.7) + .036
        base = e + (h - e) * .53 + d * r0
        tl = length * .43
        cores.append(cylinder(base, axf, .0035, tl, 12))
        tubes.append(cylinder(base, axf, .0062, tl, 16))
        for tt in (0, tl):
            caps.append(cylinder(base + axf * (tt - .004), axf, .0075, .008, 16))
    emit_parts(b, 'rings', rings, brass, bone='RightForeArm')
    emit_parts(b, 'caps', caps, brass, bone='RightForeArm')
    emit_parts(b, 'cores', cores, glow, bone='RightForeArm')
    emit_parts(b, 'tubes', tubes, glass, bone='RightForeArm')
    # Bobina na base da manopla (perto do cotovelo).
    coil = []
    cen = e + (h - e) * .44
    rad = profile(P, cen, axf, uf, vf, 40, .012)
    for k in range(5):
        coil.append(ring_band(cen + axf * (k * .006), axf, uf, vf, rad + .016, .004, .003))
    emit_parts(b, 'coil', coil, metal(b, 'copper', '#b4683a', .3), bone='RightForeArm')

    # Placa no dorso da mão direita.
    f_dir = model.heads['RightHandMiddle1'] - model.heads['RightHand']
    th_dir = model.heads['RightHandThumb1'] - model.heads['RightHand']
    dorsal = np.cross(f_dir, th_dir)
    dorsal /= np.linalg.norm(dorsal)

    def dors(corners):
        v = np.array([c[0] for c in corners])
        return (A.bone[v] == 'RightHand').all() and (model.normals[v] @ dorsal).min() > .45
    faces = [cn for mat, cn in layout.faces if mat == 'body' and dors(cn)]
    if faces:
        ps = G.surface(model, faces)
        G.offset(model, ps, .0045)
        G.smooth(ps, 4)
        G.solidify(ps, .0025)
        b.derived('hand_plate', ps, brass, weight_smooth=1)
    # Dedos articulados: falanges de aço e juntas de latão presas a cada osso.
    for bone in right:
        if bone == 'RightHand':
            continue
        hd = model.heads[bone]
        tl = model.tails[bone]
        axb = tl - hd
        ln = np.linalg.norm(axb)
        axb /= ln
        V = model.coords[A.bone == bone]
        rel = V - hd
        hgt = rel @ axb
        sel = (hgt > 0) & (hgt < ln)
        rad = np.linalg.norm(rel[sel] - np.outer(hgt[sel], axb), axis=1)
        rf = np.percentile(rad, 85) if len(rad) else .008
        seg = [cylinder(hd + axb * ln * .16, axb, rf + .0016, ln * .68, 12)]
        emit_parts(b, f'{bone}_seg', seg, steel, bone=bone)
        emit_parts(b, f'{bone}_joint', [sphere_mesh(hd, rf + .0022, 10, 7)], brass, bone=bone)
        if bone.endswith('3'):
            emit_parts(b, f'{bone}_tip', [sphere_mesh(hd + axb * ln * .9, rf + .0012, 10, 7)], steel, bone=bone)
    return b.save({})


def register(item):
    item('hair_spiky', 'hair')(spiky_hair)
    item('top_lab_coat', 'top')(lab_coat)
    item('bottom_cargo_dark', 'bottom')(cargo_pants)
    item('shoes_buckle_boots', 'shoes')(buckle_boots)
    item('hands_mech_arm', 'hands')(mech_arm)
    item('belt_bolt', 'belt')(bolt_belt)
