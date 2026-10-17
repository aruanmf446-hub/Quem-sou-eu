"""Coleção estilizada: harlequin. Registra as peças no REGISTRY de build_items."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

import cloth
import garments as G
import hair_styled as H
import overlays
from accessories import azimuth, cylinder, head_surface, merge, plane_fit, torus
from hair import scalp_line, tube_mesh
from hair_styles import emit, scalp_base, styled_material
from items import ItemBuilder
from raster import dilate, fbm, smoothstep
from wardrobe import classify_loops, foot_frame, shoe_shell, shorts_surface, sole_mesh
from wardrobe2 import G_shirt, fabric_height, flat_material, lin, ruff_mesh, sphere_mesh, tex_material

MAGENTA, TURQ, BLACK, WHITE, GOLD = '#d81f78', '#19b8b8', '#16131a', '#f4efe6', '#e8b84a'


# ----------------------------------------------------------------------- utilidades

def lozenges(u, v, w, h, aa=.0007):
    """Losangos de arlequim: retorna (cor 0=preto/1=magenta/2=turquesa como pesos, borda).

    u, v em metros; w, h = largura e altura de cada losango. Bordas antisserrilhadas por
    supersamples (4 amostras deslocadas meio texel)."""
    acc = np.zeros((len(u), 3))
    for du, dv in ((-aa, -aa), (aa, -aa), (-aa, aa), (aa, aa)):
        a = (u + du) / w + (v + dv) / h + .5
        b = (u + du) / w - (v + dv) / h + .5
        ia, ib = np.floor(a).astype(int), np.floor(b).astype(int)
        odd = (ia + ib) % 2 == 1
        row = ((ia - ib - 1) // 2) % 2
        acc[:, 0] += ~odd
        acc[:, 1] += odd & (row == 0)
        acc[:, 2] += odd & (row == 1)
    return acc / 4


def checker_diamonds(u, v, w, h, aa=.0007):
    """Losangos de duas cores (fundo / losango) com bordas suaves."""
    acc = np.zeros(len(u))
    for du, dv in ((-aa, -aa), (aa, -aa), (-aa, aa), (aa, aa)):
        a = (u + du) / w + (v + dv) / h + .5
        b = (u + du) / w - (v + dv) / h + .5
        acc += (np.floor(a).astype(int) + np.floor(b).astype(int)) % 2 == 1
    return acc / 4


def mix3(weights, cols):
    return sum(weights[:, i:i + 1] * cloth.srgb(c)[None] for i, c in enumerate(cols))


def cyl_coords(p, center, axis, ref, R0, cols):
    """Coordenadas cilíndricas (arco, altura) com número inteiro de colunas na volta."""
    axis = axis / np.linalg.norm(axis)
    ref = ref - axis * (ref @ axis)
    ref /= np.linalg.norm(ref)
    ref2 = np.cross(axis, ref)
    rel = p - center
    ang = np.arctan2(rel @ ref2, rel @ ref)
    w = 2 * np.pi * R0 / cols
    return ang * R0, rel @ axis, w


def bell_mesh(center, radius, up=(0, 1, 0)):
    """Guizo: esfera dourada com anel de pendurar e sulco no equador."""
    up = np.asarray(up, float)
    up /= np.linalg.norm(up)
    sp, sn, st = sphere_mesh(center, radius, 14, 10)
    ref = np.array([1., 0, 0]) if abs(up[0]) < .9 else np.array([0, 0, 1.])
    side = np.cross(up, ref)
    side /= np.linalg.norm(side)
    lp, ln, lt = torus(center + up * radius * 1.12, side, radius * .38, radius * .13, 10, 5)
    gp, gn, gt = torus(center, up, radius * 1.0, radius * .09, 18, 4)
    return merge([(sp, sn, st), (lp, ln, lt)]), (gp, gn, gt)


def emit_bells(b, name, centers, radius, bone=None, rigid=False, ups=None):
    gold = b.glb.material(f'{name}_gold', color=(*lin(GOLD), 1), metallic=.9, roughness=.25)
    slit = b.glb.material(f'{name}_slit', color=(*lin('#5a3a0c'), 1), metallic=.6, roughness=.5)
    parts, grooves = [], []
    for i, c in enumerate(centers):
        (p, n, t), g = bell_mesh(np.asarray(c, float), radius, ups[i] if ups is not None else (0, 1, 0))
        parts.append((p, n, t))
        grooves.append(g)
    pos, nrm, tris = merge(parts)
    b.bound(name, pos, tris, np.zeros((len(pos), 2)), gold, nrm=nrm, bone=bone, rigid=rigid)
    pos, nrm, tris = merge(grooves)
    b.bound(f'{name}_groove', pos, tris, np.zeros((len(pos), 2)), slit, nrm=nrm, bone=bone, rigid=rigid)


def ellipse_tube(path, lat, wx, wy, sides=14):
    """Tubo de seção elíptica ao longo de um caminho plano (lat = eixo lateral constante)."""
    K = len(path)
    T = np.gradient(path, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    N = np.cross(lat, T)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    pos, nrm, uv, tris = [], [], [], []
    for k in range(K):
        for s in range(sides):
            a = 2 * np.pi * s / sides
            pos.append(path[k] + lat * np.cos(a) * wx[k] + N[k] * np.sin(a) * wy[k])
            nn = lat * np.cos(a) * wy[k] + N[k] * np.sin(a) * wx[k]
            nrm.append(nn / np.linalg.norm(nn))
            uv.append((s / sides, k / (K - 1)))
    for k in range(K - 1):
        for s in range(sides):
            a, bb = k * sides + s, k * sides + (s + 1) % sides
            tris += [(a, a + sides, bb), (bb, a + sides, bb + sides)]
    tip = (K - 1) * sides
    for s in range(1, sides - 1):
        tris.append((tip, tip + s + 1, tip + s))
    return np.array(pos), np.array(nrm), np.array(uv), np.array(tris)


# ----------------------------------------------------------------------- cabelo

def curly_pigtails(model, layout, item_id='hair_curly_pigtails'):
    rng = np.random.default_rng(7)
    vol = H.HeadVolume(model)
    L = vol.L
    b = scalp_base(model, layout, item_id)
    mat = styled_material(b, 'hair', .46, tips=True)
    c, r = vol.center, vol.radii
    gathers = {}
    for sgn in (1, -1):
        g = c + np.array([sgn * r[0] * .86, r[1] * .34, -r[2] * .2])
        gathers[sgn] = g + vol.surface_dir(g) * .014
    # Calota: risca no meio, mechas rentes que correm para os dois prendedores laterais.
    P, N, az = H.roots(model, .0135, lambda P, N, aaz: P[:, 1] > scalp_line(L, aaz) + .004)
    paths, widths = [], []
    for p, a in zip(P, az):
        sgn = 1 if p[0] > 0 else -1
        path = H.cap_path(vol, p, gathers[sgn] + rng.normal(0, .005, 3), 16, lift=(.004, .009 + rng.uniform(0, .004)))
        paths.append(path)
        widths.append(H.taper(16, rng.uniform(.019, .025), .5, .6))
    emit(b, 'cap', mat, paths, widths, vol, tip_scale=0)
    # Duas maria-chiquinhas: cachos em saca-rolhas (hélice em torno de um eixo que cai).
    paths, widths = [], []
    K = 54
    for sgn in (1, -1):
        Gp = gathers[sgn]
        n = 21
        for i in range(n):
            ang = 2 * np.pi * i / n + rng.uniform(-.12, .12)
            ring = np.array([0, np.cos(ang), np.sin(ang)])
            off = ring * np.array([0, .011, .013]) + rng.normal(0, .002, 3)
            d = np.array([sgn * 1.0, .45, -.15]) + ring * np.array([0, .7, .95])
            length = rng.uniform(.19, .25)
            axis = H.free_path(vol, Gp + off, d, length, K, gravity=2.2, stiff=.1, margin=.03, seed=100 + i + 50 * (sgn > 0))
            T = np.gradient(axis, axis=0)
            T /= np.linalg.norm(T, axis=1, keepdims=True)
            Nf = np.cross(T[0], [0, 0, 1.])
            Nf /= np.linalg.norm(Nf)
            t = np.linspace(0, 1, K)
            rh = (.004 + .019 * smoothstep(0, .3, t) * (1 - .25 * t)) * rng.uniform(.85, 1.15)
            phase = rng.uniform(0, 2 * np.pi)
            turns = rng.uniform(2.8, 3.4)
            pts = []
            for k in range(K):
                if k:
                    Nf = Nf - T[k] * (Nf @ T[k])
                    Nf /= np.linalg.norm(Nf)
                Bf = np.cross(T[k], Nf)
                a = phase + sgn * turns * 2 * np.pi * t[k]
                pts.append(axis[k] + rh[k] * (np.cos(a) * Nf + np.sin(a) * Bf))
            pts = vol.push_out(np.array(pts), .012)
            paths.append(pts)
            widths.append(H.taper(K, rng.uniform(.021, .025), .4) * (.75 + .25 * smoothstep(0, .2, t)))
    pos, nrm, uv, tris, along = H.clump_mesh(paths, widths, vol, sides=7, flat=.95)
    tip = np.clip((along - .2) / .8, 0, 1) * 1.05
    b.bound('pigtails', pos, tris, uv, mat, nrm=nrm, bone='Head', extra_attrs={'_TIP': tip.astype(np.float32)})
    # Mechas cacheadas que emolduram o rosto.
    paths, widths = [], []
    for sgn in (1, -1):
        for i in range(2):
            root = c + np.array([sgn * r[0] * (.62 + i * .14), r[1] * (.42 - i * .08), r[2] * (.7 - i * .14)])
            root = vol.push_out(root[None], .004)[0]
            path = H.free_path(vol, root, np.array([sgn * .35, -1, .3]), rng.uniform(.085, .11), 18, gravity=1, stiff=.3,
                               curl=(.008, 1.6), margin=.008, seed=300 + i + 10 * (sgn > 0))
            paths.append(path)
            widths.append(H.taper(18, rng.uniform(.018, .022), .15))
    pos, nrm, uv, tris, along = H.clump_mesh(paths, widths, vol, sides=6, flat=.55)
    b.bound('locks', pos, tris, uv, mat, nrm=nrm, bone='Head', extra_attrs={'_TIP': (along ** 1.6 * .9).astype(np.float32)})
    # Prendedores: elástico magenta na esquerda e turquesa na direita.
    for sgn, col in ((1, MAGENTA), (-1, TURQ)):
        axis = np.array([sgn * 1.0, .25, 0])
        tp, tn, tt = torus(gathers[sgn] + axis / np.linalg.norm(axis) * .004, axis, .019, .0075, 18, 8)
        tie = flat_material(b, f'tie_{sgn}', col, roughness=.55)
        b.bound(f'tie_{"L" if sgn > 0 else "R"}', tp, tt, np.zeros((len(tp), 2)), tie, nrm=tn, bone='Head')
    return b.save({'tips': True})


# ----------------------------------------------------------------------- chapéu

def jester_hat(model, layout, item_id='hat_jester'):
    L = overlays.Landmarks(model)
    vol = H.HeadVolume(model)
    G.reset_strips()
    ey = L.eye_y
    c = model.coords

    def band_line(P):
        aaz = azimuth(L, P)
        return np.interp(aaz, [0, 60, 100, 140, 180], [ey + .066, ey + .064, ey + .056, ey + .038, ey + .026])

    def ok(v):
        P = c[v]
        return (P[:, 1] > band_line(P) - .002).all()
    s = head_surface(model, layout, ok)
    G.offset(model, s, .032)
    G.smooth(s, 25, keep_boundary=True)
    G.push_out(model, s, .03)
    loop = G.loops(s)[0]
    G.smooth_loop(s, loop, iters=40, rings=4)
    pc, pn = plane_fit(s.pos[loop])
    G.straighten(s, loop, pc, pn, rings=4)
    G.smooth(s, 4, keep_boundary=True)
    G.push_out(model, s, .028)
    loop = G.loops(s)[0]
    G.smooth_loop(s, loop, iters=30, rings=2)
    # Faixa enrolada na borda (desce e abre um pouco).
    G.band(s, loop, lambda P: np.tile(-pn, (len(P), 1)), .022, rows=4, part=1, flare=.013)
    edge_point, edge_n = pc, pn
    G.solidify(s, .004)
    b = ItemBuilder(model, item_id, 'headwear')
    bake = cloth.bake_surface(s, 1024)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    # Posição real (deslocada) para separar as metades e achar a faixa.
    up_d = (p - edge_point) @ edge_n
    half = smoothstep(-.002, .002, p[:, 0])
    alb = cloth.lin_mix(np.tile(cloth.srgb(TURQ), (len(p), 1)), cloth.srgb(MAGENTA), half)
    band = ((part > .5) & (part < 1.5)).astype(float)
    seam = smoothstep(.0025, .001, np.abs(p[:, 0])) * (1 - band)
    rel = p - L.center
    arc = np.arctan2(rel[:, 0], rel[:, 2]) * .1
    dd = np.abs(((arc / .034) % 1) - .5) * .034 / .0085 + np.abs(up_d + .01) / .0075
    dia = smoothstep(1.06, .94, dd)
    alb = cloth.lin_mix(alb, cloth.srgb(BLACK), np.clip(band + seam, 0, 1))
    alb = cloth.lin_mix(alb, cloth.srgb(GOLD), dia * band)
    alb = np.where((part > 1.5)[:, None], alb * .55, alb)
    metal = dia * band * .9
    rough = np.where(band > .5, .45, .6) - metal * .3

    def height(q):
        return (cloth.triplanar(q, n, cloth.twill) * 1.2 + (fbm(q, 30, 3, 5) - .5) * .0014
                + dia * band * .0008)
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=metal)
    mat = tex_material(b, 'cap', a, nm, orm, sheen=((.5, .4, .5), .5))
    b.derived('cap', s, mat)
    # Duas pontas que sobem e caem para os lados, terminando em guizos.
    outer = s.pos[s.part < 1.5] if s.part is not None else s.pos
    tips, ups = [], []
    for sgn, col in ((1, MAGENTA), (-1, TURQ)):
        dirv = np.array([sgn * .78, .62, -.08])
        dirv /= np.linalg.norm(dirv)
        k = np.argmax((outer - vol.center) @ dirv)
        base = outer[k] - dirv * .03
        o = np.array([sgn * 1., 0, -.12])
        up = np.array([0, 1., 0])
        P0 = base
        P1 = base + up * .11 + o * .03
        P2 = base + up * .12 + o * .17
        P3 = base + o * .21 - up * .06
        t = np.linspace(0, 1, 30)[:, None]
        path = (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t ** 2 * P2 + t ** 3 * P3
        tt = t[:, 0]
        rad = .044 * (1 - tt) ** .85 + .0065
        pos, nrm, uv, tris, _ = tube_mesh([path], [rad], sides=16)
        # Tampa na ponta (fecha o tubo; o guizo cobre).
        K, sides = len(path), 16
        tipc = (K - 1) * sides
        tris = np.vstack([tris, [(tipc, tipc + i + 1, tipc + i) for i in range(1, sides - 1)]])
        horn = b.glb.material(f'horn_{sgn}', color=(*lin(col), 1), roughness=.5, clearcoat=(.3, .3))
        b.bound(f'horn_{"L" if sgn > 0 else "R"}', pos, tris, uv, horn, nrm=nrm, bone='Head', rigid=True)
        T = path[-1] - path[-3]
        T /= np.linalg.norm(T)
        tips.append(path[-1] + T * .011)
        ups.append(-T)
    emit_bells(b, 'bells', tips, .015, bone='Head', rigid=True, ups=ups)
    return b.save({})


# ----------------------------------------------------------------------- blusa

def harlequin_top(model, layout, item_id='top_harlequin'):
    A = G.Anatomy(model)
    G.reset_strips()
    hips_y = A.h['Hips'][1]
    crop_y = A.h['Spine1'][1] - .068
    sleeve = .56
    s = G_shirt(model, layout, A, sleeve=sleeve, hem=hips_y - crop_y, ease=.007, sleeve_ease=(.01, .012), drape=.8)
    # Mangas bufantes: volume radial em torno do braço, menor do lado do tronco.
    for side, sgn in (('Left', 1), ('Right', -1)):
        a, f = A.h[f'{side}Arm'], A.h[f'{side}ForeArm']
        axis = (f - a) / np.linalg.norm(f - a)
        m = np.isin(A.bone[s.vid], (f'{side}Arm',))
        rel = s.pos[m] - a
        t = np.clip(rel @ axis / np.linalg.norm(f - a), 0, 1)
        radial = rel - np.outer(rel @ axis, axis)
        rn = radial / np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-9)
        away = np.array([sgn * 1., .6, 0])
        away -= axis * (away @ axis)
        away /= np.linalg.norm(away)
        side_w = .45 + .55 * smoothstep(-.6, .4, rn @ away)
        prof = np.sin(np.pi * np.clip(t / (sleeve - .02), 0, 1)) ** .7 * smoothstep(0, .12, t)
        s.pos[m] += rn * (.026 * prof * side_w)[:, None]
    G.smooth(s, 3, keep_boundary=True)
    Lp = classify_loops(s)
    for loop in Lp['sleeve']:
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        a, f = A.h[f'{side}Arm'], A.h[f'{side}ForeArm']
        axis = (f - a) / np.linalg.norm(f - a)
        G.band(s, loop, lambda P, axis=axis: np.broadcast_to(axis, P.shape).copy(), .014, rows=3, part=1, inward=.016)
    for loop in Lp['hem']:
        G.band(s, loop, lambda P: np.tile([0., -1, 0], (len(P), 1)), .016, rows=3, part=1, inward=.004)
    G.solidify(s, .0024)
    b = ItemBuilder(model, item_id, 'top')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    x = p[:, 0]
    # Losangos no tronco (cilindro vertical) e nas mangas (cilindro do braço).
    u, v, w = cyl_coords(p, np.array([0, 0, .0]), np.array([0, 1., 0]), np.array([0, 0, 1.]), .14, 12)
    wts = lozenges(u, v - crop_y, w, .088)
    for side, sgn in (('Left', 1), ('Right', -1)):
        a, f = A.h[f'{side}Arm'], A.h[f'{side}ForeArm']
        axis = (f - a) / np.linalg.norm(f - a)
        arm = (sgn * x > .17) & (part < .5)
        ua, va, wa = cyl_coords(p[arm], a, axis, np.array([0, 1., 0]), .055, 6)
        wts[arm] = lozenges(ua, va, wa, .07)
    alb = mix3(wts, (BLACK, MAGENTA, TURQ))
    alb *= (1 + .05 * (fbm(p, 25, 3, 4) - .5))[:, None]
    trim = (part > .5) & (part < 1.5)
    alb = np.where(trim[:, None], cloth.srgb(BLACK), alb)
    hem_top = crop_y + .012
    gold_line = smoothstep(.0016, .0007, np.abs(p[:, 1] - (hem_top - .003))) * (np.abs(x) < .17) * trim
    alb = cloth.lin_mix(alb, cloth.srgb(GOLD), gold_line)
    alb = np.where((part > 1.5)[:, None], alb * .6, alb)
    rough = np.where(trim, .5, .42) - gold_line * .2
    hfn = fabric_height(n, 'satin', .0022)

    def height(q):
        gathers = np.zeros(len(q))
        for side, sgn in (('Left', 1), ('Right', -1)):
            a, f = A.h[f'{side}Arm'], A.h[f'{side}ForeArm']
            axis = (f - a) / np.linalg.norm(f - a)
            arm = sgn * q[:, 0] > .17
            uu, vv, _ = cyl_coords(q, a, axis, np.array([0, 1., 0]), .055, 6)
            gathers += arm * np.sin(uu / .0055) * .00045 * smoothstep(.06, .13, vv)
        return hfn(q) + gathers + np.where(trim, cloth.triplanar(q, n, cloth.rib) * .8, 0)
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=gold_line * .9)
    mat = tex_material(b, 'blouse', a, nm, orm, sheen=((.55, .45, .55), .4))
    b.derived('blouse', s, mat)
    # Gola franzida branca, em duas camadas.
    neck_c = A.h['Neck'] + np.array([0, -.004, .004])
    rp, rt, ru = ruff_mesh(A, neck_c, r_in=.06, r_out=.112, pleats=22, rows=5)
    ruff = b.glb.material('ruff', color=(*lin(WHITE), 1), roughness=.6, sheen=((.9, .9, .9), .5), double=True)
    b.bound('ruff', rp, rt, ru, ruff, bone='Spine2')
    edge = b.glb.material('ruff_edge', color=(*lin(GOLD), 1), metallic=.9, roughness=.3)
    # Botões dourados em losango no centro do peito.
    parts = []
    for yy in (A.h['Spine2'][1] + .05, A.h['Spine2'][1] - .01, A.h['Spine1'][1] + .02):
        sel = (np.abs(s.pos[:, 0]) < .015) & (np.abs(s.pos[:, 1] - yy) < .015) & (s.part < .5)
        zf = s.pos[sel, 2].max() if sel.any() else .14
        sp, sn, st = sphere_mesh(np.array([0, yy, zf + .002]), .0085, 4, 2)
        sp = (sp - np.array([0, yy, zf + .002])) * np.array([1, 1.4, .5]) + np.array([0, yy, zf + .002])
        parts.append((sp, sn, st))
    bp, bn, bt = merge(parts)
    b.bound('buttons', bp, bt, np.zeros((len(bp), 2)), edge, nrm=bn, bone='Spine2')
    return b.save({'hides': ['chest', 'upperarm_a', 'upperarm_b']})


# ----------------------------------------------------------------------- short

def puff_shorts(model, layout, item_id='bottom_puff_shorts'):
    A = G.Anatomy(model)
    G.reset_strips()
    s, hem_y, top = shorts_surface(model, layout, A, length=.32, waist=.07, ease=(.006, .03))
    hips_y = A.h['Hips'][1]
    loops = G.loops(s)
    for loop in loops:
        if s.pos[loop, 1].mean() < hips_y - .05:
            # Barra franzida: aperta na coxa e deixa o volume bufante acima.
            G.band(s, loop, lambda P: np.tile([0., -1, 0], (len(P), 1)), .016, rows=3, part=1, inward=.02)
        else:
            G.band(s, loop, lambda P: np.tile([0., 1, 0], (len(P), 1)), .032, rows=3, part=1, inward=.0)
    G.solidify(s, .0024)
    b = ItemBuilder(model, item_id, 'bottom')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    y = p[:, 1]
    u, v, w = cyl_coords(p, np.array([0, 0, .0]), np.array([0, 1., 0]), np.array([0, 0, 1.]), .16, 16)
    wts = lozenges(u, v - top, w, .078, aa=.0005)
    alb = mix3(wts, (BLACK, MAGENTA, TURQ))
    alb *= (1 + .05 * (fbm(p, 25, 3, 4) - .5))[:, None]
    trim = (part > .5) & (part < 1.5)
    belt = trim & (y > top - .03)
    cuff = trim & ~belt
    alb = np.where(cuff[:, None], cloth.srgb(BLACK), alb)
    alb = np.where(belt[:, None], cloth.srgb('#0d0b10'), alb)
    stitch = belt * (smoothstep(.0008, .0003, np.abs(np.abs(y - (top + .016)) - .012)) *
                     (np.abs(((u / .004) % 1) - .5) < .3))
    alb = cloth.lin_mix(alb, cloth.srgb(GOLD), stitch * .8)
    alb = np.where((part > 1.5)[:, None], alb * .6, alb)
    rough = np.where(belt, .32, np.where(cuff, .55, .45))

    def height(q):
        puff = np.where(trim, 0, np.sin(np.arctan2(q[:, 0], q[:, 2]) * 30) * .0007 * smoothstep(top - .06, hem_y, q[:, 1]))
        leather = (fbm(q, 500, 2, 3) - .5) * .00008
        return np.where(belt, leather + stitch * .0002, fabric_height(n, 'satin', .0024)(q) + puff
                        + np.where(cuff, cloth.triplanar(q, n, cloth.rib) * .8, 0))
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height, metal=stitch * .8)
    mat = tex_material(b, 'shorts', a, nm, orm, sheen=((.55, .45, .55), .4), clearcoat=None)
    b.derived('shorts', s, mat)
    # Fivela dourada em losango (moldura) no centro do cinto.
    outer = s.pos[(s.part == 1) & (s.pos[:, 1] > top - .01)]
    zf = outer[np.abs(outer[:, 0]) < .02, 2].max()
    yc = top + .016
    ring_o = np.array([[0, .03], [.038, 0], [0, -.03], [-.038, 0]])
    ring_i = ring_o * .55
    pos, tris = [], []
    for k, (zz, sc) in enumerate(((zf + .002, 1.0), (zf + .007, 1.0))):
        for q in ring_o:
            pos.append((q[0] * sc, yc + q[1] * sc, zz))
        for q in ring_i:
            pos.append((q[0] * sc, yc + q[1] * sc, zz))
    pos = np.array(pos)
    # Faces: frente (z maior) e laterais do anel externo e interno.
    def quad(a, bb, c2, d):
        return [(a, bb, c2), (a, c2, d)]
    f0, f1 = 0, 8
    for i in range(4):
        j = (i + 1) % 4
        tris += quad(f1 + i, f1 + j, f1 + 4 + j, f1 + 4 + i)          # frente
        tris += quad(f0 + i, f1 + i, f1 + j, f0 + j)                  # borda externa
        tris += quad(f0 + 4 + j, f1 + 4 + j, f1 + 4 + i, f0 + 4 + i)  # borda interna
    tris = np.array(tris)
    from model import vertex_normals
    nn = vertex_normals(pos, tris)
    if nn[8:16, 2].mean() < 0:
        tris = tris[:, ::-1]
    gold = b.glb.material('buckle', color=(*lin(GOLD), 1), metallic=.92, roughness=.22)
    # Facetas planas: vértices duplicados por triângulo.
    fp = pos[tris].reshape(-1, 3)
    ft = np.arange(len(fp)).reshape(-1, 3)
    b.bound('buckle', fp, ft, np.zeros((len(fp), 2)), gold, bone='Hips', rigid=True)
    gp, gn, gt = sphere_mesh(np.array([0, yc, zf + .005]), .007, 4, 2)
    gp = (gp - [0, yc, zf + .005]) * [1, 1.3, .6] + [0, yc, zf + .005]
    gem = b.glb.material('gem', color=(*lin(MAGENTA), 1), roughness=.1, clearcoat=(1, .03))
    b.bound('gem', gp, gt, np.zeros((len(gp), 2)), gem, nrm=gn, bone='Hips', rigid=True)
    # Abas pontudas (cauda de arlequim) penduradas do cinto, alternando as cores.
    ref = s.pos[s.part < 1.5]
    th = np.arctan2(ref[:, 0], ref[:, 2])
    rr = np.hypot(ref[:, 0], ref[:, 2])
    tree = cKDTree(np.stack([th * .16, ref[:, 1]], 1))
    flap_y0 = top - .002
    length = .13
    flaps = [(-1.05, MAGENTA), (1.05, TURQ), (-1.8, TURQ), (1.8, MAGENTA), (-2.5, MAGENTA), (2.5, TURQ), (np.pi, TURQ)]
    bells = []
    mats = {col: b.glb.material(f'flap_{col[1:]}', color=(*lin(col), 1), roughness=.5, sheen=((.6, .5, .6), .45), double=True)
            for col in (MAGENTA, TURQ)}
    for k, (th0, col) in enumerate(flaps):
        rows, cols = 10, 9
        pts = []
        for i in range(rows):
            t = i / (rows - 1)
            hw = .04 * (1 - t) ** .95 + .0015
            yy = flap_y0 - t * length
            for j in range(cols):
                sx = -1 + 2 * j / (cols - 1)
                pts.append((th0 + sx * hw / .16, yy, t))
        pts = np.array(pts)
        _, idx = tree.query(np.stack([pts[:, 0] * .16, pts[:, 1]], 1), k=24)
        R = rr[idx].max(1) + .006 + pts[:, 2] * .012
        R = R.reshape(rows, cols)
        for _ in range(3):
            R[:, 1:-1] = .5 * R[:, 1:-1] + .25 * (R[:, :-2] + R[:, 2:])
            R[1:-1] = .5 * R[1:-1] + .25 * (R[:-2] + R[2:])
        R = R.reshape(-1)
        P = np.stack([np.sin(pts[:, 0]) * R, pts[:, 1], np.cos(pts[:, 0]) * R], 1)
        tr = []
        for i in range(rows - 1):
            for j in range(cols - 1):
                a0 = i * cols + j
                tr += [(a0, a0 + cols, a0 + 1), (a0 + 1, a0 + cols, a0 + cols + 1)]
        tr = np.array(tr)
        nn = vertex_normals(P, tr)
        out = np.stack([np.sin(pts[:, 0]), np.zeros(len(P)), np.cos(pts[:, 0])], 1)
        if (nn * out).sum() < 0:
            tr = tr[:, ::-1]
        uvf = np.stack([pts[:, 0], pts[:, 2]], 1)
        b.bound(f'flap_{k}', P, tr, uvf, mats[col])
        tipp = P[(rows - 1) * cols + cols // 2]
        bells.append(tipp + np.array([np.sin(th0), 0, np.cos(th0)]) * .006 - np.array([0, .012, 0]))
    emit_bells(b, 'bells', bells, .011)
    return b.save({'hides': ['hips']})


# ----------------------------------------------------------------------- meias

def harlequin_socks(model, layout, item_id='socks_harlequin'):
    A = G.Anatomy(model)
    G.reset_strips()
    top_t = .5

    def ok(v):
        bb = A.bone[v]
        thigh = np.isin(bb, ('LeftUpLeg', 'RightUpLeg')) & (A.t[v] > top_t)
        shin = np.isin(bb, ('LeftLeg', 'RightLeg'))
        foot = np.isin(bb, ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'))
        return (thigh | shin | foot).all()
    s = G.surface(model, G.select(layout, ok))
    G.offset(model, s, .0019)
    G.smooth(s, 2, keep_boundary=True)
    for loop in G.loops(s):
        side = 'Left' if s.pos[loop, 0].mean() > 0 else 'Right'
        h, k = A.h[f'{side}UpLeg'], A.h[f'{side}Leg']
        axis = (h - k) / np.linalg.norm(h - k)
        G.straighten(s, loop, s.pos[loop].mean(0), axis, rings=2)
    G.solidify(s, .0018)
    b = ItemBuilder(model, item_id, 'socks')
    bake = cloth.bake_surface(s)
    p = bake.pos[bake.mask].astype(np.float64)
    n = bake.nrm[bake.mask]
    part = bake.at('part')[:, 0]
    alb = np.zeros((len(p), 3))
    cuff = np.zeros(len(p))
    for side, sgn, base, dia_c, cuff_c in (('Left', 1, BLACK, MAGENTA, MAGENTA), ('Right', -1, WHITE, TURQ, BLACK)):
        m = np.sign(p[:, 0]) == sgn
        q = p[m]
        hip, knee, ank = A.h[f'{side}UpLeg'], A.h[f'{side}Leg'], A.h[f'{side}Foot']
        above = q[:, 1] > knee[1]
        center = np.where(above[:, None], knee + np.outer((q[:, 1] - knee[1]) / (hip[1] - knee[1]), hip - knee),
                          ank + np.outer((q[:, 1] - ank[1]) / (knee[1] - ank[1]), knee - ank))
        rel = q - center
        ang = np.arctan2(rel[:, 0] * sgn, rel[:, 2])
        R0, cols = .05, 6
        u = ang * R0
        wts = checker_diamonds(u, q[:, 1], 2 * np.pi * R0 / cols, .07)
        top_y = s.pos[s.pos[:, 0] * sgn > 0, 1].max()
        cm = smoothstep(top_y - .028, top_y - .024, q[:, 1])
        col = cloth.lin_mix(np.tile(cloth.srgb(base), (len(q), 1)), cloth.srgb(dia_c), wts)
        col = cloth.lin_mix(col, cloth.srgb(cuff_c), cm)
        stripe = smoothstep(.0014, .0006, np.abs(q[:, 1] - (top_y - .03)))
        col = cloth.lin_mix(col, cloth.srgb(GOLD), stripe)
        alb[m] = col
        cuff[m] = np.maximum(cm, stripe)
    alb *= (1 + .04 * (fbm(p, 40, 3, 6) - .5))[:, None]
    alb = np.where((part > 1.5)[:, None], alb * .7, alb)
    rough = np.full(len(p), .7)
    cuff_m = cuff

    def height(q):
        h = cloth.triplanar(q, n, lambda u, v: cloth.knit(u, v, .0014)) * .8
        return h + cuff_m * cloth.triplanar(q, n, lambda u, v: cloth.rib(u, v, .003)) * 1.4
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), rough, height)
    mat = tex_material(b, 'socks', a, nm, orm, sheen=((.45, .4, .45), .6))
    b.derived('socks', s, mat, weight_smooth=1)
    return b.save({'hides': ['thigh_d', 'shin_a', 'shin_b', 'shin_c', 'shin_d', 'feet']})


# ----------------------------------------------------------------------- botinhas

def jester_boots(model, layout, item_id='shoes_jester'):
    A = G.Anatomy(model)
    G.reset_strips()
    s = shoe_shell(model, layout, A, collar_t=.7, ease=.0065, base_y=.018)
    # Parâmetros do bico enrolado (calculados no casco original) e casco recolhido para dentro do tubo.
    orig = s.pos.copy()
    toes = {}
    for side, sgn in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        sp = orig[np.sign(orig[:, 0]) == sgn]
        ofw = (sp - ankle) @ f
        low = sp[:, 1] < .07
        tip_fw = ofw[low].max()
        mid_lt = ((sp[low & (ofw > tip_fw - .03)] - ankle) @ lat).mean()
        base = ankle * np.array([1, 0, 1]) + f * (tip_fw - .09) + lat * mid_lt + np.array([0, .042, 0])
        toes[side] = (tip_fw, base)
        m = np.sign(s.pos[:, 0]) == sgn
        rel = s.pos[m] - base
        fw = rel @ f
        k = smoothstep(.0, .035, fw)[:, None]
        lt = rel @ lat
        up = rel[:, 1]
        squeeze = np.outer(lt * .3, lat) + np.outer(up * .3, [0, 1., 0])
        s.pos[m] = s.pos[m] - squeeze * k - np.outer(np.clip(fw - .03, 0, None) * .5, f) * k
    b = ItemBuilder(model, item_id, 'shoes')
    bake = cloth.bake_surface(s, 2048)
    p = bake.pos[bake.mask].astype(np.float64)
    part = bake.at('part')[:, 0]
    alb = np.zeros((len(p), 3))
    metal = np.zeros(len(p))
    cols = {1: MAGENTA, -1: TURQ}
    for side, sgn in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        m = np.sign(p[:, 0]) == sgn
        q = p[m]
        rel = q - ankle
        fw, lt = rel @ f, rel @ lat
        col = np.tile(cloth.srgb(cols[sgn]), (len(q), 1))
        top_y = s.pos[np.sign(s.pos[:, 0]) == sgn, 1].max()
        collar = smoothstep(top_y - .024, top_y - .02, q[:, 1])
        col = cloth.lin_mix(col, cloth.srgb(BLACK), collar)
        piping = smoothstep(.0016, .0006, np.abs(q[:, 1] - (top_y - .022)))
        col = cloth.lin_mix(col, cloth.srgb(GOLD), piping)
        alb[m] = col
        metal[m] = piping * .9
    alb = np.where((part > 1.5)[:, None], cloth.srgb(BLACK) * .6, alb)

    def height(q):
        return (fbm(q, 600, 2, 3) - .5) * .00005 + (fbm(q, 40, 2, 5) - .5) * .0004 + metal * .0005
    a, nm, orm = cloth.finish(bake, np.clip(alb, 0, 1), np.full(len(p), .28) - metal * .1, height, metal=metal)
    upper = tex_material(b, 'leather', a, nm, orm, clearcoat=(.8, .1))
    b.derived('upper', s, upper, weight_smooth=2)
    sole_mat = flat_material(b, 'sole', '#121014', roughness=.5)
    heel_mat = b.glb.material('heel', color=(*lin(GOLD), 1), metallic=.9, roughness=.28)
    bells, ups = [], []
    for side, sgn in (('Left', 1), ('Right', -1)):
        ankle, f, lat = foot_frame(A, side)
        side_pos = orig[(np.sign(orig[:, 0]) == sgn)]
        fw = (side_pos - ankle) @ f
        # Sola fina contínua + plataforma na frente + salto dourado atrás (vão no arco do pé).
        pos, uv, tris, _, _ = sole_mesh(SimpleNamespace(pos=side_pos), sgn, y_bottom=-.008, y_top=.025, flare=.004)
        b.bound(f'sole_{side}', pos, tris, uv, sole_mat, bone=f'{side}Foot')
        pos, uv, tris, _, _ = sole_mesh(SimpleNamespace(pos=side_pos[fw > .035]), sgn, y_bottom=-.022, y_top=-.006, flare=.003)
        b.bound(f'platform_{side}', pos, tris, uv, sole_mat, bone=f'{side}Foot')
        heel_pts = side_pos[fw < -.005].copy()
        hc = heel_pts.mean(0)
        heel_pts[:, [0, 2]] = hc[[0, 2]] + (heel_pts[:, [0, 2]] - hc[[0, 2]]) * .82
        pos, uv, tris, _, _ = sole_mesh(SimpleNamespace(pos=heel_pts), sgn, y_bottom=-.022, y_top=-.006, flare=.0)
        b.bound(f'heel_{side}', pos, tris, uv, heel_mat, bone=f'{side}Foot')
        # Bico enrolado: tubo elíptico que sai da biqueira, sobe e enrola para trás.
        tip_fw, base = toes[side]
        P1 = base + f * .105 + np.array([0, -.008, 0])
        seg1 = [base + (P1 - base) * t for t in np.linspace(0, 1, 10)]
        Rc = .03
        C = P1 + np.array([0, Rc, 0])
        spiral = []
        for k, ang in enumerate(np.linspace(-np.pi / 2, np.pi * .95, 22)[1:]):
            rr = Rc * (1 - .45 * (k / 21))
            spiral.append(C + f * np.cos(ang) * rr + np.array([0, 1., 0]) * np.sin(ang) * rr)
        path = np.array(seg1 + spiral)
        L_ = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        tt = L_ / L_[-1]
        wx = .043 * (1 - tt) ** 1.1 + .005
        wy = .03 * (1 - tt) ** 1.1 + .005
        tp, tn, tuv, ttr = ellipse_tube(path, lat, wx, wy)
        toe_mat = b.glb.material(f'toe_{side}', color=(*lin(cols[sgn]), 1), roughness=.28, clearcoat=(.8, .1))
        b.bound(f'toe_{side}', tp, ttr, tuv, toe_mat, nrm=tn, bone=f'{side}Foot')
        T = path[-1] - path[-2]
        T /= np.linalg.norm(T)
        bells.append(path[-1] + T * .009)
        ups.append(-T)
    for side, sgn, bb, uu in (('Left', 1, bells[0], ups[0]), ('Right', -1, bells[1], ups[1])):
        emit_bells(b, f'bell_{side}', [bb], .011, bone=f'{side}Foot', ups=[uu])
    return b.save({'hides': ['feet', 'shin_d'], 'lift': .022})


# ----------------------------------------------------------------------- luvas

def ruffle_mesh(center, axis, r_in, r_out, length, pleats=18, rows=5, k=144):
    """Babado em cone: sai do punho e abre em pregas na direção de `axis`."""
    axis = axis / np.linalg.norm(axis)
    ref = np.array([0, 1., 0]) if abs(axis[1]) < .9 else np.array([1., 0, 0])
    u = np.cross(axis, ref)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    pos, tris = [], []
    for r in range(rows):
        f = r / (rows - 1)
        rr = r_in + (r_out - r_in) * f ** 1.2
        for i in range(k):
            a = 2 * np.pi * i / k
            pleat = np.sin(a * pleats) * .0065 * f ** 1.1
            d = np.cos(a) * u + np.sin(a) * v
            pos.append(center + axis * length * f + d * (rr + pleat) + axis * np.cos(a * pleats) * .003 * f)
    for r in range(rows - 1):
        for i in range(k):
            a, bb = r * k + i, r * k + (i + 1) % k
            tris += [(a, a + k, bb), (bb, a + k, bb + k)]
    return np.array(pos), np.array(tris)


def ruffle_gloves(model, layout, item_id='gloves_ruffle'):
    A = G.Anatomy(model)
    b = ItemBuilder(model, item_id, 'hands')

    def is_glove(v):
        bb = A.bone[v]
        hand = np.array(['Hand' in x for x in bb])
        fore = np.isin(bb, ('LeftForeArm', 'RightForeArm')) & (A.t[v] > .86)
        return (hand | fore).all()
    faces = [corners for mat, corners in layout.faces if mat == 'body' and is_glove(np.array([v for v, _ in corners]))]
    glove = b.glb.material('glove', color=(*lin('#141117'), 1), roughness=.34, clearcoat=(.5, .18), sheen=((.3, .25, .3), .4))
    b.skin_layer('glove', faces, .0011, glove)
    ruff = b.glb.material('cuff', color=(*lin(WHITE), 1), roughness=.6, sheen=((.9, .9, .9), .5), double=True)
    c = model.coords
    for side, sgn in (('Left', 1), ('Right', -1)):
        a, f = A.h[f'{side}ForeArm'], A.h[f'{side}Hand']
        axis = (f - a) / np.linalg.norm(f - a)
        cen = a + (f - a) * .86
        sel = (A.bone == f'{side}ForeArm') & (np.abs((c - cen) @ axis) < .012)
        rel = c[sel] - cen
        radial = rel - np.outer(rel @ axis, axis)
        r_in = np.linalg.norm(radial, axis=1).max() + .002
        pos, tris = ruffle_mesh(cen, -axis, r_in, r_in + .026, .034)
        b.bound(f'ruffle_{side}', pos, tris, np.zeros((len(pos), 2)), ruff, bone=f'{side}ForeArm')
        # Guizo pendurado na borda de fora do babado.
        out = np.array([sgn * 1., -.4, 0])
        out -= axis * (out @ axis)
        out /= np.linalg.norm(out)
        bc = cen - axis * .036 + out * (r_in + .03)
        emit_bells(b, f'bell_{side}', [bc], .0085, bone=f'{side}ForeArm')
    return b.save({'hides': ['hands']})


# ----------------------------------------------------------------------- bomba

def uv_sphere(center, radius, F, U, seg=40, rings=24):
    S = np.cross(U, F)
    pos, nrm, uv = [], [], []
    for i in range(rings + 1):
        th = np.pi * i / rings
        for j in range(seg + 1):
            ph = 2 * np.pi * j / seg
            d = np.cos(th) * U + np.sin(th) * (np.cos(ph) * F + np.sin(ph) * S)
            pos.append(center + d * radius)
            nrm.append(d)
            uv.append((j / seg, i / rings))
    tris = []
    for i in range(rings):
        for j in range(seg):
            a, bb = i * (seg + 1) + j, i * (seg + 1) + j + 1
            c2, d2 = a + seg + 1, bb + seg + 1
            tris += [(a, c2, bb), (bb, c2, d2)]
    pos, tris = np.array(pos), np.array(tris)
    from model import vertex_normals
    if (vertex_normals(pos, tris) * np.array(nrm)).sum() < 0:
        tris = tris[:, ::-1]
    return pos, np.array(nrm), np.array(uv), tris


def bomb_texture(size=512):
    h, w = size // 2, size
    yy, xx = np.mgrid[0:h, 0:w]
    th = np.pi * (yy + .5) / h
    ph = 2 * np.pi * (xx + .5) / w
    # Base local: x = lado, y = cima, z = frente.
    dx, dy, dz = np.sin(th) * np.sin(ph), np.cos(th), np.sin(th) * np.cos(ph)
    front = dz > 0
    X, Y = dx, dy
    col = np.zeros((h, w, 3))
    col[:] = cloth.srgb('#1c1a2e')
    shade = .9 + .1 * fbm(np.stack([dx.ravel(), dy.ravel(), dz.ravel()], 1), 6, 2, 3).reshape(h, w)
    col *= shade[..., None]
    aa = .012

    def mask(sd):
        return np.clip(.5 - sd / aa, 0, 1) * front
    for sx in (-1, 1):
        e = np.hypot((X - sx * .26) / .13, (Y - .2) / .17) - 1
        col = cloth.lin_mix(col, cloth.srgb('#f6f2ea'), mask(e * .13))
        pupil = np.hypot((X - sx * .23) / .065, (Y - .17) / .085) - 1
        col = cloth.lin_mix(col, cloth.srgb('#121018'), mask(pupil * .065))
        glint = np.hypot(X - sx * .2, Y - .22) - .02
        col = cloth.lin_mix(col, cloth.srgb('#ffffff'), mask(glint))
        brow = np.abs(np.hypot((X - sx * .27) / .2, (Y - .34) / .12) - 1) * .12 - .015
        col = cloth.lin_mix(col, cloth.srgb(MAGENTA if sx > 0 else TURQ), mask(brow) * (Y > .36))
        cheek = np.hypot(X - sx * .5, Y + .1) - .085
        col = cloth.lin_mix(col, cloth.srgb(MAGENTA), mask(cheek) * .8)
    top = -.08 + .55 * X ** 2
    bottom_ = -.12 - np.sqrt(np.clip(.2 - X ** 2 / 1.6, 0, None)) * 1.0
    mouth = np.maximum(-(Y - bottom_), Y - top)
    mouth_m = mask(mouth) * (np.abs(X) < .5)
    col = cloth.lin_mix(col, cloth.srgb('#8a0f2c'), mouth_m)
    teeth = mouth_m * (Y > top - .07) * (np.abs(((X / .075) % 1) - .5) > .06)
    col = cloth.lin_mix(col, cloth.srgb('#fbf7ee'), teeth)
    tongue = mask(np.hypot(X / 1.4, Y - bottom_ - .03) - .08) * mouth_m
    col = cloth.lin_mix(col, cloth.srgb('#e0477a'), tongue)
    outline = np.clip(1 - np.abs(mouth) / .014, 0, 1) * front * (np.abs(X) < .5)
    col = cloth.lin_mix(col, cloth.srgb('#08070c'), outline * .9)
    return Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8), 'RGB')


def smiling_bomb(model, layout, item_id='prop_bomb'):
    b = ItemBuilder(model, item_id, 'prop')
    hd = model.heads
    hand, mid = hd['RightHand'], hd['RightHandMiddle1']
    idx, pky = hd['RightHandIndex1'], hd['RightHandPinky1']
    fwd = (mid - hand) / np.linalg.norm(mid - hand)
    side = idx - pky
    side -= fwd * (side @ fwd)
    side /= np.linalg.norm(side)
    n = np.cross(fwd, side)
    # Palma: o polegar fica do lado da palma.
    if n @ (hd['RightHandThumb2'] - (hand + mid) / 2) < 0:
        n = -n
    palm = hand + (mid - hand) * .6
    R = .056
    center = palm + n * (R + .028)
    F = fwd - n * (fwd @ n)
    F /= np.linalg.norm(F)
    pos, nrm, uv, tris = uv_sphere(center, R, F, n)
    tex = b.glb.texture(bomb_texture(), fmt='webp', quality=92)
    body = b.glb.material('bomb', base=tex, roughness=.3, clearcoat=(1, .06))
    b.bound('bomb', pos, tris, uv, body, nrm=nrm, bone='RightHand', rigid=True)
    gold = b.glb.material('cap', color=(*lin(GOLD), 1), metallic=.9, roughness=.25)
    cp, cn, ct = cylinder(center + n * (R * .9), n, .02, .016, 24)
    rp, rn, rt = torus(center + n * (R * .9 + .016), n, .02, .0035, 20, 6)
    pp, pn_, pt = merge([(cp, cn, ct), (rp, rn, rt)])
    b.bound('cap', pp, pt, np.zeros((len(pp), 2)), gold, nrm=pn_, bone='RightHand', rigid=True)
    # Pavio torcido que sobe e curva, com faísca na ponta.
    base = center + n * (R * .9 + .014)
    t = np.linspace(0, 1, 16)[:, None]
    path = base + n * (.045 * np.sin(t * np.pi * .55)) - F * (.03 * t ** 1.6) + side * (.008 * np.sin(t * 7))
    fp, fn, fuv, ftr, _ = tube_mesh([path], [np.full(16, .0042)], sides=8)
    fuse = b.glb.material('fuse', color=(*lin('#c9a46a'), 1), roughness=.85)
    b.bound('fuse', fp, ftr, fuv, fuse, nrm=fn, bone='RightHand', rigid=True)
    tip = path[-1]
    rng = np.random.default_rng(3)
    spos, stri = [], []
    for k in range(9):
        d = rng.normal(0, 1, 3)
        d /= np.linalg.norm(d)
        o = np.cross(d, [0, 1., 0])
        if np.linalg.norm(o) < .1:
            o = np.cross(d, [1., 0, 0])
        o /= np.linalg.norm(o)
        L_ = rng.uniform(.012, .022)
        base_i = len(spos)
        spos += [tip + o * .003, tip + d * L_, tip - o * .003]
        stri.append((base_i, base_i + 1, base_i + 2))
    spark = b.glb.material('spark', color=(1, .85, .3, 1), roughness=.5, emissive=(1, .6, .1), double=True)
    b.bound('spark', np.array(spos), np.array(stri), np.zeros((len(spos), 2)), spark, bone='RightHand', rigid=True)
    gp, gn, gt = sphere_mesh(tip, .0055, 8, 6)
    glow = b.glb.material('glow', color=(1, .95, .6, 1), roughness=.4, emissive=(1, .85, .35))
    b.bound('glow', gp, gt, np.zeros((len(gp), 2)), glow, nrm=gn, bone='RightHand', rigid=True)
    return b.save({'grip': 'open', 'hand': 'Right'})


# ----------------------------------------------------------------------- pintura

def diamond_paint(model, layout, item_id='facepaint_diamond'):
    bake = overlays.head_bake(model, layout)
    L = overlays.Landmarks(model)
    p = bake.pos[bake.mask].astype(np.float64)
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    ex, ey = L.eye_x, L.eye_y
    cx, cy = ex + .002, ey - .03
    dd = np.abs(x - cx) / .0085 + np.abs(y - cy) / .0165
    front = (z > L.eyeL[2] - .03) & (x > 0)
    edge = .045
    inner = smoothstep(1 + edge, 1 - edge, dd) * front
    ring = smoothstep(1 + edge, 1 - edge, dd) * smoothstep(.62 - edge, .62 + edge, dd) * front
    col = np.tile(cloth.srgb('#121016'), (len(p), 1))
    small = np.abs(x - (cx + .002)) / .0035 + np.abs(y - (cy - .026)) / .006
    small_m = smoothstep(1.1, .9, small) * front
    col = cloth.lin_mix(col, cloth.srgb(MAGENTA), small_m)
    alpha = np.clip(inner * .95 + small_m * .95, 0, 1)
    img = np.zeros((overlays.SIZE, overlays.SIZE, 4), np.float32)
    img[bake.mask, :3] = col
    img[bake.mask, 3] = alpha
    img = dilate(img, bake.mask)
    tex = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGBA')
    b = ItemBuilder(model, item_id, 'bodyart')
    mat = b.glb.material('paint', color=(1, 1, 1, 1), base=b.glb.texture(tex, fmt='webp', quality=90), roughness=.5,
                         alpha=('BLEND', 0), extras={'overlay': True})
    faces = overlays.faces_in(layout, model, alpha)
    b.skin_layer('paint', faces, .00045, mat)
    return b.save({})


def register(item):
    item('hair_curly_pigtails', 'hair')(curly_pigtails)
    item('hat_jester', 'headwear')(jester_hat)
    item('top_harlequin', 'top')(harlequin_top)
    item('bottom_puff_shorts', 'bottom')(puff_shorts)
    item('socks_harlequin', 'socks')(harlequin_socks)
    item('shoes_jester', 'shoes')(jester_boots)
    item('gloves_ruffle', 'hands')(ruffle_gloves)
    item('prop_bomb', 'prop')(smiling_bomb)
    item('facepaint_diamond', 'bodyart')(diamond_paint)
