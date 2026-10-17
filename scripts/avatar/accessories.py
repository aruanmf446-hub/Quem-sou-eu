"""Acessórios e arte corporal: boné, faixa, óculos, corrente, munhequeira, relógio, tatuagem e pintura."""
from __future__ import annotations

import numpy as np
from PIL import Image

import cloth
import garments as G
import overlays
from garments import Surface
from hair import scalp_line, tube_mesh
from items import ItemBuilder
from model import vertex_normals
from raster import Bake, dilate, fbm, smoothstep
from wardrobe2 import flat_material, lin, tex_material, neutral


def select_head(layout, pred):
    return [corners for mat, corners in layout.faces if mat == 'head' and pred(np.array([v for v, _ in corners]))]


def plane_fit(P):
    c = P.mean(0)
    _, _, vt = np.linalg.svd(P - c)
    n = vt[2]
    return c, n if n[1] > 0 else -n


def azimuth(L, P):
    rel = P - L.center
    return np.abs(np.degrees(np.arctan2(rel[:, 0], rel[:, 2])))


def merge(parts):
    pos, nrm, tris = [], [], []
    off = 0
    for p, n, t in parts:
        pos.append(p)
        nrm.append(n)
        tris.append(t + off)
        off += len(p)
    return np.vstack(pos), np.vstack(nrm), np.vstack(tris)


def torus(center, axis, R, r, seg=10, sides=6):
    axis = axis / np.linalg.norm(axis)
    ref = np.array([0, 1., 0]) if abs(axis[1]) < .9 else np.array([1., 0, 0])
    u = np.cross(axis, ref); u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    pos, nrm, tris = [], [], []
    for i in range(seg):
        a = 2 * np.pi * i / seg
        c = center + R * (np.cos(a) * u + np.sin(a) * v)
        radial = np.cos(a) * u + np.sin(a) * v
        for j in range(sides):
            b = 2 * np.pi * j / sides
            d = np.cos(b) * radial + np.sin(b) * axis
            pos.append(c + d * r)
            nrm.append(d)
    for i in range(seg):
        for j in range(sides):
            a = i * sides + j
            b = ((i + 1) % seg) * sides + j
            c = i * sides + (j + 1) % sides
            d = ((i + 1) % seg) * sides + (j + 1) % sides
            tris += [(a, b, c), (b, d, c)]
    return np.array(pos), np.array(nrm), np.array(tris)


def cylinder(center, axis, radius, height, seg=24, caps=True):
    axis = axis / np.linalg.norm(axis)
    ref = np.array([0, 1., 0]) if abs(axis[1]) < .9 else np.array([1., 0, 0])
    u = np.cross(axis, ref); u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    pos, nrm, tris = [], [], []
    for h in (0, height):
        for i in range(seg):
            a = 2 * np.pi * i / seg
            d = np.cos(a) * u + np.sin(a) * v
            pos.append(center + d * radius + axis * h)
            nrm.append(d)
    for i in range(seg):
        a, b = i, (i + 1) % seg
        tris += [(a, b, a + seg), (b, b + seg, a + seg)]
    if caps:
        for h, sgn in ((0, -1), (height, 1)):
            base = len(pos)
            pos.append(center + axis * h)
            nrm.append(axis * sgn)
            for i in range(seg):
                a = 2 * np.pi * i / seg
                pos.append(center + (np.cos(a) * u + np.sin(a) * v) * radius + axis * h)
                nrm.append(axis * sgn)
            for i in range(seg):
                a, b = base + 1 + i, base + 1 + (i + 1) % seg
                tris.append((base, b, a) if sgn > 0 else (base, a, b))
    return np.array(pos), np.array(nrm), np.array(tris)


def head_surface(model, layout, pred):
    return G.surface(model, select_head(layout, pred))


# ------------------------------------------------------------------------- boné

def cap(model, layout, item_id='cap_snapback', color='#1d2433'):
    L = overlays.Landmarks(model)
    G.reset_strips()
    ey = L.eye_y
    c = model.coords

    def band_line(P):
        aaz = azimuth(L, P)
        return np.interp(aaz, [0, 60, 100, 140, 180], [ey + .05, ey + .045, ey + .03, ey + .005, ey - .005])

    def ok(v):
        P = c[v]
        return (P[:, 1] > band_line(P) - .002).all()
    s = head_surface(model, layout, ok)
    G.offset(model, s, .016)
    G.smooth(s, 25, keep_boundary=True)
    G.push_out(model, s, .014)
    loop = G.loops(s)[0]
    pc, pn = plane_fit(s.pos[loop])
    G.straighten(s, loop, pc, pn, rings=4)
    G.smooth(s, 4, keep_boundary=True)
    G.push_out(model, s, .012)
    G.solidify(s, .003)
    b = ItemBuilder(model, item_id, 'headwear')
    bake = cloth.bake_surface(s, 1024)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    az = np.degrees(np.arctan2(p[:, 0] - L.center[0], p[:, 2] - L.center[2]))
    seams = smoothstep(1.2, .4, np.abs(((az + 30) % 60) - 30) * np.hypot(p[:, 0] - L.center[0], p[:, 2] - L.center[2]) * 60)
    alb = neutral(p, .9)
    alb *= (1 - .25 * seams)[:, None]
    alb = np.where((part > 1.5)[:, None], alb * .7, alb)

    def height(q):
        return cloth.triplanar(q, n, cloth.twill) * 1.5 + seams * -.0004
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), np.full(len(p), .7), height)
    crown_mat = tex_material(b, 'crown', a, nm, orm, color=color, tint='main')
    b.derived('crown', s, crown_mat)
    # Aba reta à frente, a partir da borda inferior frontal.
    P = s.pos[loop]
    aaz = azimuth(L, P)
    front = aaz < 75
    idx = np.flatnonzero(front)
    ang = np.degrees(np.arctan2(P[idx, 0] - L.center[0], P[idx, 2] - L.center[2]))
    order = idx[np.argsort(ang)]
    edge = P[order]
    k = len(edge)
    ts = np.linspace(-1, 1, k)
    depth = .078 * np.sqrt(np.clip(1 - ts ** 2, 0, 1))
    rad = edge[:, [0, 2]] - L.center[[0, 2]]
    rad /= np.linalg.norm(rad, axis=1, keepdims=True)
    rows = 6
    top_pos, bot_pos = [], []
    for r in range(rows):
        f = r / (rows - 1)
        pts = edge.copy()
        pts[:, 0] += rad[:, 0] * depth * f
        pts[:, 2] += rad[:, 1] * depth * f
        pts[:, 1] += -.004 * f - .002
        top_pos.append(pts)
        bot_pos.append(pts - np.array([0, .004, 0]))
    top_pos, bot_pos = np.vstack(top_pos), np.vstack(bot_pos)
    tris = []
    for r in range(rows - 1):
        for i in range(k - 1):
            a, bb = r * k + i, r * k + i + 1
            c2, d2 = a + k, bb + k
            tris += [(a, bb, c2), (bb, d2, c2)]
    tris = np.array(tris)
    # Ajusta orientação: a face de cima aponta para +y.
    nn = vertex_normals(top_pos, tris)
    if nn[:, 1].mean() < 0:
        tris = tris[:, ::-1]
    N = len(top_pos)
    rim = []
    outer = [(rows - 1) * k + i for i in range(k)]
    for i in range(k - 1):
        a, bb = outer[i], outer[i + 1]
        rim += [(a, bb + N, bb), (a, a + N, bb + N)]
    rim = np.array(rim)
    if (vertex_normals(np.vstack([top_pos, bot_pos]), rim)[outer][:, [0, 2]] * rad).sum() < 0:
        rim = rim[:, ::-1]
    brim_pos = np.vstack([top_pos, bot_pos])
    brim_tris = np.vstack([tris, tris[:, ::-1] + N, rim])
    brim_mat = flat_material(b, 'brim', color, roughness=.65, tint='main')
    b.bound('brim', brim_pos, brim_tris, np.zeros((len(brim_pos), 2)), brim_mat, bone='Head')
    top = s.pos[s.pos[:, 1].argmax()]
    bp, bn, bt = cylinder(top - np.array([0, .003, 0]), np.array([0, 1., 0]), .006, .006)
    b.bound('button', bp, bt, np.zeros((len(bp), 2)), brim_mat, nrm=bn, bone='Head')
    return b.save({})


def headband(model, layout, item_id='headband', color='#f2f2ee'):
    L = overlays.Landmarks(model)
    G.reset_strips()
    ey = L.eye_y
    c = model.coords

    def line(P):
        aaz = azimuth(L, P)
        return np.interp(aaz, [0, 60, 95, 130, 180], [ey + .056, ey + .05, ey + .045, ey + .04, ey + .03])

    def ok(v):
        P = c[v]
        d = P[:, 1] - line(P)
        ear = (azimuth(L, P) > 75) & (azimuth(L, P) < 115) & (P[:, 1] < ey + .035)
        return ((d > -.024) & (d < .004) & ~ear).all()
    s = head_surface(model, layout, ok)
    G.offset(model, s, .007)
    G.smooth(s, 6, keep_boundary=True)
    G.push_out(model, s, .006)
    for loop in G.loops(s):
        P = s.pos[loop]
        pc, pn = plane_fit(P)
        G.straighten(s, loop, pc, pn, rings=2)
    G.smooth(s, 2, keep_boundary=True)
    G.push_out(model, s, .005)
    G.solidify(s, .004)
    b = ItemBuilder(model, item_id, 'headwear')
    bake = cloth.bake_surface(s, 1024)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    alb = neutral(p, .93)
    alb = np.where((part > 1.5)[:, None], alb * .8, alb)

    def height(q):
        return cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .0028)) * 1.6 + (fbm(q, 1500, 2, 4) - .5) * .0002
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), np.full(len(p), .92), height)
    mat = tex_material(b, 'band', a, nm, orm, color=color, tint='main', sheen=((.5, .5, .5), .8))
    b.derived('band', s, mat)
    return b.save({})


# ------------------------------------------------------------------------- óculos

def temple_paths(L, ex, y, z_front):
    paths = []
    for sgn in (1, -1):
        ear = np.array([sgn * .074, y + .002, L.center[2] - .02])
        start = np.array([sgn * ex, y, z_front])
        mid = np.array([sgn * (ex + .006), y + .003, (z_front + ear[2]) / 2])
        t = np.linspace(0, 1, 12)[:, None]
        path = (1 - t) ** 2 * start + 2 * (1 - t) * t * mid + t ** 2 * ear
        path = np.vstack([path, ear + np.array([0, -.012, -.01])])
        paths.append(path)
    return paths


def glasses_sport(model, layout, item_id='glasses_sport'):
    L = overlays.Landmarks(model)
    ey = L.eye_y
    b = ItemBuilder(model, item_id, 'eyewear')
    zc = L.eyeL[2] + .036
    R = .12
    axis_z = zc - R
    nu, nv = 42, 8
    phis = np.linspace(-.68, .68, nu)
    pos, nrm = [], []
    for layer, dr in enumerate((0, -.0025)):
        for i, ph in enumerate(phis):
            top = ey + .019 - .004 * (abs(ph) / .68) ** 2
            bottom = ey - .021 + .012 * (abs(ph) / .68) ** 2 + .011 * np.exp(-(ph / .09) ** 2)
            for j in range(nv):
                f = j / (nv - 1)
                y = bottom + (top - bottom) * f
                rr = R + dr - .006 * (2 * f - 1) ** 2
                pos.append((np.sin(ph) * rr, y, axis_z + np.cos(ph) * rr))
                nrm.append((np.sin(ph), 0, np.cos(ph)))
    pos, nrm = np.array(pos), np.array(nrm)
    tris = []
    for layer in range(2):
        base = layer * nu * nv
        for i in range(nu - 1):
            for j in range(nv - 1):
                a = base + i * nv + j
                bb = a + nv
                tri = [(a, bb, a + 1), (bb, bb + 1, a + 1)]
                tris += tri if layer == 0 else [t[::-1] for t in tri]
    tris = np.array(tris)
    nrm[nu * nv:] *= -1
    lens = b.glb.material('lens', color=(*lin('#5d6fb8'), 1), metallic=.85, roughness=.06, clearcoat=(1, .02))
    b.bound('lens', pos, tris, np.zeros((len(pos), 2)), lens, nrm=nrm, bone='Head', rigid=True)
    # Armação superior e hastes.
    top_path = [np.array([(np.sin(ph) * (R + .0015), ey + .02 - .004 * (abs(ph) / .68) ** 2, axis_z + np.cos(ph) * (R + .0015)) for ph in phis])]
    paths = top_path + temple_paths(L, np.sin(.68) * R, ey + .012, axis_z + np.cos(.68) * R)
    radii = [np.full(len(p), .0026) for p in paths]
    fp, fn, fuv, ft, _ = tube_mesh(paths, radii, sides=6)
    frame = flat_material(b, 'frame', '#16171b', roughness=.35)
    b.bound('frame', fp, ft, fuv, frame, nrm=fn, bone='Head', rigid=True)
    return b.save({})


def glasses_round(model, layout, item_id='glasses_round'):
    L = overlays.Landmarks(model)
    ey, ex = L.eye_y, L.eye_x
    b = ItemBuilder(model, item_id, 'eyewear')
    zf = L.eyeL[2] + .03
    rr = .021
    parts = []
    lens_parts = []
    for sgn in (1, -1):
        center = np.array([sgn * (ex + .002), ey - .001, zf])
        parts.append(torus(center, np.array([sgn * .12, 0, 1.]), rr, .0014, 28, 6))
        lp, ln, lt = cylinder(center - np.array([0, 0, .0006]), np.array([sgn * .12, 0, 1.]), rr, .0012, 28)
        lens_parts.append((lp, ln, lt))
    t = np.linspace(0, 1, 10)[:, None]
    a, c = np.array([.0, ey + .008, zf + .004]), np.array([-(ex - rr + .002), ey + .004, zf])
    bridge = np.vstack([(1 - t) ** 2 * c + 2 * (1 - t) * t * a + t ** 2 * (c * [-1, 1, 1])])
    paths = [bridge] + temple_paths(L, ex + rr + .001, ey + .004, zf - .002)
    fp, fn, _, ft, _ = tube_mesh(paths, [np.full(len(p), .0013) for p in paths], sides=6)
    parts.append((fp, fn, ft))
    pos, nrm, tris = merge(parts)
    metal = b.glb.material('frame', color=(*lin('#b08d57'), 1), metallic=1, roughness=.25)
    b.bound('frame', pos, tris, np.zeros((len(pos), 2)), metal, nrm=nrm, bone='Head', rigid=True)
    lp, ln, lt = merge(lens_parts)
    glass = b.glb.material('lens', color=(.9, .95, 1, .14), roughness=.02, alpha=('BLEND', 0), clearcoat=(1, .02))
    b.bound('lens', lp, lt, np.zeros((len(lp), 2)), glass, nrm=ln, bone='Head', rigid=True)
    return b.save({})


# ------------------------------------------------------------------------- corrente

def chain(model, layout, item_id='chain_gold'):
    from wardrobe import nipple_centers  # noqa: F401 (garante corpo alisado disponível)
    A = G.Anatomy(model)
    b = ItemBuilder(model, item_id, 'neck')
    neck = A.h['Neck']
    a = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    rx, rz = .078, .072
    base_y = neck[1] - .012
    dip = .09
    path = np.stack([rx * np.sin(a), base_y - dip * np.clip(np.cos(a), 0, 1) ** 2.2, neck[2] + .005 + rz * np.cos(a)], 1)
    # Afasta da pele (por cima de camisas justas).
    for _ in range(3):
        ids, bary, off = model.bind(path, coords=model.smoothed())
        nn = (model.normals[ids] * bary[..., None]).sum(1)
        nn /= np.linalg.norm(nn, axis=1, keepdims=True)
        d = (off * nn).sum(1)
        path = path + nn * np.maximum(.016 - d, 0)[:, None]
    seglen = np.linalg.norm(np.diff(np.vstack([path, path[:1]]), axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seglen)])
    total = cum[-1]
    step = .0068
    parts = []
    for i, s_ in enumerate(np.arange(0, total - step / 2, step)):
        p = np.array([np.interp(s_, cum, np.append(path[:, k], path[0, k])) for k in range(3)])
        q = np.array([np.interp(s_ + .001, cum, np.append(path[:, k], path[0, k])) for k in range(3)])
        tdir = (q - p) / max(np.linalg.norm(q - p), 1e-9)
        out = p - np.array([0, p[1], neck[2]])
        out[1] = 0
        out /= max(np.linalg.norm(out), 1e-9)
        axis = np.cross(tdir, out) if i % 2 == 0 else out
        parts.append(torus(p, axis, .0042, .0011, 10, 5))
    front = path[np.argmin(path[:, 1])]
    # Pingente: losango facetado.
    c0 = front + np.array([0, -.016, .004])
    dp = np.array([[0, .012, 0], [.008, 0, 0], [0, -.012, 0], [-.008, 0, 0], [0, 0, .004], [0, 0, -.003]]) + c0
    dt = np.array([[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4], [1, 0, 5], [2, 1, 5], [3, 2, 5], [0, 3, 5]])
    parts.append((dp, vertex_normals(dp, dt), dt))
    pos, nrm, tris = merge(parts)
    gold = b.glb.material('gold', color=(*lin('#e2b450'), 1), metallic=1, roughness=.22)
    b.bound('chain', pos, tris, np.zeros((len(pos), 2)), gold, nrm=nrm)
    return b.save({})


# ------------------------------------------------------------------------- pulso

def wrist_surface(model, layout, A, side, t0, t1, ease):
    bone = f'{side}ForeArm'

    def ok(v):
        return (np.isin(A.bone[v], (bone,)) & (A.t[v] > t0) & (A.t[v] < t1)).all()
    s = G.surface(model, G.select(layout, ok))
    G.offset(model, s, ease)
    G.smooth(s, 4, keep_boundary=True)
    a, f = A.h[bone], A.h[f'{side}Hand']
    axis = (f - a) / np.linalg.norm(f - a)
    for loop in G.loops(s):
        G.straighten(s, loop, s.pos[loop].mean(0), axis, rings=1)
    G.push_out(model, s, ease * .8, smooth_body=False)
    return s, axis


def wristband(model, layout, item_id='wristband', color='#1b8a46'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, axis = wrist_surface(model, layout, A, 'Right', .74, .93, .006)
    G.solidify(s, .004)
    b = ItemBuilder(model, item_id, 'wrist')
    bake = cloth.bake_surface(s, 512)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    alb = neutral(p, .92)
    alb = np.where((part > 1.5)[:, None], alb * .8, alb)

    def height(q):
        return cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .0026)) * 2 + (fbm(q, 1800, 2, 1) - .5) * .0002
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), np.full(len(p), .95), height)
    mat = tex_material(b, 'band', a, nm, orm, color=color, tint='main', sheen=((.5, .5, .5), .8))
    b.derived('band', s, mat, weight_smooth=1)
    return b.save({})


def watch(model, layout, item_id='watch'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, axis = wrist_surface(model, layout, A, 'Left', .78, .93, .0035)
    G.solidify(s, .0025)
    b = ItemBuilder(model, item_id, 'wrist')
    strap = flat_material(b, 'strap', '#17181c', roughness=.55)
    b.derived('strap', s, strap, weight_smooth=1)
    # Caixa do relógio no dorso do punho (lado de fora do braço).
    center_band = s.pos.mean(0)
    out = np.array([1., .25, .15])
    out -= axis * (out @ axis)
    out /= np.linalg.norm(out)
    k = np.argmax((s.pos - center_band) @ out)
    base = s.pos[k] - out * .001
    cp, cn, ct = cylinder(base, out, .017, .0075, 32)
    rp, rn, rt = torus(base + out * .0075, out, .0165, .0016, 32, 6)
    case = b.glb.material('case', color=(*lin('#c8ccd2'), 1), metallic=1, roughness=.2)
    pos, nrm, tris = merge([(cp, cn, ct), (rp, rn, rt)])
    b.bound('case', pos, tris, np.zeros((len(pos), 2)), case, nrm=nrm, bone='LeftForeArm', rigid=True)
    fp, fnn, ft = cylinder(base + out * .0076, out, .0145, .0004, 32)
    face = b.glb.material('face', color=(*lin('#0f1a2a'), 1), metallic=0, roughness=.15, clearcoat=(1, .02))
    b.bound('face', fp, ft, np.zeros((len(fp), 2)), face, nrm=fnn, bone='LeftForeArm', rigid=True)
    # Ponteiros.
    ref = np.cross(out, axis)
    hands = []
    for d, L_, w in ((axis, .011, .0012), (ref, .008, .0016)):
        c0 = base + out * .0082
        quad = np.array([c0 - ref * w * 0, c0 + d * L_, c0 + d * L_ + np.cross(out, d) * w, c0 + np.cross(out, d) * w])
        hands.append((quad, np.tile(out, (4, 1)), np.array([[0, 1, 2], [0, 2, 3]])))
    hp, hn, ht = merge(hands)
    white = b.glb.material('hands', color=(.9, .9, .88, 1), roughness=.4)
    b.bound('hands', hp, ht, np.zeros((len(hp), 2)), white, nrm=hn, bone='LeftForeArm', rigid=True)
    return b.save({})


# ------------------------------------------------------------------------- arte corporal

def tattoo_sleeve(model, layout, item_id='tattoo_sleeve'):
    A = G.Anatomy(model)
    side = 'Right'
    e, w = A.h[f'{side}ForeArm'], A.h[f'{side}Hand']
    axis = (w - e) / np.linalg.norm(w - e)
    length = np.linalg.norm(w - e)
    sel = [(m, corners) for m, corners in layout.faces if m == 'body' and
           all(A.bone[v] == f'{side}ForeArm' and .06 < A.t[v] < .97 for v, _ in corners)]
    faces = [c for _, c in sel]
    tris_v, tris_uv = [], []
    for corners in faces:
        for i in range(1, len(corners) - 1):
            tri = (corners[0], corners[i], corners[i + 1])
            tris_v.append([t[0] for t in tri])
            tris_uv.append([t[1] for t in tri])
    tv, tuv = np.array(tris_v), np.array(tris_uv)
    bake = Bake(2048, tuv, model.coords[tv], model.normals[tv])
    p = bake.pos[bake.mask].astype(np.float64)
    rel = p - e
    l = rel @ axis
    radial = rel - np.outer(l, axis)
    # Referência angular: lado de fora/dorsal do antebraço direito (-x).
    ref = np.array([-1., .2, .1])
    ref -= axis * (ref @ axis)
    ref /= np.linalg.norm(ref)
    ref2 = np.cross(axis, ref)
    r = np.linalg.norm(radial, axis=1) + 1e-9
    ang = np.arctan2(radial @ ref2, radial @ ref)
    u = ang * .035  # comprimento de arco aproximado
    v = l
    ink = np.zeros(len(p))
    line = lambda d, wdt=.0007: smoothstep(wdt, wdt * .4, np.abs(d))
    # Punho: duas linhas e faixa de triângulos.
    for lv in (length * .9, length * .935):
        ink = np.maximum(ink, line(v - lv))
    tri_row = (v > length * .84) & (v < length * .895)
    saw = np.abs(((u / .012) % 1) - .5) * 2
    ink = np.maximum(ink, tri_row * smoothstep(.06, .0, (v - length * .84) / (length * .055) - saw) * smoothstep(-.02, .05, (v - length * .84) / (length * .055) - saw + .4))
    # Mandala de lótus no meio (lado de fora).
    c_v = length * .55
    du, dv = u, v - c_v
    rho = np.hypot(du, dv)
    psi = np.arctan2(dv, du)
    petal1 = .028 * (.55 + .45 * np.abs(np.cos(4 * psi)))
    petal2 = .04 * (.6 + .4 * np.abs(np.cos(4 * psi + np.pi / 4)))
    ink = np.maximum(ink, line(rho - petal1, .0008))
    ink = np.maximum(ink, line(rho - petal2, .0008) * (rho < .05))
    ink = np.maximum(ink, line(rho - .009, .0007))
    ink = np.maximum(ink, smoothstep(.0045, .0035, rho) * .9)
    dots = (rho > .042) & (rho < .052) & (np.abs(((psi / (2 * np.pi)) * 32) % 1 - .5) < .18) & (np.abs(rho - .047) < .0018)
    ink = np.maximum(ink, dots)
    # Pétalas internas preenchidas com pontilhismo.
    stipple = (fbm(p, 2600, 1, 5) > .62) * (rho < petal1) * (rho > .012) * .8
    ink = np.maximum(ink, stipple)
    # Geometria perto do cotovelo: losangos em faixa.
    band_e = (v > length * .12) & (v < length * .3)
    diam = np.abs(((u / .018) % 1) - .5) + np.abs(((v / .018) % 1) - .5)
    ink = np.maximum(ink, band_e * line(diam - .35, .02))
    ink = np.maximum(ink, line(v - length * .11) + line(v - length * .31))
    # Linhas que conectam os motivos.
    ink = np.maximum(ink, line(u - .0) * (v > length * .31) * (v < c_v - .05))
    ink = np.maximum(ink, line(u - .0) * (v > c_v + .05) * (v < length * .84))
    ink = np.clip(ink, 0, 1) * (.88 + .12 * fbm(p, 400, 2, 9))
    img = np.zeros(bake.mask.shape + (4,), np.float32)
    img[bake.mask, :3] = 1
    img[bake.mask, 3] = ink
    img = dilate(img, bake.mask)
    tex = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGBA')
    b = ItemBuilder(model, item_id, 'bodyart')
    mat = b.glb.material('ink', color=(*lin('#17151b'), 1), base=b.glb.texture(tex, fmt='webp', quality=90), roughness=.5,
                         alpha=('BLEND', 0), extras={'overlay': True})
    b.skin_layer('ink', faces, .0003, mat)
    return b.save({})


def facepaint(model, layout, item_id='facepaint_midnight'):
    bake = overlays.head_bake(model, layout)
    L = overlays.Landmarks(model)
    p = bake.pos[bake.mask].astype(np.float64)
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    ax = np.abs(x)
    ey, ex = L.eye_y, L.eye_x
    mouth = L.mouth_y
    rel = p - L.center
    aaz = np.abs(np.degrees(np.arctan2(rel[:, 0], rel[:, 2])))
    face = (1 - smoothstep(58, 74, aaz)) * smoothstep(L.chin_y - .012, L.chin_y, y) * (1 - smoothstep(ey + .07, ey + .08, y))
    white = np.array([.95, .94, .92])
    black = np.array([.07, .05, .08])
    red = np.array([.62, .05, .12])
    col = np.tile(white, (len(p), 1))
    alpha = face * (.93 + .05 * fbm(p, 200, 2, 3))
    # Losangos verticais atravessando os olhos.
    dia = np.abs(ax - ex) / .016 + np.abs(y - ey - .003) / .05
    dia_m = smoothstep(1.02, .96, dia) * (z > L.eyeL[2] - .03)
    col = cloth.lin_mix(col, black, dia_m)
    # Sorriso vermelho alongado + lábios.
    lips = smoothstep(.15, .5, overlays._bake['lips'])
    smile_y = mouth - .002 + 9 * np.clip(ax - .018, 0, None) ** 2 * 10
    smile = smoothstep(.0045, .003, np.abs(y - smile_y)) * (ax < .06) * (ax > .012) * (z > L.front_z - .08)
    col = cloth.lin_mix(col, red, np.clip(smile + lips, 0, 1))
    # Nariz vermelho.
    nose = smoothstep(.012, .009, np.hypot(x, y - (ey - .043))) * (z > L.front_z - .03)
    col = cloth.lin_mix(col, red, nose)
    # Lágrima preta abaixo do olho esquerdo do personagem.
    tear = smoothstep(.0035, .0025, np.hypot((x - ex) * 1.0, (y - (ey - .035)) * .6)) * (x > 0)
    col = cloth.lin_mix(col, black, tear)
    alpha = np.maximum(alpha, np.clip(smile + nose + dia_m, 0, 1) * face)
    img = np.zeros((overlays.SIZE, overlays.SIZE, 4), np.float32)
    img[bake.mask, :3] = col
    img[bake.mask, 3] = alpha
    img = dilate(img, bake.mask)
    tex = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGBA')
    b = ItemBuilder(model, item_id, 'bodyart')
    mat = b.glb.material('paint', color=(1, 1, 1, 1), base=b.glb.texture(tex, fmt='webp', quality=90), roughness=.55,
                         alpha=('BLEND', 0), extras={'overlay': True})
    faces = overlays.faces_in(layout, model, alpha)
    b.skin_layer('paint', faces, .00045, mat)
    return b.save({})
