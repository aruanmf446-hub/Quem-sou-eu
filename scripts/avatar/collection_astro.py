"""Coleção estilizada: astro (Astrônoma). Registra as peças no REGISTRY de build_items.

Peças: cabelo ondulado longo meio-preso, enfeite de engrenagem, túnica com tabardo, capa curta com capuz
estrelado, calça bufante estrelada, botas com punhos dourados, cinto com bússola e bolsinhas, braçadeiras de
couro e cajado com esfera armilar.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

import cloth
import garments as G
from accessories import cylinder, merge, torus
from items import ItemBuilder
from raster import Bake, fbm, smoothstep
from wardrobe import TORSO, classify_loops, foot_frame, nipple_centers, shoe_shell, sole_mesh
from wardrobe2 import (arm_axis, clear_bottoms, fabric_height, flat_material, hem_ease, lin, sphere_mesh,
                       tex_material)

NAVY = '#1d2b5e'
NAVY_DEEP = '#141d40'
CREAM = '#efe3c8'
GOLD = '#e7b24c'
LEATHER = '#6b4126'
LEATHER_DARK = '#3f2616'


# ---------------------------------------------------------------- utilidades

def gold_material(b, name='gold', roughness=.35):
    return b.glb.material(name, color=(*lin(GOLD), 1), metallic=.9, roughness=roughness)


def frame(u):
    u = np.asarray(u, float) / np.linalg.norm(u)
    ref = np.array([0, 0, 1.]) if abs(u[2]) < .9 else np.array([1., 0, 0])
    e1 = np.cross(u, ref)
    e1 /= np.linalg.norm(e1)
    return u, e1, np.cross(u, e1)


def sd_star(p, r, rf=.45):
    """Estrela de 5 pontas (distância com sinal, ponta para +y)."""
    k1 = np.array([.809016994375, -.587785252292])
    k2 = np.array([-k1[0], k1[1]])
    p = p.copy()
    p[:, 0] = np.abs(p[:, 0])
    p -= 2 * np.maximum(p @ k1, 0)[:, None] * k1
    p -= 2 * np.maximum(p @ k2, 0)[:, None] * k2
    p[:, 0] = np.abs(p[:, 0])
    p[:, 1] -= r
    ba = rf * np.array([-k1[1], k1[0]]) - np.array([0, 1.])
    h = np.clip((p @ ba) / (ba @ ba), 0, r)
    d = p - h[:, None] * ba
    return np.linalg.norm(d, axis=1) * np.sign(p[:, 1] * ba[0] - p[:, 0] * ba[1])


def sd_sparkle(p, r):
    """Brilho de 4 pontas (astroide)."""
    r = np.asarray(r, float)
    a = np.abs(p) / (r[:, None] if r.ndim else r)
    return (a[:, 0] ** .5 + a[:, 1] ** .5 - 1) * r * .5


def _hash(i, j, k=0):
    h = np.sin(i * 127.1 + j * 311.7 + k * 74.7) * 43758.5453
    return h - np.floor(h)


def star_field(X, Y, cell=.05, size=(.008, .014), density=.85, seed=0):
    """Campo de estrelas douradas num plano (X, Y em metros). Retorna (máscara 0..1, altura)."""
    i, j = np.floor(X / cell), np.floor(Y / cell)
    fx, fy = X / cell - i, Y / cell - j
    ox = .3 + .4 * _hash(i, j, seed + 1)
    oy = .3 + .4 * _hash(i, j, seed + 2)
    r = (size[0] + (size[1] - size[0]) * _hash(i, j, seed + 3)) / cell
    kind = _hash(i, j, seed + 4)
    ang = (_hash(i, j, seed + 5) - .5) * .9
    q = np.stack([fx - ox, fy - oy], 1)
    c, s = np.cos(ang), np.sin(ang)
    q = np.stack([q[:, 0] * c - q[:, 1] * s, q[:, 0] * s + q[:, 1] * c], 1)
    d_star = sd_star(q, r)
    d_spark = sd_sparkle(q, r * .9)
    d = np.where(kind < .72, d_star, d_spark)
    present = _hash(i, j, seed + 6) < density
    px = 1 / (cell * 2600)
    m = smoothstep(px, -px, d) * present
    return m, m * .00035


def grid_mesh(P, closed=False, u_range=(0, 1), v_range=(0, 1)):
    """Malha de grade (R, C, 3) com UV retangular. closed: emenda a última coluna na primeira."""
    R, C, _ = P.shape
    cols = C + 1 if closed else C
    pos, uv = [], []
    for r in range(R):
        for c in range(cols):
            pos.append(P[r, c % C])
            uv.append((u_range[0] + (u_range[1] - u_range[0]) * c / (cols - 1),
                       v_range[0] + (v_range[1] - v_range[0]) * r / (R - 1)))
    tris = []
    for r in range(R - 1):
        for c in range(cols - 1):
            a, b_ = r * cols + c, r * cols + c + 1
            tris += [(a, a + cols, b_), (b_, a + cols, b_ + cols)]
    return np.array(pos), np.array(uv), np.array(tris)


def mesh_normals(pos, tris):
    from model import vertex_normals
    return vertex_normals(pos, tris)


def bake_mesh(pos, uv, tris, size=1024, extra=None):
    n = mesh_normals(pos, tris)
    ex = {k: (v[tris] if v.ndim > 1 else v[tris][..., None]).astype(np.float32) for k, v in (extra or {}).items()}
    return Bake(size, uv[tris], pos[tris], n[tris], ex)


def solid_shell(pos, uv, tris, thickness, nrm=None):
    """Dá espessura a uma malha aberta: lado de dentro deslocado e bordas fechadas."""
    n = mesh_normals(pos, tris) if nrm is None else nrm
    N = len(pos)
    inner = pos - n * thickness
    from collections import Counter
    edges = Counter()
    for t in tris:
        for a, b_ in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edges[(a, b_)] += 1
    border = [(a, b_) for (a, b_) in edges if (b_, a) not in edges]
    rim = []
    for a, b_ in border:
        rim += [(b_, a, a + N), (b_, a + N, b_ + N)]
    P = np.vstack([pos, inner])
    U = np.vstack([uv, uv])
    T = np.vstack([tris, tris[:, ::-1] + N] + ([np.array(rim)] if rim else []))
    part = np.concatenate([np.zeros(N), np.full(N, 2.0)])
    return P, U, T, part


def extrude_polygon(poly2, center, e1, e2, normal, thickness):
    """Polígono 2D (no plano e1/e2) extrudado ao longo de normal; retorna (pos, nrm, tris)."""
    n = len(poly2)
    front = center + poly2[:, :1] * e1 + poly2[:, 1:2] * e2 + normal * thickness / 2
    back = front - normal * thickness
    pos = [center + normal * thickness / 2, center - normal * thickness / 2]
    nrm = [normal, -normal]
    pos += list(front) + list(back)
    nrm += [normal] * n + [-normal] * n
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris.append((0, 2 + i, 2 + j))
        tris.append((1, 2 + n + j, 2 + n + i))
    base = len(pos)
    for i in range(n):
        j = (i + 1) % n
        a, b_, c, d = front[i], front[j], back[i], back[j]
        side = np.cross(b_ - a, normal)
        side /= max(np.linalg.norm(side), 1e-9)
        pos += [a, b_, c, d]
        nrm += [side] * 4
        k = base + 4 * i
        tris += [(k, k + 2, k + 1), (k + 1, k + 2, k + 3)]
    return np.array(pos), np.array(nrm), np.array(tris)


def star_polygon(r, rf=.45, points=5, rot=0.0):
    a = np.arange(points * 2) * np.pi / points + rot
    rr = np.where(np.arange(points * 2) % 2 == 0, r, r * rf)
    return np.stack([np.sin(a) * rr, np.cos(a) * rr], 1)


def gear_polygon(r, teeth=10, depth=.22, hole=0.0):
    k = teeth * 8
    a = np.linspace(0, 2 * np.pi, k, endpoint=False)
    w = (np.cos(a * teeth) > -.1).astype(float)
    from scipy.ndimage import uniform_filter1d
    w = uniform_filter1d(w, 2, mode='wrap')
    rr = r * (1 - depth + depth * w)
    return np.stack([np.cos(a) * rr, np.sin(a) * rr], 1)


def gear_mesh(center, normal, r, thickness, teeth=10, hole=.45, spokes=5):
    """Engrenagem com aro, raios e cubo (vazada), extrudada."""
    normal = np.asarray(normal, float) / np.linalg.norm(normal)
    _, e1, e2 = frame(normal)
    parts = []
    # Aro dentado: faixa entre o contorno dos dentes e um anel interno.
    outer = gear_polygon(r, teeth)
    k = len(outer)
    inner_r = r * (1 - .22) * (1 - .18)
    a = np.linspace(0, 2 * np.pi, k, endpoint=False)
    inner = np.stack([np.cos(a) * inner_r, np.sin(a) * inner_r], 1)
    pos, nrm, tris = [], [], []
    for sgn in (1, -1):
        base = len(pos)
        for P2 in (outer, inner):
            for q in P2:
                pos.append(center + q[0] * e1 + q[1] * e2 + normal * thickness / 2 * sgn)
                nrm.append(normal * sgn)
        for i in range(k):
            j = (i + 1) % k
            o0, o1, i0, i1 = base + i, base + j, base + k + i, base + k + j
            tris += [(o0, o1, i0), (o1, i1, i0)] if sgn > 0 else [(o0, i0, o1), (o1, i0, i1)]
    for P2, out in ((outer, 1), (inner, -1)):
        for i in range(k):
            j = (i + 1) % k
            qa, qb = P2[i], P2[j]
            A0 = center + qa[0] * e1 + qa[1] * e2
            B0 = center + qb[0] * e1 + qb[1] * e2
            side = np.cross(B0 - A0, normal) * out
            side /= max(np.linalg.norm(side), 1e-9)
            base = len(pos)
            pos += [A0 + normal * thickness / 2, B0 + normal * thickness / 2, A0 - normal * thickness / 2, B0 - normal * thickness / 2]
            nrm += [side] * 4
            tris += [(base, base + 2, base + 1), (base + 1, base + 2, base + 3)] if out > 0 else [(base, base + 1, base + 2), (base + 1, base + 3, base + 2)]
    parts.append((np.array(pos), np.array(nrm), np.array(tris)))
    # Cubo e raios.
    parts.append(cylinder(center - normal * thickness * .7, normal, r * hole * .45, thickness * 1.4, 20))
    for i in range(spokes):
        ang = 2 * np.pi * i / spokes
        d = np.cos(ang) * e1 + np.sin(ang) * e2
        w = r * .09
        L0, L1 = r * hole * .4, inner_r + r * .02
        quad = np.array([[L0, -w], [L1, -w], [L1, w], [L0, w]])
        rot = np.stack([quad[:, 0] * np.cos(ang) - quad[:, 1] * np.sin(ang), quad[:, 0] * np.sin(ang) + quad[:, 1] * np.cos(ang)], 1)
        parts.append(extrude_polygon(rot, center, e1, e2, normal, thickness * .8))
    return merge(parts)


def finish_flat(bake, albedo, rough, height, metal=None):
    """Mesmo que cloth.finish, com alturas já calculadas por texel."""
    vals = np.zeros(bake.mask.shape, np.float32)
    vals[bake.mask] = height

    def height_fn(q):
        return vals[bake.mask]
    return cloth.finish(bake, albedo, rough, height_fn, metal=metal)


def body_weights(model, pos, blend):
    """Pesos por vértice: mistura de ossos [(nome, peso por vértice)] normalizada."""
    W = np.zeros((len(pos), len(model.bone_names)), np.float32)
    for name, w in blend:
        W[:, model.bone_index(name)] += w
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    return W


def emit_weighted(b, name, pos, tris, uv, material, W, nrm=None, extra_attrs=None, rigid=False):
    """Como ItemBuilder.bound, mas com pesos escolhidos (morphs do corpo mais próximo)."""
    m = b.model
    ids, bary, _ = m.bind(pos)
    morphs = m.bound_morphs(ids, bary)
    if rigid:
        morphs = {k: np.broadcast_to(d.mean(0), d.shape).copy() for k, d in morphs.items()}
    morphs = {k: v for k, v in morphs.items() if np.abs(v).max() > 5e-4}
    if nrm is None:
        nrm = mesh_normals(pos, tris)
    b._emit(name, pos, nrm, uv, tris, material, W, morphs, extra_attrs)


# ---------------------------------------------------------------- cajado

# Pose parada (idle) da mão direita no esqueleto-padrão: posição e rotação do osso RightHand.
# O cajado passa pelo vão dos dedos fechados e fica quase vertical nessa pose.
IDLE_HAND = (np.array([-.303, .925, .082]), [0.265, -0.117, 0.295, 0.91])
STAFF = {'center': np.array([-.29, .835, .106]), 'idle': .65, 'below': .66, 'above': .92, 'wrap': .022}


def orrery_staff(model, layout, item_id='prop_orrery_staff'):
    b = ItemBuilder(model, item_id, 'prop')
    from scipy.spatial.transform import Rotation as R
    hand_idle, quat = IDLE_HAND
    q = R.from_quat(quat)
    hand_rest = model.heads['RightHand']
    g = q.inv().apply(STAFF['center'] - hand_idle) + hand_rest
    # Eixo: meio-termo entre a vertical da pose parada (peso 'idle') e a vertical do repouso (pose A).
    u = q.inv().apply([0, 1, 0]) * STAFF['idle'] + np.array([0, 1, 0]) * (1 - STAFF['idle'])
    u /= np.linalg.norm(u)
    u, e1, e2 = frame(u)
    lo, hi = STAFF['below'], STAFF['above']
    wood = flat_material(b, 'wood', '#2a1d2e', roughness=.45, clearcoat=(.5, .3))
    gold = gold_material(b)
    leather = flat_material(b, 'wrap', LEATHER, roughness=.7)
    # Haste afunilada (mais grossa no alto).
    parts = []
    n_seg = 24
    ring_pts = []
    for i, t in enumerate(np.linspace(-lo, hi - .1, 26)):
        rad = .0115 + .003 * (t + lo) / (hi + lo)
        ang = np.linspace(0, 2 * np.pi, n_seg, endpoint=False)
        ring_pts.append(g + u * t + rad * (np.cos(ang)[:, None] * e1 + np.sin(ang)[:, None] * e2))
    P = np.array(ring_pts)
    pos, uv, tris = grid_mesh(P, closed=True)
    b.bound('shaft', pos, tris, uv, wood, bone='RightHand', rigid=True)
    # Empunhadura de couro trançado, ponteira e anéis dourados.
    wrap = []
    for t in np.linspace(-.07, .07, 9) + STAFF['wrap']:
        wrap.append(torus(g + u * t, u, .0135, .0032, 24, 6))
    wp, wn, wt = merge(wrap + [cylinder(g + u * (STAFF['wrap'] - .075), u, .0128, .15, 24)])
    b.bound('grip', wp, wt, np.zeros((len(wp), 2)), leather, nrm=wn, bone='RightHand', rigid=True)
    gp = [torus(g + u * t, u, .0145, .0035, 24, 8) for t in (STAFF['wrap'] - .085, STAFF['wrap'] + .085)]
    gp.append(cylinder(g - u * lo, u, .0125, .06, 20))
    tip = g - u * (lo + .02)
    cone = []
    for i, t in enumerate(np.linspace(0, 1, 6)):
        ang = np.linspace(0, 2 * np.pi, 16, endpoint=False)
        cone.append(tip + u * .02 * t + (.004 + .0085 * t) * (np.cos(ang)[:, None] * e1 + np.sin(ang)[:, None] * e2))
    cp, _, ct = grid_mesh(np.array(cone), closed=True)
    gp.append((cp, mesh_normals(cp, ct), ct))
    # Espiral dourada na parte alta da haste.
    from hair import tube_mesh
    tt = np.linspace(.2, hi - .14, 120)
    helix = g + u * tt[:, None] + .0142 * (np.cos(tt * 38)[:, None] * e1 + np.sin(tt * 38)[:, None] * e2)
    hp, hn, huv, ht, _ = tube_mesh([helix], [np.full(len(tt), .0022)], sides=5)
    gp.append((hp, hn, ht))
    # Suporte da esfera: colar, dois braços curvos (forquilha) e o anel equatorial.
    top = g + u * hi
    c = top + u * .05
    R_ = .1
    gp.append(cylinder(g + u * (hi - .14), u, .018, .03, 24))
    gp.append(torus(g + u * (hi - .11), u, .019, .005, 24, 8))
    for sgn in (1, -1):
        arc = []
        for a in np.linspace(0, 1, 24):
            ang = -np.pi / 2 + a * np.pi * .62
            arc.append(c + (sgn * e1 * np.cos(ang) + u * np.sin(ang)) * (R_ + .012) * (1 + .15 * (1 - a) ** 2))
        arc = np.array(arc)
        arc[0] = g + u * (hi - .1)
        ap, an, _, at, _ = tube_mesh([arc], [np.linspace(.0065, .004, len(arc))], sides=8)
        gp.append((ap, an, at))
    # Esfera armilar: equador, dois meridianos, eclíptica inclinada e anel das órbitas.
    gp.append(torus(c, u, R_, .0042, 48, 6))
    gp.append(torus(c, e1, R_, .0042, 48, 6))
    gp.append(torus(c, e2, R_ * .985, .0036, 48, 6))
    ecl = u * np.cos(.41) + e1 * np.sin(.41)
    gp.append(torus(c, ecl, R_ * .93, .006, 48, 6))
    gp.append(torus(c, u * np.cos(-.3) + e2 * np.sin(-.3), R_ * .7, .0028, 48, 6))
    # Remate: estrela no topo.
    sp, sn, st = extrude_polygon(star_polygon(.034), c + u * (R_ + .045), e1, u, e2, .01)
    gp.append((sp, sn, st))
    gp.append(cylinder(c + u * R_ * .97, u, .006, .03, 12))
    gpos, gnrm, gtris = merge(gp)
    b.bound('gold', gpos, gtris, np.zeros((len(gpos), 2)), gold, nrm=gnrm, bone='RightHand', rigid=True)
    # Núcleo luminoso e planetas.
    orb = b.glb.material('orb', color=(*lin('#5ab8ff'), 1), roughness=.15, emissive=(.25, .62, 1.0), clearcoat=(1, .05))
    op, on, ot = sphere_mesh(c, .038, 20, 14)
    b.bound('orb', op, ot, np.zeros((len(op), 2)), orb, nrm=on, bone='RightHand', rigid=True)
    planets = []
    colors = (('#e0763a', .016, 0.6, R_ * .7, u * np.cos(-.3) + e2 * np.sin(-.3)), ('#5fd0c0', .012, 2.6, R_ * .93, ecl), ('#d8d2ff', .009, 4.1, R_ * .7, u * np.cos(-.3) + e2 * np.sin(-.3)))
    for i, (col, rad, ang, rr, ax) in enumerate(colors):
        ax, f1, f2 = frame(ax)
        pc = c + rr * (np.cos(ang) * f1 + np.sin(ang) * f2)
        pp, pn, pt = sphere_mesh(pc, rad, 16, 10)
        mat = b.glb.material(f'planet{i}', color=(*lin(col), 1), roughness=.4, emissive=tuple(np.array(lin(col)) * .25))
        b.bound(f'planet{i}', pp, pt, np.zeros((len(pp), 2)), mat, nrm=pn, bone='RightHand', rigid=True)
    return b.save({'grip': 'staff', 'hand': 'Right'})


# ---------------------------------------------------------------- túnica com colete e tabardo

def arm_angle(p, A, side):
    """Ângulo ao redor do eixo do braço (para pregas de manga bufante)."""
    a, f = A.h[f'{side}Arm'], A.h[f'{side}Hand']
    ax = (f - a) / np.linalg.norm(f - a)
    _, e1, e2 = frame(ax)
    r = p - a
    return np.arctan2(r @ e2, r @ e1), (r @ ax) / np.linalg.norm(f - a)


def sun_emblem(X, Y, r=.022):
    """Sol com raios e estrela no centro. Retorna (ouro, azul) em 0..1."""
    rr = np.hypot(X, Y)
    ang = np.arctan2(X, Y)
    px = .0007
    disk = smoothstep(r + px, r - px, rr)
    ray_w = np.abs(((ang / (2 * np.pi) * 12) % 1) - .5)
    rays = smoothstep(r * 1.9 + px, r * 1.9 - px, rr + ray_w * r * 2.2) * (rr > r * .9)
    ring = smoothstep(px, -px, np.abs(rr - r * .78) - .0012)
    star = smoothstep(px, -px, sd_star(np.stack([X, Y], 1), r * .62))
    gold = np.clip(disk * (1 - smoothstep(r * .7 + px, r * .7 - px, rr)) + rays + ring + star, 0, 1)
    blue = disk * smoothstep(r * .7 + px, r * .7 - px, rr) * (1 - star)
    return gold, blue


def tunic_surface(model, layout, A):
    from wardrobe2 import long_top_surface
    s = long_top_surface(model, layout, A, ease=.016, sleeve_ease=(.026, .05), hem=.06, sleeve_end=.56, drape=1.0, neck_up=.004)
    return s


def star_tunic(model, layout, item_id='top_star_tunic'):
    A = G.Anatomy(model)
    G.reset_strips()
    s = tunic_surface(model, layout, A)
    L = classify_loops(s)
    neck_c = A.h['Neck']
    for loop in L['neck']:
        G.band(s, loop, lambda P: np.array([0, 1, 0]) + (neck_c - P) * np.array([.4, 0, .4]), .014, rows=2, part=1)
    for loop in L['sleeve']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        _, _, axis = arm_axis(A, side, upper=False)
        G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .03, rows=3, part=1, inward=.024)
    for loop in L['hem']:
        G.band(s, loop, lambda P: np.tile([0., -1, 0], (len(P), 1)), .022, rows=3, part=1, inward=-.002)
    G.solidify(s, .0026)
    b = ItemBuilder(model, item_id, 'top')
    arm = np.isin(A.bone[s.vid], ('LeftArm', 'RightArm', 'LeftForeArm', 'RightForeArm')).astype(float)
    bake = cloth.bake_surface(s, extra={'arm': arm})
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    on_arm = bake.at('arm')[:, 0] > .5
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    cream, navy, dark, gold = cloth.srgb(CREAM), cloth.srgb(NAVY), cloth.srgb('#262744'), cloth.srgb(GOLD)
    front = (z > 0) & (n[:, 2] > -.2)
    # Colete escuro no tronco, com decote em coração na frente e mais alto nas costas.
    neck_line = np.where(front, 1.35 + .7 * np.clip(np.abs(x) - .03, 0, .12) ** 1.2 + .02 * np.cos(np.clip(np.abs(x) / .05, 0, 1) * np.pi), 1.45)
    vest = (~on_arm) & (y < neck_line) & (part < .5)
    tab_w = .082 - .01 * smoothstep(1.32, 1.1, y)
    tabard = front & (np.abs(x) < tab_w) & (y < 1.37) & (n[:, 2] > .2)
    alb = cream * (1 + .04 * (fbm(p, 20, 3, 4) - .5))[:, None]
    alb = np.where(vest[:, None], dark * (1 + .08 * (fbm(p, 40, 3, 9) - .5))[:, None], alb)
    alb = np.where(tabard[:, None], cream * .97, alb)
    metal = np.zeros(len(p))
    rough = np.where(vest, .62, .7)
    # Debrum dourado no decote do colete e bordas do tabardo (ouro por fora, azul por dentro).
    edge_v = smoothstep(.0035, .0018, np.abs(y - neck_line)) * (~on_arm) * (~tabard)
    dx = tab_w - np.abs(x)
    edge_t = tabard * (smoothstep(.0035, .0018, np.abs(dx - .004)))
    blue_t = tabard * smoothstep(.0012, 0, np.abs(dx - .011) - .0028)
    trim = np.clip(edge_v + edge_t, 0, 1)
    alb = cloth.lin_mix(alb, navy, blue_t)
    alb = cloth.lin_mix(alb, gold, trim)
    # Sol com estrela no tabardo, na altura da barriga.
    sg, sb = sun_emblem(x, y - 1.235, .024)
    sg, sb = sg * tabard, sb * tabard
    alb = cloth.lin_mix(alb, navy, sb)
    alb = cloth.lin_mix(alb, gold, sg)
    gold_m = np.clip(trim + sg, 0, 1)
    metal = gold_m * .85
    rough = rough * (1 - gold_m) + .35 * gold_m
    # Faixas: gola creme com fio dourado, punhos franzidos, barra azul com fio dourado.
    band = (part > .5) & (part < 1.5)
    hem_band = band & (y < 1.1)
    alb = np.where(hem_band[:, None], navy, alb)
    alb = np.where((part > 1.5)[:, None], alb * .7, alb)
    hfn = fabric_height(n, 'satin', .0018)
    arm_ang = np.zeros(len(p))
    for side, sgn in (('Left', 1), ('Right', -1)):
        ang, t = arm_angle(p, A, side)
        arm_ang = np.where(np.sign(x) == sgn, ang, arm_ang)

    def height(q):
        puffs = on_arm * np.sin(arm_ang * 9 + fbm(q, 30, 2, 4) * 2) * .0016
        gathers = band * np.sin(arm_ang * 26) * .0006
        return hfn(q) + puffs + gathers + gold_m * .0004 + blue_t * .0001
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=metal)
    mat = tex_material(b, 'tunic', a, nm, orm, sheen=((.5, .46, .4), .45))
    b.derived('tunic', s, mat)
    tabard_flaps(model, A, b, s)
    return b.save({'hides': ['chest', 'belly', 'upperarm_a', 'upperarm_b', 'upperarm_c', 'upperarm_d', 'forearm_a', 'forearm_b']})


def hanging_profile(model, x0, y_top, y_bot, side_z, rows, ease):
    """Perfil (z por altura) de um painel que cai a partir da cintura sem atravessar o corpo."""
    c = model.coords[:13380]
    ys = np.linspace(y_top, y_bot, rows)
    zs = []
    for yy in ys:
        m = (np.abs(c[:, 0] - x0) < .03) & (np.abs(c[:, 1] - yy) < .015)
        if side_z > 0:
            zs.append(c[m, 2].max() + ease if m.any() else np.nan)
        else:
            zs.append(c[m, 2].min() - ease if m.any() else np.nan)
    zs = np.array(zs)
    zs = np.where(np.isnan(zs), np.nanmax(zs) if side_z > 0 else np.nanmin(zs), zs)
    # Pano pendurado: nunca volta para dentro depois de passar por um ponto saliente.
    if side_z > 0:
        zs = np.maximum.accumulate(zs)
    else:
        zs = np.minimum.accumulate(zs)
    return ys, zs


def tabard_flaps(model, A, b, s):
    """Abas do tabardo (frente e costas) caindo da cintura sobre a calça."""
    hips = A.h['Hips'][1]
    y_top, y_bot = hips + .09, hips - .27
    rows, cols = 24, 13
    parts = []
    for side_z, width, drop in ((1, .085, 0.0), (-1, .095, .02)):
        xs = np.linspace(-width, width, cols)
        P = np.zeros((rows, cols, 3))
        for j, x0 in enumerate(xs):
            ys, zs = hanging_profile(model, x0, y_top, y_bot - drop, side_z, rows, .03)
            # Sobe até a túnica no topo: usa a superfície da túnica como apoio.
            near = (np.abs(s.pos[:, 0] - x0) < .02) & (np.abs(s.pos[:, 1] - y_top) < .02) & (np.sign(s.pos[:, 2]) == side_z)
            zt = (s.pos[near, 2].max() if side_z > 0 else s.pos[near, 2].min()) if near.any() else zs[0]
            zs = np.maximum(zs, zt + .004) if side_z > 0 else np.minimum(zs, zt - .004)
            P[:, j, 0] = x0 * (1 + .12 * np.linspace(0, 1, rows))
            P[:, j, 1] = ys
            P[:, j, 2] = zs
        # Alisa o painel lateralmente (pano rígido, sem degraus).
        from scipy.ndimage import uniform_filter1d
        P[..., 2] = uniform_filter1d(P[..., 2], 5, axis=1, mode='nearest')
        P[..., 2] = uniform_filter1d(P[..., 2], 3, axis=0, mode='nearest')
        if side_z > 0:
            P[..., 2] = np.maximum.accumulate(P[..., 2], axis=0)
        else:
            P[..., 2] = np.minimum.accumulate(P[..., 2], axis=0)
            P = P[:, ::-1]
        parts.append(P)
    # Uma textura para as duas abas (metade esquerda frente, direita costas).
    for k, P in enumerate(parts):
        pos, uv, tris = grid_mesh(P)
        uv = uv * np.array([.48, 1]) + np.array([.5 * k + .01, 0])
        parts[k] = solid_shell(pos, uv, tris, .0025)
    # Textura das abas: creme com borda azul e fio dourado, sol na frente.
    allp = np.vstack([q[0][:len(q[0]) // 2] for q in parts])
    allu = np.vstack([q[1][:len(q[1]) // 2] for q in parts])
    allt, off = [], 0
    for q in parts:
        nn = len(q[0]) // 2
        t = q[2][(q[2] < nn).all(1)]
        allt.append(t + off)
        off += nn
    allt = np.vstack(allt)
    bake = bake_mesh(allp, allu, allt, 1024)
    H, W = bake.mask.shape
    vv, uu = np.mgrid[0:H, 0:W]
    U = (uu[bake.mask] + .5) / W
    V = (vv[bake.mask] + .5) / H
    k = (U > .5).astype(int)
    lu = (U - .01 - .5 * k) / .48
    width = np.where(k == 0, .085, .095) * 2
    X = (lu - .5) * width
    Y = V * (.36 + .02 * k)
    cream, navy, gold = cloth.srgb(CREAM), cloth.srgb(NAVY), cloth.srgb(GOLD)
    d_edge = np.minimum(np.minimum(X + width / 2, width / 2 - X), np.where(k == 0, .36, .38) - Y)
    alb = np.tile(cream, (len(U), 1)) * (1 + .04 * (fbm(bake.pos[bake.mask].astype(np.float64), 20, 3, 4) - .5))[:, None]
    blue = smoothstep(.0145, .0135, d_edge)
    goldm = smoothstep(.0012, .0, np.abs(d_edge - .0045) - .0015) + smoothstep(.0012, 0, np.abs(d_edge - .017) - .001)
    sg, sb = np.zeros(len(U)), np.zeros(len(U))
    st, _ = star_field(X + k * 3, Y, .045, (.006, .009), .55, seed=4)
    st = st * (d_edge > .025)
    alb = cloth.lin_mix(alb, navy, np.clip(blue + sb, 0, 1))
    gm = np.clip(goldm + sg + st, 0, 1)
    alb = cloth.lin_mix(alb, gold, gm)
    rough = .7 * (1 - gm) + .35 * gm
    a, nm, orm = finish_flat(bake, np.clip(alb, 0, 1), rough, gm * .0004 + (fbm(bake.pos[bake.mask].astype(np.float64), 900, 2, 5) - .5) * .00006, metal=gm * .85)
    mat = tex_material(b, 'tabard', a, nm, orm, sheen=((.5, .46, .4), .45), double=False)
    names = ('front', 'back')
    for (sp, su, st_, part), name in zip(parts, names):
        y = sp[:, 1]
        hang = smoothstep(y_top - .05, y_bot, y)
        left = smoothstep(-.03, .03, sp[:, 0])
        W = body_weights(model, sp, [('Hips', 1 - .6 * hang), ('Spine', .25 * (1 - hang) * (y > hips + .04)),
                                     ('LeftUpLeg', .6 * hang * left), ('RightUpLeg', .6 * hang * (1 - left))])
        emit_weighted(b, f'tabard_{name}', sp, st_, su, mat, W)


# ---------------------------------------------------------------- calça bufante estrelada

def leg_coords(p, A):
    """Coordenadas cilíndricas por perna: (contorno em metros, altura ao longo da perna)."""
    X = np.zeros(len(p))
    Y = np.zeros(len(p))
    ang_out = np.zeros(len(p))
    for side, sgn in (('Left', 1), ('Right', -1)):
        a, f = A.h[f'{side}UpLeg'], A.h[f'{side}Foot']
        ax = (f - a) / np.linalg.norm(f - a)
        e1 = np.array([0, 0, 1.]) - ax * ax[2]
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        r = p - a
        ang = np.arctan2(r @ e2 * sgn, r @ e1)
        m = np.sign(p[:, 0]) == sgn
        X[m] = (ang * .085)[m] + sgn * 5
        Y[m] = (r @ ax)[m]
        ang_out[m] = ang[m]
    return X, Y, ang_out


PANTS_END = .6


def star_pants_surface(model, layout, A):
    c = model.coords
    top = A.h['Hips'][1] + .05
    end_t = PANTS_END

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
    # Bufante: folga cresce até o meio da canela e se recolhe no cano da bota.
    puff = .046 * np.exp(-((t - .2) / .2) ** 2)
    gather = .011 + (puff - .011) * smoothstep(end_t - .02, .36, t)
    amount = np.where(shin, gather, np.where(thigh, .007 + .028 * smoothstep(.3, 1.0, t), .007))
    G.offset(model, s, amount)
    G.smooth(s, 14, keep_boundary=True)
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
    return s, top


def star_pants(model, layout, item_id='bottom_star_pants'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, top = star_pants_surface(model, layout, A)
    for loop in classify_loops(s)['hem']:
        G.band(s, loop, lambda P: np.tile([0., 1, 0], (len(P), 1)), .03, rows=3, part=1, inward=.002)
    G.solidify(s, .0025)
    b = ItemBuilder(model, item_id, 'bottom')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    X, Y, ang = leg_coords(p, A)
    navy, gold = cloth.srgb(NAVY), cloth.srgb(GOLD)
    stars, st_h = star_field(X, Y, .052, (.008, .013), .8, seed=11)
    stars = stars * (part < .5)
    alb = navy * (1 + .07 * (fbm(p, 18, 3, 4) - .5))[:, None]
    alb = cloth.lin_mix(alb, gold, stars)
    alb = np.where((part > .5)[:, None] & (part < 1.5)[:, None], cloth.srgb(NAVY_DEEP), alb)
    alb = np.where((part > 1.5)[:, None], alb * .65, alb)
    rough = .62 * (1 - stars) + .35 * stars
    knee_y, ankle_y = A.h['LeftLeg'][1], A.h['LeftFoot'][1]
    cuff_y = knee_y + (ankle_y - knee_y) * PANTS_END
    gathers = smoothstep(cuff_y + .16, cuff_y + .02, p[:, 1]) * (p[:, 1] < knee_y)

    def extra(q):
        radial = gathers * np.sin(ang * 13 + fbm(q, 15, 2, 3) * 3) * .0022
        sway = np.sin(q[:, 1] * 2 * np.pi * 7 + ang * 2 + fbm(q, 10, 2, 2) * 6) * .0011 * (q[:, 1] < A.h['Hips'][1] - .05)
        return radial + sway + stars * .0003
    hfn = fabric_height(n, 'satin', .0024, extra)
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, hfn, metal=stars * .8)
    mat = tex_material(b, 'pants', a, nm, orm, sheen=((.35, .38, .55), .45))
    b.derived('pants', s, mat)
    return b.save({'hides': ['hips', 'thigh_a', 'thigh_b', 'thigh_c', 'thigh_d', 'shin_a', 'shin_b']})


# ---------------------------------------------------------------- botas com punho dourado

BOOT_TOP = .38


def gold_boots(model, layout, item_id='shoes_gold_boots'):
    A = G.Anatomy(model)
    G.reset_strips()
    s = shoe_shell(model, layout, A, collar_t=BOOT_TOP, ease=.007)
    # Cano mais largo no alto (a calça bufante entra na bota).
    knee_y, ankle_y = A.h['LeftLeg'][1], A.h['LeftFoot'][1]
    top_y = knee_y + (ankle_y - knee_y) * BOOT_TOP
    k = smoothstep(ankle_y + .06, top_y - .02, s.pos[:, 1]) * (s.part < 1.5)
    G.offset(model, s, .011 * k)
    G.smooth(s, 2, keep_boundary=True)
    # Biqueira lisa: a frente do pé é projetada num superelipsoide (sem dedos marcados).
    toe_n = np.zeros_like(s.pos)
    toe_k = np.zeros(len(s.pos))
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = np.sign(s.pos[:, 0]) == sign
        P = s.pos[m]
        rel = P - ankle
        fw, lt, up = rel @ f, rel @ lat, P[:, 1]
        cc = np.array([.075, 0., .042])
        rad = np.array([.165, .056, .056])
        dd = np.stack([fw - cc[0], lt - cc[1], up - cc[2]], 1) / rad
        norm = (np.abs(dd) ** 2.6).sum(1) ** (1 / 2.6)
        target = dd / np.maximum(norm, 1e-6)[:, None] * rad + cc
        kk = smoothstep(-.04, .07, fw) * (up < .13)
        thick = s.part[m] > 1.5
        target = np.where(thick[:, None], target - (target - cc) / np.linalg.norm(target - cc, axis=1, keepdims=True) * .002, target)
        new = np.stack([fw, lt, up], 1) * (1 - kk[:, None]) + target * kk[:, None]
        s.pos[m] = ankle * [1, 0, 1] + np.outer(new[:, 0], f) + np.outer(new[:, 1], lat) + np.outer(new[:, 2], [0, 1, 0])
        grad = np.sign(dd) * np.abs(dd) ** 1.6 / rad
        gw = np.outer(grad[:, 0], f) + np.outer(grad[:, 1], lat) + np.outer(grad[:, 2], [0, 1, 0])
        gw /= np.linalg.norm(gw, axis=1, keepdims=True)
        toe_n[m] = np.where(thick[:, None], -gw, gw)
        toe_k[m] = kk
    G.smooth(s, 6, keep_boundary=True)
    s.pos[:, 1] = np.maximum(s.pos[:, 1], .016)
    b = ItemBuilder(model, item_id, 'shoes')
    bake = cloth.bake_surface(s, 1024, extra={'P': s.pos, 'K': toe_k})
    p = bake.at('P').astype(np.float64)
    flat_toe = 1 - smoothstep(.2, .6, bake.at('K')[:, 0])
    part = bake.at('part')[:, 0]
    brown, dark, gold = cloth.srgb(LEATHER), cloth.srgb(LEATHER_DARK), cloth.srgb(GOLD)
    alb = brown * (1 + .12 * (fbm(p, 30, 3, 5) - .5))[:, None]
    trim = np.zeros(len(p))
    toe = np.zeros(len(p))
    for side, sign in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = np.sign(p[:, 0]) == sign
        fw = (p - ankle) @ f
        toe[m] = (smoothstep(.1, .13, fw) * (p[:, 1] < .07))[m]
        # Friso dourado junto à sola.
        trim[m] = np.maximum(trim[m], smoothstep(.0022, .001, np.abs(p[m, 1] - .03)))
    alb = cloth.lin_mix(alb, dark, toe * .7)
    alb = cloth.lin_mix(alb, gold, trim)
    alb = np.where((part > 1.5)[:, None], dark * .7, alb)
    rough = .48 * (1 - trim) + .35 * trim

    def height(q):
        return ((fbm(q, 500, 2, 3) - .5) * .00012 + (fbm(q, 45, 2, 6) - .5) * .0007 + trim * .0004) * flat_toe
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=trim * .85)
    upper = tex_material(b, 'leather', a, nm, orm, clearcoat=(.35, .3))
    nrm = G.vertex_normals_canon(s)
    kk = smoothstep(.0, .5, toe_k)[:, None]
    nrm = nrm * (1 - kk) + toe_n * kk
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    b.derived('upper', s, upper, weight_smooth=2, normals=nrm)
    boot_cuffs(model, A, b, s, top_y)
    sole_mat = flat_material(b, 'sole', '#2a1a10', roughness=.6)
    for side, sign in (('Left', 1), ('Right', -1)):
        pos, uv, tris, outline, center = sole_mesh(s, sign, y_bottom=-.013, y_top=.02, flare=.005)
        b.bound(f'sole_{side}', pos, tris, uv, sole_mat, bone=f'{side}Foot')
    return b.save({'hides': ['shin_c', 'shin_d', 'feet'], 'lift': .014})


def boot_cuffs(model, A, b, s, top_y):
    """Punho dobrado e alargado no alto do cano, com frisos e estrela dourados."""
    from hair import tube_mesh
    gold = gold_material(b)
    cuff_mat = None
    meshes = []
    for side, sign in (('Left', 1), ('Right', -1)):
        kk, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        axis = (kk - a) / np.linalg.norm(kk - a)
        _, e1, e2 = frame(axis)
        m = (np.sign(s.pos[:, 0]) == sign) & (s.part < 1.5) & (s.pos[:, 1] > s.pos[:, 1].max() - .035)
        P = s.pos[m]
        cen = P.mean(0)
        rel = P - cen
        ang = np.arctan2(rel @ e2, rel @ e1)
        th = np.linspace(-np.pi, np.pi, 48, endpoint=False)
        # Raio do cano por ângulo (o mais externo perto do topo).
        radial = np.linalg.norm(rel - axis * (rel @ axis)[:, None], axis=1)
        rad = np.array([radial[np.abs(((ang - t + np.pi) % (2 * np.pi)) - np.pi) < .25].max(initial=-1) for t in th])
        ok = rad > 0
        rad = np.interp(th, np.r_[th[ok] - 2 * np.pi, th[ok], th[ok] + 2 * np.pi], np.tile(rad[ok], 3))
        rad = np.convolve(np.r_[rad[-2:], rad, rad[:2]], np.ones(5) / 5, 'valid')
        rim = cen + axis * ((P - cen) @ axis).max()
        rows = []
        for f, (dh, dr) in enumerate(((.008, .003), (.0, .006), (-.015, .011), (-.03, .016), (-.042, .019), (-.046, .017))):
            rows.append(rim + axis * dh + (rad + dr)[:, None] * (np.cos(th)[:, None] * e1 + np.sin(th)[:, None] * e2))
        G3 = np.array(rows)
        pos, uv, tris = grid_mesh(G3, closed=True)
        uv = uv * np.array([.48, 1]) + np.array([.5 * (sign < 0) + .01, 0])
        meshes.append((side, solid_shell(pos, uv, tris, .003), G3))
    allp = np.vstack([q[1][0][:len(q[1][0]) // 2] for q in meshes])
    allu = np.vstack([q[1][1][:len(q[1][1]) // 2] for q in meshes])
    allt, off = [], 0
    for q in meshes:
        nn = len(q[1][0]) // 2
        allt.append(q[1][2][(q[1][2] < nn).all(1)] + off)
        off += nn
    bake = bake_mesh(allp, allu, np.vstack(allt), 512)
    H, W = bake.mask.shape
    vv, uu = np.mgrid[0:H, 0:W]
    V = (vv[bake.mask] + .5) / H
    pp = bake.pos[bake.mask].astype(np.float64)
    alb = cloth.srgb(LEATHER_DARK) * 1.25 * (1 + .14 * (fbm(pp, 30, 3, 5) - .5))[:, None]
    stitch = smoothstep(.04, .02, np.abs(V - .82)) * (np.sin((uu[bake.mask] / W) * 2 * np.pi * 70) > 0)
    alb = cloth.lin_mix(alb, cloth.srgb(GOLD), stitch * .8)
    a, nm, orm = finish_flat(bake, np.clip(alb, 0, 1), .5 - .1 * stitch, (fbm(pp, 45, 2, 6) - .5) * .0007 + stitch * .0003, metal=stitch * .7)
    cuff_mat = tex_material(b, 'cuff', a, nm, orm, clearcoat=(.35, .3))
    for side, (sp, su, st, part), G3 in meshes:
        b.bound(f'cuff_{side}', sp, st, su, cuff_mat, bone=f'{side}Leg')
        rings = [np.vstack([G3[0], G3[0][:1]]), np.vstack([G3[-1], G3[-1][:1]])]
        tp, tn, _, tt, _ = tube_mesh(rings, [np.full(len(rings[0]), .003), np.full(len(rings[1]), .0035)], sides=6)
        kk, a = A.h[f'{side}Leg'], A.h[f'{side}Foot']
        _, f, lat = foot_frame(A, side)
        front = G3[2][np.argmax(G3[2] @ f)]
        sp2, sn2, st2 = extrude_polygon(star_polygon(.013), front + f * .002, lat, (kk - a) / np.linalg.norm(kk - a), f, .004)
        pos, nrm, tris = merge([(tp, tn, tt), (sp2, sn2, st2)])
        b.bound(f'cuff_gold_{side}', pos, tris, np.zeros((len(pos), 2)), gold, nrm=nrm, bone=f'{side}Leg')


# ---------------------------------------------------------------- cabelo longo ondulado

class _LongHairVolume:
    """Cabeça e ombros (hair_styled.HeadVolume) + corpo com folga para a capa (o cabelo cai por cima dela)."""

    def __init__(self, model):
        import hair_styled as H
        from scipy.spatial import cKDTree
        self.v = H.HeadVolume(model)
        self.center, self.radii, self.L = self.v.center, self.v.radii, self.v.L
        self.neck_y = model.heads['Neck'][1]
        torso = np.flatnonzero(model.coords[:13380, 1] < self.neck_y - .01)
        sm = model.smoothed()
        self.pts, self.nrm = sm[torso], model.normals[torso]
        self.tree = cKDTree(self.pts)

    def surface_dir(self, p):
        return self.v.surface_dir(p)

    def push_out(self, p, margin):
        p = np.asarray(self.v.push_out(p, margin), float)
        flat = p.reshape(-1, 3).copy()
        low = flat[:, 1] < self.neck_y - .02
        if low.any():
            q = flat[low]
            # Folga da capa curta (mais larga nos ombros) + margem do cabelo.
            clear = .06 + .045 * smoothstep(.11, .24, np.abs(q[:, 0])) + margin
            for _ in range(3):
                _, i = self.tree.query(q, k=4)
                n = self.nrm[i].mean(1)
                n /= np.linalg.norm(n, axis=1, keepdims=True)
                d = ((q - self.pts[i[:, 0]]) * n).sum(1)
                q = q + n * np.clip(clear - d, 0, None)[:, None]
            flat[low] = q
        return flat.reshape(p.shape)


def _fall_paths(vol, starts, dirs, lengths, waves, k=24, gravity=1.5, margin=.012):
    """Mechas que caem juntas e escorregam sobre cabeça, ombros e costas (a direção segue o deslocamento real)."""
    P = np.asarray(starts, float)
    D = np.asarray(dirs, float)
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    step = np.asarray(lengths, float)[:, None] / (k - 1)
    out = [P.copy()]
    for i in range(1, k):
        t = i / (k - 1)
        D = D * .9 + np.array([0, -1., 0]) * gravity * .25 * (.3 + t)
        D /= np.linalg.norm(D, axis=1, keepdims=True)
        Q = vol.push_out(P + D * step, margin)
        mv = Q - P
        nm = np.linalg.norm(mv, axis=1, keepdims=True)
        D = D * .4 + mv / np.maximum(nm, 1e-9) * .6
        D /= np.linalg.norm(D, axis=1, keepdims=True)
        P = Q
        out.append(P.copy())
    paths = np.stack(out, 1)
    res = []
    tt = np.linspace(0, 1, k)
    for pts, (amp, freq, phase) in zip(paths, waves):
        T = np.gradient(pts, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        o = pts - vol.center * np.array([1, 0, 1])
        o[:, 1] = 0
        side = np.cross(T, o)
        side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-9)
        pts = pts + side * (np.sin(tt * freq * 2 * np.pi + phase) * amp * np.clip(tt * 2.5, 0, 1))[:, None]
        res.append(vol.push_out(pts, margin * .7))
    return res


def _emit_long(b, model, name, mat, paths, widths, vol, tip_scale=1.0, flat=.42):
    """Mechas longas: a raiz segue a cabeça e o comprimento passa para a coluna (não atravessa as costas ao virar)."""
    import hair_styled as H
    pos, nrm, uv, tris, along = H.clump_mesh(paths, widths, vol, flat=flat)
    m = model
    ids, bary, _ = m.bind(pos)
    morphs = {k: v for k, v in m.bound_morphs(ids, bary).items() if not k.startswith('expr_') and np.abs(v).max() > 5e-4}
    neck_y = m.heads['Neck'][1]
    w = smoothstep(neck_y + .01, neck_y - .12, pos[:, 1])
    W = np.zeros((len(pos), len(m.bone_names)), np.float32)
    W[:, m.bone_index('Head')] = 1 - w
    W[:, m.bone_index('Neck')] += w * .35
    W[:, m.bone_index('Spine2')] += w * .65
    tip = (np.clip(along, 0, 1) ** 1.4 * tip_scale).astype(np.float32)
    b._emit(name, pos, nrm, uv, tris, mat, W, morphs, {'_TIP': tip})


def hair_wavy_long(model, layout, item_id='hair_wavy_long'):
    """Cabelo longo em ondas largas até o meio das costas, risca lateral e mechas que emolduram o rosto."""
    import hair
    import hair_styled as H
    from hair_styles import emit, scalp_base, styled_material
    rng = np.random.default_rng(31)
    vol = _LongHairVolume(model)
    L = vol.L
    b = scalp_base(model, layout, item_id)
    mat = styled_material(b, 'hair', .45, tips=True)
    c, r = vol.center, vol.radii
    part_x = r[0] * .3  # risca do lado esquerdo do personagem
    P, N, az = H.roots(model, .012, lambda P, N, aaz: P[:, 1] > hair.scalp_line(L, aaz) + .004)
    cap_paths, cap_w, long_paths, long_w, fall = [], [], [], [], []
    for p, a in zip(P, az):
        # Destino na calota: penteado para o lado oposto da risca e para trás, terminando na altura das orelhas.
        side = 1 if p[0] > part_x else -1
        ang = np.radians(a)
        back = abs(a) > 100
        tgt_az = ang + side * (.25 if not back else .05)
        tgt_y = c[1] - r[1] * (.15 if not back else .45)
        tgt = np.array([c[0] + np.sin(tgt_az) * r[0] * 1.05, tgt_y, c[2] + np.cos(tgt_az) * r[2] * 1.05 - .01])
        if abs(a) < 35:
            # Frente: varre para o lado e para trás da orelha.
            tgt = np.array([side * r[0] * 1.02, c[1] - r[1] * .05, c[2] - r[2] * .15])
        path = H.cap_path(vol, p, tgt, 14, lift=(.004, .014 + rng.uniform(0, .006)))
        cap_paths.append(path)
        cap_w.append(H.taper(14, rng.uniform(.018, .026), .7, .5))
        # Continuação: cai em ondas largas a partir do fim da calota.
        if rng.uniform() < .8:
            d = path[-1] - path[-3]
            # Tudo cai por trás dos ombros; só as mechas soltas abaixo ficam na frente.
            back_dir = np.array([np.sign(path[-1][0]) * .25, -1.2, -1.1]) if abs(a) < 120 else np.array([path[-1][0] * 2, -1.2, -.4])
            fall.append((path[-2], path[-1], d / np.linalg.norm(d) * .3 + back_dir,
                         rng.uniform(.52, .64) if abs(a) > 60 else rng.uniform(.42, .52),
                         (rng.uniform(.016, .024), rng.uniform(2.0, 2.6), rng.uniform(0, 6)), rng.uniform(.036, .05)))
    fps = _fall_paths(vol, [f[1] for f in fall], [f[2] for f in fall], [f[3] for f in fall], [f[4] for f in fall], 24)
    for f, fp in zip(fall, fps):
        long_paths.append(np.vstack([f[0][None], fp]))
        long_w.append(H.taper(25, f[5], .25))
    emit(b, 'cap', mat, cap_paths, cap_w, vol.v, tip_scale=.2)
    _emit_long(b, model, 'waves', mat, long_paths, long_w, vol, tip_scale=1)
    # Franja lateral longa e mechas que caem à frente dos ombros.
    paths, widths = [], []
    for i in range(6):
        sx = part_x - .01 - i * .012
        root = c + np.array([sx, r[1] * .72, r[2] * .55])
        root = vol.push_out(root[None], .006)[0]
        d = np.array([-.75, -.3, .55])
        paths.append(H.free_path(vol, root, d, rng.uniform(.13, .17), 18, gravity=1.1, stiff=.45,
                                 wave=(.006, 1.1, rng.uniform(0, 6)), margin=.01, seed=200 + i))
        widths.append(H.taper(18, rng.uniform(.03, .038), .2))
    locks = []
    for sd in (1, -1):
        for i in range(2):
            root = c + np.array([sd * r[0] * .9, r[1] * .05 - i * .01, r[2] * (.35 - i * .14)])
            locks.append((vol.push_out(root[None], .006)[0], np.array([sd * .35, -1, .3]), rng.uniform(.36, .42),
                          (.016, 2.4, rng.uniform(0, 6))))
    for fp in _fall_paths(vol, [l[0] for l in locks], [l[1] for l in locks], [l[2] for l in locks], [l[3] for l in locks], 22, 1.4):
        paths.append(fp)
        widths.append(H.taper(22, rng.uniform(.026, .034), .2))
    _emit_long(b, model, 'front', mat, paths, widths, vol, tip_scale=.9)
    return b.save({'tips': True})


# ---------------------------------------------------------------- tiara de engrenagem

def circlet_gear(model, layout, item_id='circlet_gear'):
    """Tiara dourada fina sobre o cabelo com engrenagens e gema azul acima da têmpora."""
    import overlays
    from accessories import head_ring
    from hair import tube_mesh
    L = overlays.Landmarks(model)
    ey = L.eye_y
    b = ItemBuilder(model, item_id, 'headwear')
    gold = gold_material(b, roughness=.28)
    P, ang = head_ring(model, L, [ey + .085, ey + .08, ey + .07, ey + .06, ey + .05], n=96, clearance=.018)
    loop = np.vstack([P, P[:1]])
    tp, tn, _, tt, _ = tube_mesh([loop], [np.full(len(loop), .0028)], sides=8)
    parts = [(tp, tn, tt)]
    # Pingente central na testa (estrela pequena).
    i0 = int(np.argmin(np.abs(ang)))
    out = P[i0] - L.center
    out[1] = 0
    out /= np.linalg.norm(out)
    up = np.array([0, 1., 0])
    parts.append(extrude_polygon(star_polygon(.009), P[i0] + out * .002 - up * .006, np.cross(up, out), up, out, .003))
    # Engrenagens sobre a têmpora esquerda (do personagem).
    i1 = int(np.argmin(np.abs(ang - np.radians(62))))
    o1 = P[i1] - L.center
    o1[1] = 0
    o1 /= np.linalg.norm(o1)
    n1 = o1 + np.array([0, .25, .15])
    n1 /= np.linalg.norm(n1)
    g1 = P[i1] + o1 * .006 + up * .012
    parts.append(gear_mesh(g1, n1, .024, .0045, 12, .45, 5))
    _, e1, e2 = frame(n1)
    g2 = g1 + e1 * .026 + e2 * .012 - n1 * .002
    parts.append(gear_mesh(g2, n1, .014, .004, 9, .5, 4))
    g3 = g1 - e1 * .02 + e2 * .018 - n1 * .003
    parts.append(gear_mesh(g3, n1, .011, .0035, 8, .5, 3))
    pos, nrm, tris = merge(parts)
    b.bound('gold', pos, tris, np.zeros((len(pos), 2)), gold, nrm=nrm, bone='Head')
    gem = b.glb.material('gem', color=(*lin('#3f7bff'), 1), roughness=.06, emissive=(.05, .14, .45), clearcoat=(1, .03))
    gp, gn, gt = sphere_mesh(g1 + n1 * .004, .0075, 16, 10)
    b.bound('gem', gp, gt, np.zeros((len(gp), 2)), gem, nrm=gn, bone='Head')
    return b.save({})


# ---------------------------------------------------------------- capa curta com capuz

def _neck_ring(model, y, n, clearance):
    neck = model.heads['Neck']
    center = np.array([0, y, neck[2]])
    ang = np.linspace(-np.pi, np.pi, n, endpoint=False)
    d = np.stack([np.sin(ang), np.zeros(n), np.cos(ang)], 1)
    P = center + d * .14
    sm = model.smoothed()
    for _ in range(30):
        ids, bary, off = model.bind(P, coords=sm)
        nn = (model.normals[ids] * bary[..., None]).sum(1)
        nn /= np.linalg.norm(nn, axis=1, keepdims=True)
        P = P - d * ((off * nn).sum(1) - clearance)[:, None] * .7
    for _ in range(4):
        P = .5 * P + .25 * (np.roll(P, 1, 0) + np.roll(P, -1, 0))
    return P, ang


def _push_from_body(model, P, clearance, iters=12):
    """Afasta pontos da pele (corpo alisado) até `clearance`, pela normal da superfície mais próxima."""
    sm = model.smoothed()
    nrm = model.normals
    for _ in range(iters):
        ids, bary, off = model.bind(P, coords=sm)
        n = (nrm[ids] * bary[..., None]).sum(1)
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        d = (off * n).sum(1)
        cl = clearance(P) if callable(clearance) else clearance
        bad = d < cl
        if not bad.any():
            break
        P = P + n * np.where(bad, cl - d, 0)[:, None]
    return P


def back_star_capelet(model, layout, item_id='back_star_capelet'):
    """Capa curta azul-noite sobre os ombros, estrelas douradas, barra bordada, capuz caído e broche."""
    from collection_volt import emit_custom, grid_surface
    b = ItemBuilder(model, item_id, 'back')
    neck = model.heads['Neck']
    y_neck = neck[1] - .03
    gap = np.radians(14)
    cols, rows = 97, 22
    theta = np.linspace(-np.pi + gap, np.pi - gap, cols) + np.pi  # 0 = costas... ajustado abaixo
    theta = (theta + np.pi) % (2 * np.pi) - np.pi  # ângulo a partir da frente (+z), abertura na frente
    ring, ang = _neck_ring(model, y_neck, 180, .02)
    neck_pts = np.array([ring[int(np.argmin(np.abs(((ang - t) + np.pi) % (2 * np.pi) - np.pi)))] for t in theta])
    shoulder_y = model.heads['LeftArm'][1]
    sc = np.array([0, shoulder_y, .01])
    G3 = np.zeros((rows, cols, 3))
    for j, t in enumerate(theta):
        d = np.array([np.sin(t), 0, np.cos(t)])
        # Barra: elipse larga (cobre o ombro até o meio do braço), mais curta na frente.
        front = max(np.cos(t), 0)
        hem_r = np.array([.34, 0, .15])
        hem = sc + d * hem_r + np.array([0, -.13 - .06 * (1 - front) + .04 * front, 0])
        for i, s in enumerate(np.linspace(0, 1, rows)):
            q = neck_pts[j] * (1 - s) + hem * s
            q = q + np.array([0, .045, 0]) * np.sin(s * np.pi) ** 1.3 + d * .02 * np.sin(s * np.pi)
            G3[i, j] = q
    def clear(P):
        # Folga maior sobre os ombros e braços: cobre as mangas bufantes da túnica.
        return .03 + .045 * smoothstep(.11, .24, np.abs(P[:, 0]))
    flat = _push_from_body(model, G3.reshape(-1, 3), clear)
    G3 = flat.reshape(rows, cols, 3)
    # Suaviza a grade (dobra macia) mantendo a gola.
    for _ in range(4):
        G3[1:-1] = .5 * G3[1:-1] + .25 * (G3[:-2] + G3[2:])
        G3[:, 1:-1] = .5 * G3[:, 1:-1] + .25 * (G3[:, :-2] + G3[:, 2:])
    # Pregas: ondulação que cresce para a barra.
    sgrid = np.linspace(0, 1, rows)[:, None]
    wave = np.sin(theta[None, :] * 14) * .006 * sgrid ** 1.5
    radial = G3 - np.array([0, 0, neck[2]])
    radial[..., 1] = 0
    radial /= np.maximum(np.linalg.norm(radial, axis=-1, keepdims=True), 1e-9)
    G3 = G3 + radial * wave[..., None]
    G3 = _push_from_body(model, G3.reshape(-1, 3), lambda P: clear(P) - .004, 6).reshape(rows, cols, 3)
    s = grid_surface(G3)
    s.uv = np.stack([theta[None, :].repeat(rows, 0).ravel() * .24, -np.cumsum(np.vstack([np.zeros((1, cols)), np.linalg.norm(np.diff(G3, axis=0), axis=-1)]), 0).ravel()], 1)
    uv_lo, uv_hi = s.uv.min(0), s.uv.max(0)
    s.uv = (s.uv - uv_lo) / (uv_hi - uv_lo) * .98 + .01
    G.solidify(s, .003)
    ids, bary, _ = model.bind(s.pos)
    W = model.bound_weights(ids, bary).astype(np.float32)
    keep = np.isin(model.bone_names, ('Spine1', 'Spine2', 'Neck', 'LeftShoulder', 'RightShoulder', 'LeftArm', 'RightArm'))
    W[:, ~keep] = 0
    W[:, model.bone_index('Spine2')] += .15
    W /= W.sum(1, keepdims=True)
    # Textura: azul-noite, estrelas douradas, barra com fio duplo dourado.
    bake = cloth.bake_surface(s, 2048)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    hh, ww = bake.mask.shape
    vv, uu = np.mgrid[0:hh, 0:ww]
    U = ((uu[bake.mask] + .5) / ww - .01) / .98
    V = ((vv[bake.mask] + .5) / hh - .01) / .98
    X = uv_lo[0] + U * (uv_hi[0] - uv_lo[0])
    Y = uv_lo[1] + V * (uv_hi[1] - uv_lo[1])
    v_min = uv_lo[1]
    stars, _ = star_field(X, Y, .045, (.007, .012), .75, seed=21)
    hem_d = Y - v_min
    trim = smoothstep(.003, .0015, np.abs(hem_d - .012)) + smoothstep(.002, .001, np.abs(hem_d - .022))
    stars = stars * (hem_d > .035)
    navy, deep, gold = cloth.srgb(NAVY), cloth.srgb(NAVY_DEEP), cloth.srgb(GOLD)
    alb = navy * (1 + .08 * (fbm(p, 16, 3, 7) - .5))[:, None]
    alb = cloth.lin_mix(alb, deep, smoothstep(.04, 0, hem_d) * .6)
    gm = np.clip(stars + trim, 0, 1)
    alb = cloth.lin_mix(alb, gold, gm)
    alb = np.where((part > 1.5)[:, None], deep * .8, alb)
    hfn = fabric_height(n, 'satin', .002, lambda q: gm * .0003)
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), .6 * (1 - gm) + .32 * gm, hfn, metal=gm * .85)
    mat = tex_material(b, 'capelet', a, nm, orm, sheen=((.3, .34, .55), .5), double=True)
    emit_custom(b, 'capelet', s, mat, W, model)
    # Capuz caído atrás do pescoço: rolo grosso em meia-lua com forro claro.
    back = [k for k in range(len(theta)) if abs(theta[k]) > np.radians(70)]
    path = np.array([G3[1, k] for k in back])
    path = path + np.array([0, .012, -.02])
    hood = []
    for k, q in enumerate(path):
        t = k / (len(path) - 1)
        fat = .032 * np.sin(t * np.pi) ** .6 + .006
        hood.append((q, fat))
    from hair import tube_mesh
    hp, hn, huv, ht, _ = tube_mesh([path], [np.array([f for _, f in hood])], sides=14)
    hp = _push_from_body(model, hp, .02, 6)
    hood_mat = flat_material(b, 'hood', NAVY_DEEP, roughness=.6)
    b.bound('hood', hp, ht, huv, hood_mat, nrm=hn, bone='Spine2')
    # Broche: sol dourado com gema, fechando a capa na frente do pescoço.
    gold_m = gold_material(b, 'clasp', .3)
    fr = ring[int(np.argmin(np.abs(ang)))] + np.array([0, -.012, .012])
    parts = [gear_mesh(fr, np.array([0, .2, 1.]), .018, .004, 12, .5, 6)]
    for sgn in (1, -1):
        parts.append(cylinder(fr + np.array([sgn * .03, -.004, -.004]), np.array([0, .2, 1.]), .008, .005, 16))
    pos, nrm, tris = merge(parts)
    b.bound('clasp', pos, tris, np.zeros((len(pos), 2)), gold_m, nrm=nrm, bone='Spine2', rigid=True)
    gem = b.glb.material('gem', color=(*lin('#3f7bff'), 1), roughness=.06, emissive=(.05, .14, .45), clearcoat=(1, .03))
    gp, gn, gt = sphere_mesh(fr + np.array([0, .001, .006]), .007, 14, 8)
    b.bound('gem', gp, gt, np.zeros((len(gp), 2)), gem, nrm=gn, bone='Spine2', rigid=True)
    return b.save({})


# ---------------------------------------------------------------- cinto da bússola

def belt_compass(model, layout, item_id='belt_compass'):
    """Cinto de couro largo com fivela-bússola dourada e passadores."""
    from collection_volt import box, profile, ring_band
    A = G.Anatomy(model)
    G.reset_strips()
    s, top = star_pants_surface(model, layout, A)
    b = ItemBuilder(model, item_id, 'belt')
    center = np.array([0, top - .03, A.h['Hips'][2]])
    ax, u, v = np.array([0, 1., 0]), np.array([0, 0, 1.]), np.array([1., 0, 0])
    rad = profile(s.pos, center, ax, u, v, 72, .02) + .009
    for _ in range(3):
        rad = (np.roll(rad, 1) + 2 * rad + np.roll(rad, -1)) / 4
    leather = flat_material(b, 'belt', LEATHER, roughness=.55, clearcoat=(.25, .4))
    pos, nrm, tris = ring_band(center, ax, u, v, rad, .04, .0045)
    b.bound('belt', pos, tris, np.zeros((len(pos), 2)), leather, nrm=nrm)
    gold = gold_material(b, roughness=.3)
    front = center + u * (rad[36] + .006)
    parts = [cylinder(front, u, .03, .008, 40), torus(front + u * .008, u, .03, .003, 40, 8),
             torus(front + u * .008, u, .021, .0016, 32, 6)]
    # Rosa dos ventos em relevo.
    for k in range(8):
        a = k * np.pi / 4
        L_ = .019 if k % 2 == 0 else .012
        d = np.cos(a) * v + np.sin(a) * ax
        o = np.cross(u, d)
        tri = np.array([front + u * .009 + d * L_, front + u * .009 + o * .0035, front + u * .009 - o * .0035, front + u * .0125])
        tris_ = np.array([[0, 1, 3], [0, 3, 2]])
        nn = np.cross(tri[1] - tri[0], tri[3] - tri[0])
        nn = nn / np.linalg.norm(nn)
        parts.append((tri, np.tile(u, (4, 1)), tris_ if nn @ u > 0 else tris_[:, ::-1]))
    for sgn in (1, -1):
        parts.append(box(center + (np.cos(np.radians(sgn * 40) - 0) * u + np.sin(np.radians(sgn * 40)) * v) * (rad[36 + sgn * 8] + .005), v, ax, u, .006, .024, .0025))
    pos, nrm, tris = merge(parts)
    b.bound('compass', pos, tris, np.zeros((len(pos), 2)), gold, nrm=nrm, bone='Hips', rigid=True)
    face = b.glb.material('face', color=(*lin(NAVY), 1), roughness=.3, clearcoat=(1, .05))
    fp, fn, ft = cylinder(front + u * .0082, u, .02, .0006, 32)
    b.bound('face', fp, ft, np.zeros((len(fp), 2)), face, nrm=fn, bone='Hips', rigid=True)
    return b.save({})


# ---------------------------------------------------------------- braçadeiras de couro

def bracers_leather(model, layout, item_id='bracers_leather'):
    """Braçadeiras de couro no antebraço com cordões cruzados e bordas douradas."""
    A = G.Anatomy(model)
    G.reset_strips()

    def ok(v):
        b_ = A.bone[v]
        return (np.isin(b_, ('LeftForeArm', 'RightForeArm')) & (A.t[v] > .42) & (A.t[v] < .9)).all()
    s = G.surface(model, G.select(layout, ok))
    G.offset(model, s, .0045)
    G.smooth(s, 3, keep_boundary=True)
    for loop in G.loops(s):
        c = s.pos[loop].mean(0)
        side = 'Left' if c[0] > 0 else 'Right'
        a, f = A.h[f'{side}ForeArm'], A.h[f'{side}Hand']
        axis = (f - a) / np.linalg.norm(f - a)
        G.straighten(s, loop, c, axis, rings=2)
        sgn = 1 if (c - (a + f) / 2) @ axis > 0 else -1
        G.band(s, loop, lambda P, d=axis * sgn: np.broadcast_to(d, P.shape).copy(), .006, rows=2, part=1, flare=.002)
    G.push_out(model, s, .004, smooth_body=False)
    G.solidify(s, .0022)
    b = ItemBuilder(model, item_id, 'wrist')
    bake = cloth.bake_surface(s, 1024)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    alb = cloth.srgb(LEATHER) * (1 + .16 * (fbm(p, 25, 3, 5) - .5))[:, None]
    lace = np.zeros(len(p))
    for side, sg in (('Left', 1), ('Right', -1)):
        a, f = A.h[f'{side}ForeArm'], A.h[f'{side}Hand']
        axis = (f - a) / np.linalg.norm(f - a)
        rel = p - a
        along = rel @ axis
        # Lado de dentro do antebraço (voltado para o corpo na pose A) recebe o cordão cruzado.
        inner = np.array([-sg, 0, 0.]) - axis * (-sg * axis[0])
        inner /= np.linalg.norm(inner)
        side_ax = np.cross(axis, inner)
        lat = rel @ side_ax
        m = (np.sign(p[:, 0]) == sg) & ((rel @ inner) > 0)
        zig = np.abs(((along * 70) % 2) - 1) * 2 - 1
        lace = np.maximum(lace, m * smoothstep(.0022, .001, np.abs(np.abs(lat) - np.abs(zig) * .012)) * (np.abs(lat) < .014))
        lace = np.maximum(lace, m * smoothstep(.0028, .0014, np.abs(np.abs(lat) - .014)))
    edge = (part > .5) & (part < 1.5)
    alb = cloth.lin_mix(alb, cloth.srgb(CREAM), lace * .9)
    alb = np.where(edge[:, None], cloth.srgb(GOLD), alb)
    alb = np.where((part > 1.5)[:, None], cloth.srgb(LEATHER_DARK), alb)
    metal = edge * .85
    rough = np.where(edge, .32, .55)
    a_, nm, orm = finish_flat(bake, np.clip(alb, 0, 1), rough, (fbm(p, 60, 2, 3) - .5) * .0005 + lace * .0004, metal=metal)
    mat = tex_material(b, 'bracer', a_, nm, orm, clearcoat=(.3, .35))
    b.derived('bracer', s, mat, weight_smooth=1)
    return b.save({})


# ---------------------------------------------------------------- registro

def register(item):
    item('prop_orrery_staff', 'prop')(orrery_staff)
    item('top_star_tunic', 'top')(star_tunic)
    item('bottom_star_pants', 'bottom')(star_pants)
    item('shoes_gold_boots', 'shoes')(gold_boots)
    item('hair_wavy_long', 'hair')(hair_wavy_long)
    item('circlet_gear', 'headwear')(circlet_gear)
    item('back_star_capelet', 'back')(back_star_capelet)
    item('belt_compass', 'belt')(belt_compass)
    item('bracers_leather', 'wrist')(bracers_leather)
