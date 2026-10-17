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


# ---------------------------------------------------------------- registro

def register(item):
    item('prop_orrery_staff', 'prop')(orrery_staff)
    item('top_star_tunic', 'top')(star_tunic)
    item('bottom_star_pants', 'bottom')(star_pants)
    item('shoes_gold_boots', 'shoes')(gold_boots)
