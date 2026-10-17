"""Demais peças do catálogo: básicos tintáveis, Nova, Meia-Noite e acessórios."""
from __future__ import annotations

import numpy as np

import cloth
import garments as G
from garments import Surface
from items import ItemBuilder
from raster import fbm, smoothstep
from wardrobe import (TORSO, classify_loops, foot_frame, jersey_camisa10, nipple_centers, shoe_shell,
                      shorts_surface, sole_mesh)


def lin(hexstr):
    c = cloth.srgb(hexstr)
    return tuple(np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4))


def tex_material(b, name, alb, nrm, orm, color=None, tint=None, sheen=None, clearcoat=None, extras=None, alpha=None,
                 size_q=88, double=False):
    ex = dict(extras or {})
    if tint:
        ex['tint'] = tint
    base = b.glb.texture(alb, fmt='webp' if alb.mode == 'RGBA' else 'jpeg', quality=size_q)
    return b.glb.material(name, color=(*lin(color), 1) if color else (1, 1, 1, 1), base=base,
                          normal=b.glb.texture(nrm, fmt='webp', quality=88) if nrm is not None else None,
                          orm=b.glb.texture(orm, fmt='jpeg', quality=82) if orm is not None else None,
                          roughness=1 if orm is not None else .6, sheen=sheen, clearcoat=clearcoat, extras=ex or None,
                          alpha=alpha, double=double)


def flat_material(b, name, hexstr, roughness=.5, metallic=0., tint=None, clearcoat=None, alpha=None, opacity=1.0, extras=None):
    ex = dict(extras or {})
    if tint:
        ex['tint'] = tint
    return b.glb.material(name, color=(*lin(hexstr), opacity), roughness=roughness, metallic=metallic,
                          clearcoat=clearcoat, alpha=alpha, extras=ex or None)


def baked_tris(s: Surface):
    part = s.part if s.part is not None else np.zeros(len(s.pos))
    return np.flatnonzero((part[s.tris] < 1.5).all(1))


def subsurface(s: Surface, tri_ids, lift=0.0):
    tris = s.tris[tri_ids]
    used = np.unique(tris)
    remap = np.full(len(s.pos), -1)
    remap[used] = np.arange(len(used))
    n = G.vertex_normals_canon(s)
    part = s.part[used] if s.part is not None else None
    return Surface(s.pos[used] + n[used] * lift, s.vid[used], s.uv[used], remap[tris], s.ref[used], part)


def decal(b, s, bake, rgba, name, offset=.0007, roughness=.5, metallic=0., tint=None, color='#ffffff', clearcoat=None):
    """Camada decalque (listras, zíper, logos) sobre a peça, sem tinta do jogador."""
    from PIL import Image
    m = bake.mask
    img = np.zeros(m.shape + (4,), np.float32)
    img[m] = rgba
    covered = img[..., 3] > .02
    tri_hit = np.unique(bake.tri[covered & m])
    tri_hit = tri_hit[tri_hit >= 0]
    if not len(tri_hit):
        return
    from raster import dilate
    img = dilate(img, m)
    alb = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGBA')
    ids = baked_tris(s)[tri_hit]
    sub = subsurface(s, ids, offset)
    ex = {'overlay': True}
    if tint:
        ex['tint'] = tint
    mat = b.glb.material(name, color=(*lin(color), 1), base=b.glb.texture(alb, fmt='webp', quality=90), roughness=roughness,
                         metallic=metallic, alpha=('MASK', .5), clearcoat=clearcoat, extras=ex)
    b.derived(name, sub, mat)


def fabric_height(n, kind='knit', folds=.0012, extra=None):
    def h(q):
        if kind == 'knit':
            base = cloth.triplanar(q, n, cloth.knit)
        elif kind == 'rib':
            base = cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .003))
        elif kind == 'twill':
            base = cloth.triplanar(q, n, cloth.twill) * 1.5
        elif kind == 'fleece':
            base = cloth.fleece(q, n) * 1.5
        elif kind == 'satin':
            base = (fbm(q, 300, 2, 2) - .5) * .00004
        else:
            base = (fbm(q, 900, 2, 5) - .5) * .00006
        out = base + (fbm(q, 38, 3, 11) - .5) * folds
        if extra is not None:
            out = out + extra(q)
        return out
    return h


def neutral(p, level=.94, var=.05):
    v = level * (1 + var * (fbm(p, 25, 3, 7) - .5)) * (1 + .02 * (fbm(p, 200, 2, 3) - .5))
    return np.stack([v, v, v], 1)


def hem_ease(model, A, s, amount=.009, top=.14):
    """Folga extra perto da barra para a peça cobrir o cós da parte de baixo."""
    hips_y = A.h['Hips'][1]
    k = smoothstep(hips_y + top, hips_y - .02, s.pos[:, 1])
    G.offset(model, s, amount * k)


_env = {}


def bottoms_envelope(model, layout, A):
    """Raio máximo das partes de baixo (cós) por altura e ângulo, para as blusas passarem por fora."""
    if 'e' not in _env:
        sb, hem_y, top = shorts_surface(model, layout, A)
        for loop in classify_loops(sb)['hem']:
            G.band(sb, loop, lambda P: np.tile([0., 1, 0], (len(P), 1)), .026, rows=3, part=1, inward=.002)
        P = sb.pos
        cz = .0
        r = np.hypot(P[:, 0], P[:, 2] - cz)
        th = np.arctan2(P[:, 0], P[:, 2] - cz)
        nb, dy = 48, .01
        ti = ((th + np.pi) / (2 * np.pi) * nb).astype(int) % nb
        yi = np.floor(P[:, 1] / dy).astype(int)
        y0, y1 = A.h['Hips'][1] - .06, top + .05
        sel = (P[:, 1] > y0) & (P[:, 1] < y1)
        R = {}
        for a, b, rr in zip(yi[sel], ti[sel], r[sel]):
            R[(a, b)] = max(R.get((a, b), 0), rr)
        _env['e'] = (R, dy, nb, cz, y0, y1)
    return _env['e']


def clear_bottoms(model, layout, A, s, gap=.011):
    R, dy, nb, cz, y0, y1 = bottoms_envelope(model, layout, A)
    P = s.pos
    r = np.hypot(P[:, 0], P[:, 2] - cz)
    th = np.arctan2(P[:, 0], P[:, 2] - cz)
    ti = ((th + np.pi) / (2 * np.pi) * nb).astype(int) % nb
    yi = np.floor(P[:, 1] / dy).astype(int)
    need = np.zeros(len(P))
    for k in range(len(P)):
        if not (y0 - .02 < P[k, 1] < y1 + .02):
            continue
        best = 0
        for dyb in (-2, -1, 0, 1, 2):
            for dtb in (-2, -1, 0, 1, 2):
                best = max(best, R.get((yi[k] + dyb, (ti[k] + dtb) % nb), 0))
        if best:
            need[k] = max(0, best + gap - r[k])
    scale = np.where(r > 1e-6, (r + need) / np.maximum(r, 1e-6), 1)
    s.pos = np.stack([P[:, 0] * scale, P[:, 1], (P[:, 2] - cz) * scale + cz], 1)
    G.smooth(s, 2, keep_boundary=True)


def loops_by(s, fn):
    out = {}
    for loop in G.loops(s):
        out.setdefault(fn(s.pos[loop].mean(0)), []).append(loop)
    return out


def arm_axis(A, side, upper=True):
    a = A.h[f'{side}Arm'] if upper else A.h[f'{side}ForeArm']
    f = A.h[f'{side}ForeArm'] if upper else A.h[f'{side}Hand']
    return a, f, (f - a) / np.linalg.norm(f - a)


# --------------------------------------------------------------------------- tops

def tee(model, layout, item_id='top_tee', color='#f2f2ee'):
    A = G.Anatomy(model)
    G.reset_strips()
    s = G_shirt(model, layout, A, sleeve=.5, hem=.075, ease=.009, sleeve_ease=(.012, .022))
    hem_ease(model, A, s)
    clear_bottoms(model, layout, A, s)
    clip_neck(A, s)
    L = classify_loops(s)
    neck_c = A.h['Neck']
    for loop in L['neck']:
        G.band(s, loop, lambda P: np.array([0, 1, 0]) + (neck_c - P) * np.array([1.2, 0, 1.2]), .009, rows=3, part=1)
    G.solidify(s, .0022)
    b = ItemBuilder(model, item_id, 'top')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    alb = neutral(p)
    hem_line = smoothstep(.0025, .001, np.abs(p[:, 1] - (A.h['Hips'][1] - .075 + .012 + .014))) * (part < .5)
    alb *= (1 - .08 * hem_line)[:, None]
    alb = np.where((part > 1.5)[:, None], alb * .78, alb)
    rough = np.where(part > .5, .82, .72)
    is_trim = part > .5
    hips_y = A.h['Hips'][1]

    def extra(q):
        waist = smoothstep(.09, .15, np.abs(q[:, 0])) * smoothstep(hips_y + .2, hips_y + .05, q[:, 1])
        return waist * np.sin(q[:, 1] * 2 * np.pi * 24 + fbm(q, 30, 2, 4) * 5) * .0013 + hem_line * .0003
    hfn = fabric_height(n, 'knit', .0016, extra)

    def height(q):
        return np.where(is_trim, cloth.triplanar(q, n, cloth.rib), hfn(q))
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    mat = tex_material(b, 'tee', a, nm, orm, color=color, tint='main', sheen=((.3, .3, .3), .7))
    b.derived('tee', s, mat)
    return b.save({'hides': ['chest', 'belly', 'upperarm_a', 'upperarm_b']})


def clip_neck(A, s, normal=(0, 1, .45), drop=.0):
    """Remove dobras acima do plano do decote (nada do tecido sobe acima da gola)."""
    nrm = np.array(normal, float)
    nrm /= np.linalg.norm(nrm)
    loop = [l for l in G.loops(s) if s.pos[l].mean(0)[1] > A.h['Neck'][1] - .1 and abs(s.pos[l].mean(0)[0]) < .1]
    if not loop:
        return
    point = s.pos[loop[0]].mean(0) - nrm * drop
    near = s.pos[:, 1] > A.h['Neck'][1] - .09
    d = (s.pos - point) @ nrm
    over = near & (d > 0)
    s.pos[over] -= np.outer(d[over], nrm)
    G.smooth(s, 2, keep_boundary=True)


def G_shirt(model, layout, A, **kw):
    from wardrobe import shirt_surface
    return shirt_surface(model, layout, A, **kw)


def tank(model, layout, item_id='top_tank', color='#2d3442'):
    A = G.Anatomy(model)
    G.reset_strips()
    c = model.coords
    neck_y, hips_y = A.h['Neck'][1], A.h['Hips'][1]
    arm_y = A.h['LeftArm'][1]
    sh_x = A.h['LeftArm'][0]

    def edge(x, front):
        ax = np.abs(x)
        y_sh = neck_y + .012 - np.clip(ax - .05, 0, None) * .45
        scoop = np.where(front, .07, .03) * (1 - smoothstep(.04, .065, ax))
        e = y_sh - scoop
        arm_bottom = arm_y - np.where(front, .1, .13)
        y11 = neck_y + .012 - .06 * .45
        cava = y11 - np.clip((ax - .105) / .055, 0, 1) ** .7 * (y11 - arm_bottom)
        return np.where(ax > .105, cava, e)

    def ok(v):
        b = A.bone[v]
        x, y, z = c[v, 0], c[v, 1], c[v, 2]
        torso = np.isin(b, TORSO) | (np.isin(b, ('LeftArm', 'RightArm')) & (np.abs(x) < .19))
        return (torso & (y < edge(x, z > -.01)) & (y > hips_y - .07)).all()
    s = G.surface(model, G.select(layout, ok))
    low = smoothstep(A.h['Spine'][1] + .05, hips_y - .07, s.pos[:, 1])
    G.offset(model, s, .007 + .006 * low)
    G.flatten(s, nipple_centers(model), .028)
    G.smooth(s, 14, keep_boundary=True)
    G.drape(model, s, s.pos[:, 1] < A.h['Spine2'][1] + .05, amount=1.0, slope=.14)
    near = np.min([np.linalg.norm(s.ref - q, axis=1) for q in nipple_centers(model)], axis=0) < .04
    G.push_out(model, s, .004, skip=near)
    groups = loops_by(s, lambda cen: 'hem' if cen[1] < hips_y + .05 else ('neck' if abs(cen[0]) < .05 else 'arm'))
    for loop in groups.get('hem', []):
        G.straighten(s, loop, np.array([0, hips_y - .07 + .012, 0]), [0, 1, 0])
    G.smooth(s, 4, keep_boundary=True)
    G.push_out(model, s, .0015, skip=near)
    G.flatten(s, nipple_centers(model), .03)
    G.push_out(model, s, .003, smooth_body=False)
    hem_ease(model, A, s)
    clear_bottoms(model, layout, A, s)
    groups = loops_by(s, lambda cen: 'hem' if cen[1] < hips_y + .05 else ('neck' if abs(cen[0]) < .05 else 'arm'))
    for key in ('neck', 'arm'):
        for loop in groups.get(key, []):
            G.smooth_loop(s, loop, 14, rings=4)
    G.smooth(s, 3, keep_boundary=True)
    G.push_out(model, s, .003, smooth_body=False)
    G.solidify(s, .0025)
    b = ItemBuilder(model, item_id, 'top')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    alb = neutral(p, .9)
    alb = np.where((part > 1.5)[:, None], alb * .78, alb)
    rough = np.where(part > .5, .8, .7)
    is_trim = part > .5
    hfn = fabric_height(n, 'rib', .0012)

    def height(q):
        return np.where(is_trim, cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .002)), hfn(q))
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    mat = tex_material(b, 'tank', a, nm, orm, color=color, tint='main', sheen=((.25, .25, .25), .7))
    b.derived('tank', s, mat)
    return b.save({'hides': ['belly']})


def jersey_away(model, layout):
    return jersey_camisa10(model, layout, item_id='top_jersey_away', base='#1f2c66', trim='#f2cf1d', accent='#b8930c')


def long_top_surface(model, layout, A, ease=.009, sleeve_ease=(.011, .016), hem=.03, sleeve_end=.9, drape=1.0, neck_up=.012):
    """Parte de cima de manga longa (jaqueta, túnica)."""
    neck_y, hips_y = A.h['Neck'][1], A.h['Hips'][1]
    c = model.coords

    def ok(v):
        b = A.bone[v]
        torso = np.isin(b, TORSO)
        upper = np.isin(b, ('LeftArm', 'RightArm'))
        fore = np.isin(b, ('LeftForeArm', 'RightForeArm')) & (A.t[v] < sleeve_end)
        y = c[v, 1]
        return ((torso | upper | fore) & (y < neck_y + neck_up) & (y > hips_y - hem)).all()
    s = G.surface(model, G.select(layout, ok))
    v = s.vid
    arm = np.isin(A.bone[v], ('LeftArm', 'RightArm', 'LeftForeArm', 'RightForeArm'))
    fore = np.isin(A.bone[v], ('LeftForeArm', 'RightForeArm'))
    t = np.clip(A.t[v], 0, 1)
    low = smoothstep(A.h['Spine'][1] + .05, hips_y - hem, s.pos[:, 1])
    amount = np.where(arm, sleeve_ease[0] + (sleeve_ease[1] - sleeve_ease[0]) * np.where(fore, .5 + .5 * t, .5 * t), ease + .006 * low)
    G.offset(model, s, amount)
    G.flatten(s, nipple_centers(model), .028)
    G.smooth(s, 14, weights=np.where(arm, .6, 1.0), keep_boundary=True)
    if drape:
        G.drape(model, s, ~arm & (s.pos[:, 1] < A.h['Spine2'][1] + .05), amount=drape, slope=.14)
    near = np.min([np.linalg.norm(s.ref - q, axis=1) for q in nipple_centers(model)], axis=0) < .04
    G.push_out(model, s, .004, skip=near)
    L = classify_loops(s)
    for loop in L['hem']:
        G.straighten(s, loop, np.array([0, hips_y - hem + .012, 0]), [0, 1, 0])
    for loop in L['sleeve']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        a, f, axis = arm_axis(A, side, upper=False)
        G.straighten(s, loop, a + (f - a) * (sleeve_end - .05), axis)
    for loop in L['neck']:
        G.straighten(s, loop, s.pos[loop].mean(0), [0, 1, .2])
    G.smooth(s, 3, keep_boundary=True)
    G.push_out(model, s, .002, skip=near)
    G.flatten(s, nipple_centers(model), .03)
    hem_ease(model, A, s, .01)
    clear_bottoms(model, layout, A, s)
    return s


def track_jacket(model, layout, item_id='top_track_jacket', color='#7c5ce0'):
    A = G.Anatomy(model)
    G.reset_strips()
    s = long_top_surface(model, layout, A, ease=.008, sleeve_ease=(.01, .015), hem=.035)
    L = classify_loops(s)
    neck_c = A.h['Neck']
    for loop in L['neck']:
        G.band(s, loop, lambda P: np.array([0, 1, 0]) + (neck_c - P) * np.array([.6, 0, .6]), .03, rows=4, part=1)
    for loop in L['sleeve']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        _, _, axis = arm_axis(A, side, upper=False)
        G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .03, rows=3, part=1, inward=.004)
    for loop in L['hem']:
        G.band(s, loop, lambda P: np.tile([0., -1, 0], (len(P), 1)), .035, rows=3, part=1, inward=.003)
    G.solidify(s, .0026)
    b = ItemBuilder(model, item_id, 'top')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    alb = neutral(p, .88, .04)
    alb = np.where((part > .5)[:, None] & (part < 1.5)[:, None], alb * .82, alb)
    alb = np.where((part > 1.5)[:, None], alb * .7, alb)
    rough = np.where(part > .5, .8, .55)
    is_trim = part > .5
    hfn = fabric_height(n, 'satin', .0018)

    def height(q):
        zip_groove = smoothstep(.006, .002, np.abs(q[:, 0])) * (q[:, 2] > .02) * -.0005
        return np.where(is_trim, cloth.triplanar(q, n, cloth.rib), hfn(q) + zip_groove)
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    mat = tex_material(b, 'jacket', a, nm, orm, color=color, tint='main', sheen=((.45, .45, .5), .4))
    b.derived('jacket', s, mat)
    # Decalque: zíper metálico frontal e duas listras brancas ao longo das mangas.
    rgba = np.zeros((len(p), 4))
    front = (z > .0) & (n[:, 2] > .1)
    zip_m = smoothstep(.0045, .0025, np.abs(x)) * front * (y < A.h['Neck'][1] + .05) * (y > A.h['Hips'][1] - .07)
    teeth = .7 + .3 * (np.sin(y * 2 * np.pi / .0035) > 0)
    rgba[:, :3] = np.where(zip_m[:, None] > .01, np.array([.78, .78, .8]) * teeth[:, None], np.array([.96, .96, .95]))
    stripes = np.zeros(len(p))
    for side, sgn in (('Left', 1), ('Right', -1)):
        for seg_from, seg_to in ((f'{side}Arm', f'{side}ForeArm'), (f'{side}ForeArm', f'{side}Hand')):
            pa, pb = A.h[seg_from], A.h[seg_to]
            d = (pb - pa)
            tt = np.clip(((p - pa) @ d) / (d @ d), 0, 1)
            closest = pa + tt[:, None] * d
            rel = p - closest
            # Lado de fora do braço (direção para fora/cima no plano perpendicular).
            out = np.array([sgn, .35, 0])
            out = out - d * (out @ d) / (d @ d)
            out /= np.linalg.norm(out)
            relp = rel - (rel @ d / (d @ d))[:, None] * d
            r = np.linalg.norm(relp, axis=1) + 1e-9
            ang = np.arccos(np.clip((relp @ out) / r, -1, 1)) * r
            on_arm = (part < .5) & (np.linalg.norm(rel, axis=1) < .07) & (np.sign(x) == sgn) & (np.abs(x) > .17)
            stripes = np.maximum(stripes, smoothstep(.0035, .0022, np.abs(ang - .009)) * on_arm)
    rgba[:, 3] = np.clip(zip_m + stripes, 0, 1)
    decal(b, s, bake, rgba, 'details', roughness=.35, metallic=0.)
    return b.save({'hides': ['chest', 'belly', 'upperarm_a', 'upperarm_b', 'upperarm_c', 'upperarm_d', 'forearm_a', 'forearm_b', 'forearm_c']})


def ruff_mesh(A, neck_c, r_in=.068, r_out=.155, pleats=30, rows=6):
    """Gola franzida em pregas (rufo) ao redor do pescoço."""
    cy = neck_c[1] + .028
    pos, tris = [], []
    k = pleats * 8
    for layer, (dy, wob) in enumerate(((0, .018), (-.005, .02))):
        base = len(pos)
        for r in range(rows):
            f = r / (rows - 1)
            rr = r_in + (r_out - r_in) * f
            for i in range(k):
                a = 2 * np.pi * i / k
                pleat = np.sin(a * pleats) * wob * (.2 + .8 * f)
                pos.append((neck_c[0] + np.sin(a) * rr * 1.08, cy + dy - .045 * f ** 1.3 + pleat, neck_c[2] + .012 + np.cos(a) * rr * .92))
        for r in range(rows - 1):
            for i in range(k):
                a, bb = base + r * k + i, base + r * k + (i + 1) % k
                c2, d2 = a + k, bb + k
                if layer == 0:
                    tris += [(a, c2, bb), (bb, c2, d2)]
                else:
                    tris += [(a, bb, c2), (bb, d2, c2)]
    pos = np.array(pos)
    uv = np.zeros((len(pos), 2))
    return pos, np.array(tris), uv


def sphere_mesh(center, radius, seg=14, rings=10):
    th = np.linspace(0, np.pi, rings + 1)
    ph = np.linspace(0, 2 * np.pi, seg + 1)[:-1]
    T, P = np.meshgrid(th, ph, indexing='ij')
    pos = np.stack([np.sin(T) * np.cos(P), np.cos(T), np.sin(T) * np.sin(P)], -1).reshape(-1, 3)
    nrm = pos.copy()
    pos = pos * radius + center
    tris = []
    for r in range(rings):
        for s in range(seg):
            a, b = r * seg + s, r * seg + (s + 1) % seg
            c, d = a + seg, b + seg
            tris += [(a, b, c), (b, d, c)]
    return pos, nrm, np.array(tris)


def clown_tunic(model, layout, item_id='top_clown_tunic'):
    A = G.Anatomy(model)
    G.reset_strips()
    s = long_top_surface(model, layout, A, ease=.018, sleeve_ease=(.02, .04), hem=.11, sleeve_end=.86, drape=1.0, neck_up=.0)
    L = classify_loops(s)
    for loop in L['sleeve']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        _, _, axis = arm_axis(A, side, upper=False)
        G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .028, rows=3, part=1, inward=.012)
    G.solidify(s, .0025)
    b = ItemBuilder(model, item_id, 'top')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    ivory, wine, dark = cloth.srgb('#e8dfcb'), cloth.srgb('#6d1424'), cloth.srgb('#24161e')
    diamonds = (np.abs(((x + .5) / .06) % 1 - .5) + np.abs(((y) / .08) % 1 - .5)) < .18
    alb = ivory * (1 + .05 * (fbm(p, 20, 3, 4) - .5))[:, None]
    alb = cloth.lin_mix(alb, ivory * .9, diamonds * .6)
    cuffs = (part > .5) & (part < 1.5)
    alb = np.where(cuffs[:, None], wine, alb)
    piping = smoothstep(.003, .0015, np.abs(y - (A.h['Hips'][1] - .11 + .02))) * (part < .5)
    alb = cloth.lin_mix(alb, wine, piping)
    alb = np.where((part > 1.5)[:, None], alb * .7, alb)
    rough = np.where(cuffs, .5, .45)
    hfn = fabric_height(n, 'satin', .0028)

    def height(q):
        puff = np.sin(np.arctan2(q[:, 0], q[:, 2]) * 22) * .0006
        return hfn(q) + puff + diamonds * .0001
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    mat = tex_material(b, 'tunic', a, nm, orm, sheen=((.6, .55, .45), .35))
    b.derived('tunic', s, mat)
    neck_c = A.h['Neck'] + np.array([0, .005, 0])
    rp, rt, ru = ruff_mesh(A, neck_c)
    ruff = flat_material(b, 'ruff', '#efe8d8', roughness=.6)
    b.bound('ruff', rp, rt, ru, ruff, bone='Spine2')
    pom = flat_material(b, 'pompom', '#6d1424', roughness=.9)
    pp, pn, pt = [], [], []
    for i, yy in enumerate((A.h['Spine2'][1] + .06, A.h['Spine1'][1] + .04, A.h['Spine'][1] + .03)):
        # Fica à frente da túnica: procura a superfície mais à frente na altura.
        sel = (np.abs(s.pos[:, 0]) < .02) & (np.abs(s.pos[:, 1] - yy) < .02) & (s.part < .5)
        zf = s.pos[sel, 2].max() if sel.any() else .15
        ps, ns, ts = sphere_mesh(np.array([0, yy, zf + .016]), .02)
        pt.append(ts + sum(len(q) for q in pp))
        pp.append(ps)
        pn.append(ns)
    b.bound('pompoms', np.vstack(pp), np.vstack(pt), np.zeros((sum(len(q) for q in pp), 2)), pom, nrm=np.vstack(pn), bone='Spine2')
    return b.save({'hides': ['chest', 'belly', 'upperarm_a', 'upperarm_b', 'upperarm_c', 'upperarm_d', 'forearm_a', 'forearm_b']})


# ------------------------------------------------------------------------ bottoms

def plain_shorts(model, layout, item_id='bottom_shorts', color='#262c3a'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, hem_y, top = shorts_surface(model, layout, A, length=.45, ease=(.004, .018))
    for loop in classify_loops(s)['hem']:
        G.band(s, loop, lambda P: np.tile([0., 1, 0], (len(P), 1)), .03, rows=3, part=1, inward=.002)
    G.solidify(s, .0022)
    b = ItemBuilder(model, item_id, 'bottom')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x, y = p[:, 0], p[:, 1]
    alb = neutral(p, .92)
    seam = smoothstep(.0022, .0008, np.abs(np.abs(x) - (.155 - (top - y) * .12))) * (part < .5)
    hem = smoothstep(.002, .0008, np.abs(y - hem_y - .014)) * (np.abs(n[:, 1]) < .7) * (part < .5)
    alb *= (1 - .18 * np.clip(seam + hem, 0, 1))[:, None]
    alb = np.where((part > .5)[:, None] & (part < 1.5)[:, None], alb * .9, alb)
    alb = np.where((part > 1.5)[:, None], alb * .7, alb)
    rough = np.where(part > .5, .8, .66)
    waist = part > .5
    hfn = fabric_height(n, 'knit', .0016, lambda q: (seam + hem) * -.0002)

    def height(q):
        return np.where(waist, cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .004)), hfn(q))
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    mat = tex_material(b, 'shorts', a, nm, orm, color=color, tint='main', sheen=((.3, .3, .35), .6))
    b.derived('shorts', s, mat)
    return b.save({'hides': ['hips', 'thigh_a', 'thigh_b']})


def pants_surface(model, layout, A, end_t=.93, waist=.05, ease_hip=.004, ease_knee=.012, ease_ankle=.006):
    c = model.coords
    top = A.h['Hips'][1] + waist

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
    amount = np.where(shin, ease_knee + (ease_ankle - ease_knee) * (t / end_t) ** 1.5,
                      np.where(thigh, ease_hip + (ease_knee - ease_hip) * t, ease_hip))
    G.offset(model, s, amount)
    G.smooth(s, 12, keep_boundary=True)
    G.push_out(model, s, .003)
    L = classify_loops(s)
    for loop in L['leg']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (k - a) / np.linalg.norm(k - a)
        G.straighten(s, loop, k + (a - k) * (end_t - .02), axis)
    for loop in L['hem']:
        G.straighten(s, loop, np.array([0, top, 0]), [0, 1, .12])
    G.smooth(s, 3, keep_boundary=True)
    G.push_out(model, s, .003)
    return s, top


def drawstrings(A, top, z_front):
    from hair import tube_mesh
    paths, radii = [], []
    for sx in (-.012, .012):
        t = np.linspace(0, 1, 10)
        path = np.stack([np.full_like(t, sx) + sx * .3 * t, top - .008 - t * .045, z_front + .006 + .004 * np.sin(t * 3)], 1)
        paths.append(path)
        radii.append(np.full(len(t), .0022))
    pos, nrm, uv, tris, _ = tube_mesh(paths, radii, sides=6)
    return pos, nrm, tris


def joggers(model, layout, item_id='bottom_joggers', color='#1e2230'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, top = pants_surface(model, layout, A, end_t=.9, ease_hip=.008, ease_knee=.036, ease_ankle=.014)
    L = classify_loops(s)
    for loop in L['hem']:
        G.band(s, loop, lambda P: np.tile([0., 1, 0], (len(P), 1)), .035, rows=3, part=1, inward=.002)
    for loop in L['leg']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        k, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (a - k) / np.linalg.norm(a - k)
        G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .035, rows=3, part=1, inward=.004)
    G.solidify(s, .0024)
    b = ItemBuilder(model, item_id, 'bottom')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x, y = p[:, 0], p[:, 1]
    alb = neutral(p, .88)
    seam = smoothstep(.0022, .0008, np.abs(np.abs(n[:, 0]) - .97)) * 0
    alb = np.where((part > .5)[:, None] & (part < 1.5)[:, None], alb * .9, alb)
    alb = np.where((part > 1.5)[:, None], alb * .7, alb)
    rough = np.full(len(p), .85)
    trim = part > .5
    knee_y = A.h['LeftLeg'][1]
    ankle_y = A.h['LeftFoot'][1]

    def extra(q):
        # Pregas: atrás do joelho e franzido acima do punho.
        knee = np.exp(-((q[:, 1] - knee_y) / .05) ** 2) * np.sin(q[:, 1] * 2 * np.pi * 35 + fbm(q, 20, 2, 3) * 4) * .0016
        bunch = smoothstep(ankle_y + .2, ankle_y + .1, q[:, 1]) * np.sin(q[:, 1] * 2 * np.pi * 45 + fbm(q, 25, 2, 6) * 6) * .0018
        return knee + bunch
    hfn = fabric_height(n, 'fleece', .002, extra)

    def height(q):
        return np.where(trim, cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .003)), hfn(q))
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    mat = tex_material(b, 'joggers', a, nm, orm, color=color, tint='main', sheen=((.35, .35, .4), .7))
    b.derived('joggers', s, mat)
    zf = s.pos[(np.abs(s.pos[:, 0]) < .02) & (np.abs(s.pos[:, 1] - top + .01) < .015), 2].max()
    dp, dn, dt = drawstrings(A, top, zf)
    cord = flat_material(b, 'cord', '#efefea', roughness=.7)
    b.bound('drawstrings', dp, dt, np.zeros((len(dp), 2)), cord, nrm=dn, bone='Hips')
    return b.save({'hides': ['hips', 'thigh_a', 'thigh_b', 'thigh_c', 'thigh_d', 'shin_a', 'shin_b']})


def clown_pants(model, layout, item_id='bottom_clown_pants'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, top = pants_surface(model, layout, A, end_t=.88, ease_hip=.008, ease_knee=.03, ease_ankle=.055)
    for loop in classify_loops(s)['hem']:
        G.band(s, loop, lambda P: np.tile([0., 1, 0], (len(P), 1)), .03, rows=3, part=1, inward=.002)
    G.solidify(s, .0025)
    b = ItemBuilder(model, item_id, 'bottom')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    cream, wine = cloth.srgb('#e6dcc6'), cloth.srgb('#5e1222')
    stripes = cloth.triplanar(p, n, lambda u, v: smoothstep(.15, .35, np.abs(((u / .045) % 1) - .5)))
    alb = cloth.lin_mix(cream, wine, stripes) * (1 + .05 * (fbm(p, 20, 3, 4) - .5))[:, None]
    alb = np.where((part > .5)[:, None] & (part < 1.5)[:, None], np.array([.12, .08, .1]), alb)
    alb = np.where((part > 1.5)[:, None], alb * .7, alb)
    rough = np.where(part > .5, .6, .5)
    hfn = fabric_height(n, 'satin', .003, lambda q: np.sin(q[:, 1] * 2 * np.pi * 9 + fbm(q, 10, 2, 2) * 8) * .0015)
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, hfn)
    mat = tex_material(b, 'pants', a, nm, orm, sheen=((.5, .45, .4), .4))
    b.derived('pants', s, mat)
    return b.save({'hides': ['hips', 'thigh_a', 'thigh_b', 'thigh_c', 'thigh_d', 'shin_a', 'shin_b']})


# -------------------------------------------------------------------------- socks

def socks_plain(model, layout, item_id, color, height_t, hides):
    A = G.Anatomy(model)
    G.reset_strips()

    def ok(v):
        b = A.bone[v]
        shin = np.isin(b, ('LeftLeg', 'RightLeg')) & (A.t[v] > height_t)
        foot = np.isin(b, ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'))
        return (shin | foot).all()
    s = G.surface(model, G.select(layout, ok))
    G.offset(model, s, .0018)
    G.smooth(s, 2, keep_boundary=True)
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
    knee_y, ankle_y = A.h['LeftLeg'][1], A.h['LeftFoot'][1]
    top = knee_y - (knee_y - ankle_y) * height_t
    cuff = (p[:, 1] > top - .025) & (part < 1.5)
    heel_toe = np.zeros(len(p))
    for side, sgn in (('Left', 1), ('Right', -1)):
        ankle, f, _ = foot_frame(A, side)
        fw = (p - ankle) @ f
        heel_toe = np.maximum(heel_toe, (np.sign(p[:, 0]) == sgn) * (smoothstep(.12, .15, fw) + smoothstep(-.04, -.06, fw)) * (p[:, 1] < .06))
    alb = neutral(p, .95, .03) * (1 - .06 * heel_toe)[:, None]
    alb = np.where((part > 1.5)[:, None], alb * .8, alb)
    rough = np.full(len(p), .88)
    cuff_c = cuff

    def height(q):
        h = cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .0024)) * 1.1
        h = h + cuff_c * cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .0032)) * 1.4
        return h + (fbm(q, 60, 2, 8) - .5) * .0006
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    mat = tex_material(b, 'socks', a, nm, orm, color=color, tint='main', sheen=((.4, .4, .4), .7))
    b.derived('socks', s, mat, weight_smooth=1)
    return b.save({'hides': hides})


def socks_crew(model, layout):
    return socks_plain(model, layout, 'socks_crew', '#f4f4f0', .74, ['shin_d', 'feet'])


def socks_football_plain(model, layout):
    return socks_plain(model, layout, 'socks_football', '#f1f1ec', .16, ['shin_b', 'shin_c', 'shin_d', 'feet'])


# -------------------------------------------------------------------------- shoes

def shoe_texture(A, bake, base, sole_band=None, laces='#fbfbf9', lace_gap='#9a9da6', eyestay=None, heel=None, toe=None):
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    albedo = np.tile(np.array(base, float), (len(p), 1))
    lace_m = np.zeros(len(p))
    accent = np.zeros(len(p))
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = np.sign(p[:, 0]) == sign
        rel = p - ankle
        fw, lt, up = rel @ f, rel @ lat, p[:, 1]
        lace = (np.abs(lt) < .019) * (fw > -.005) * (fw < .11) * (n[:, 1] > .25)
        rows = smoothstep(.34, .2, np.abs((fw / .011) % 1 - .5)) * smoothstep(.017, .012, np.abs(lt))
        es = smoothstep(.0035, .0018, np.abs(np.abs(lt) - .02)) * (fw > -.01) * (fw < .115) * (n[:, 1] > .2)
        albedo[m] = cloth.lin_mix(albedo[m], cloth.srgb(lace_gap), (lace * (1 - rows) * .85)[m])
        albedo[m] = cloth.lin_mix(albedo[m], cloth.srgb(laces), (lace * rows)[m])
        lace_m[m] = (lace * rows)[m]
        side_panel = (np.abs(n[:, 1]) < .8) * smoothstep(.024, .03, up) * (1 - smoothstep(.06, .07, up)) * (fw > -.06) * (fw < .09)
        swoop = smoothstep(.007, .004, np.abs(up - (.05 - fw * .12 - .01 * np.sin(fw * 50)))) * (np.abs(n[:, 1]) < .85) * (fw > -.05) * (fw < .1)
        accent[m] = np.maximum(swoop, es * (eyestay is not None))[m]
        if heel is not None:
            hc = smoothstep(-.035, -.05, fw) * (up < .1)
            albedo[m] = cloth.lin_mix(albedo[m], cloth.srgb(heel), hc[m])
        if toe is not None:
            tc = smoothstep(.1, .13, fw) * (up < .06)
            albedo[m] = cloth.lin_mix(albedo[m], cloth.srgb(toe), tc[m])
    albedo = np.where((part > 1.5)[:, None], albedo * .8, albedo)
    return p, n, albedo, lace_m, accent


def sneakers(model, layout, item_id='shoes_sneakers', accent_color='#7c5ce0', hightop=False, base='#f3f3f0', main_tint=None):
    A = G.Anatomy(model)
    G.reset_strips()
    s = shoe_shell(model, layout, A, collar_t=.62 if hightop else .9, ease=.0065 if hightop else .0055)
    b = ItemBuilder(model, item_id, 'shoes')
    bake = cloth.bake_surface(s, 1024)
    tint_upper = main_tint is not None
    p, n, albedo, lace_m, accent = shoe_texture(A, bake, (.8, .8, .8) if tint_upper else cloth.srgb(base),
                                                eyestay=True, toe='#ffffff' if hightop else None,
                                                lace_gap='#5a5a5a' if tint_upper else '#9a9da6')
    lace_c, acc_c = lace_m, accent

    def height(q):
        return (fbm(q, 900, 2, 5) - .5) * .00008 + lace_c * .0012 + acc_c * .00025 + (fbm(q, 120, 2, 9) - .5) * .0002
    rough = np.full(len(p), .45 if not tint_upper else .55)
    a, nm, orm = cloth.finish(bake, np.clip(albedo, 0, 1), rough, height)
    if tint_upper:
        upper = tex_material(b, 'upper', a, nm, orm, color=main_tint, tint='main', clearcoat=(.2, .4))
    else:
        upper = tex_material(b, 'upper', a, nm, orm, clearcoat=(.25, .35))
    b.derived('upper', s, upper, weight_smooth=2)
    # Detalhe recolorível (swoosh original + ilhoses).
    rgba = np.zeros((len(p), 4))
    rgba[:, :3] = .95
    rgba[:, 3] = accent if not tint_upper else 0
    if not tint_upper:
        decal(b, s, bake, rgba, 'accent', roughness=.45, tint='accent', color=accent_color)
    sole_mat = flat_material(b, 'sole', '#f2f2ee', roughness=.6)
    trim_mat = flat_material(b, 'sole_trim', '#c9c9c4', roughness=.8)
    for side, sign in (('Left', 1), ('Right', -1)):
        pos, uv, tris, outline, center = sole_mesh(s, sign, y_bottom=-.011, y_top=.024, flare=.0045)
        b.bound(f'sole_{side}', pos, tris, uv, sole_mat, bone=f'{side}Foot')
        # Borracha da sola (faixa inferior escura).
        pos2, uv2, tris2, _, _ = sole_mesh(s, sign, y_bottom=-.0115, y_top=-.004, flare=.0052)
        b.bound(f'outsole_{side}', pos2, tris2, uv2, trim_mat, bone=f'{side}Foot')
    hides = ['feet'] + (['shin_d'] if hightop else [])
    return b.save({'hides': hides, 'lift': .011})


def hightops(model, layout):
    return sneakers(model, layout, 'shoes_hightops', hightop=True, main_tint='#1c1f29')


def clown_shoes(model, layout, item_id='shoes_clown'):
    A = G.Anatomy(model)
    G.reset_strips()
    s = shoe_shell(model, layout, A, collar_t=.9, ease=.009)
    # Alonga e arredonda a ponta: escala à frente do tornozelo.
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = np.sign(s.pos[:, 0]) == sign
        rel = s.pos[m] - ankle
        fw = rel @ f
        k = smoothstep(.0, .14, fw)
        grow = 1 + .55 * k
        lt = rel @ lat
        up = s.pos[m, 1]
        new = ankle + np.outer(fw * grow, f) + np.outer(lt * (1 + .35 * k), lat)
        new[:, 1] = up + k * np.clip(up - .02, 0, None) * .7
        s.pos[m] = new
    G.smooth(s, 8, keep_boundary=True)
    s.pos[:, 1] = np.maximum(s.pos[:, 1], .014)
    b = ItemBuilder(model, item_id, 'shoes')
    bake = cloth.bake_surface(s, 1024)
    p = bake.pos[bake.mask].astype(np.float64)
    part = bake.at('part')[:, 0]
    wine, black = cloth.srgb('#4a0c18'), cloth.srgb('#121014')
    alb = np.tile(wine, (len(p), 1))
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = np.sign(p[:, 0]) == sign
        fw = (p - ankle) @ f
        alb[m] = cloth.lin_mix(alb[m], black, (smoothstep(.03, .02, fw) * (p[:, 1] < .2))[m])
    alb = np.where((part > 1.5)[:, None], black, alb)

    def height(q):
        return (fbm(q, 600, 2, 3) - .5) * .00005 + (fbm(q, 40, 2, 5) - .5) * .0005
    a, nm, orm = cloth.finish(bake, alb, np.full(len(p), .25), height)
    upper = tex_material(b, 'leather', a, nm, orm, clearcoat=(.9, .08))
    b.derived('upper', s, upper, weight_smooth=2)
    sole_mat = flat_material(b, 'sole', '#0f0d10', roughness=.5)
    for side, sign in (('Left', 1), ('Right', -1)):
        pos, uv, tris, _, _ = sole_mesh(s, sign, y_bottom=-.012, y_top=.02, flare=.006)
        b.bound(f'sole_{side}', pos, tris, uv, sole_mat, bone=f'{side}Foot')
    return b.save({'hides': ['feet'], 'lift': .012})
