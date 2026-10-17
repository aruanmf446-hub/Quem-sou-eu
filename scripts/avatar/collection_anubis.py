"""Coleção Guardião Anúbis: máscara de chacal com nemes, colar usekh, faixas,
saiote cerimonial, manto, braceletes, grevas e cetro solar.

Formas orgânicas (cabeça de chacal, orelhas, cetro) são modeladas por campos de
distância com união suave e extraídas por marching cubes; roupas derivam da
anatomia (pesos e morphs transferidos automaticamente).
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.spatial import ConvexHull

import cloth
import garments as G
from items import ItemBuilder
from model import top4, vertex_normals
from raster import fbm, smoothstep
from wardrobe2 import flat_material, lin, tex_material

GOLD = '#e2b14a'
GOLD_DARK = '#a8741f'
LAPIS = '#2a49a8'
NIGHT = '#24264a'
LINEN = '#f1e8d3'


# --------------------------------------------------------------------------- utilidades

def smin(a, b, k):
    h = np.clip(.5 + .5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def sd_ellipsoid(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=-1)
    k1 = np.linalg.norm(q / r, axis=-1)
    return k0 * (k0 - 1) / np.maximum(k1, 1e-9)


def sd_round_cone(p, a, b, r1, r2):
    """Cone arredondado entre a (raio r1) e b (raio r2)."""
    ba = b - a
    l2 = (ba * ba).sum()
    pa = p - a
    t = np.clip((pa * ba).sum(-1) / l2, 0, 1)
    d = np.linalg.norm(pa - t[..., None] * ba, axis=-1)
    return d - (r1 + (r2 - r1) * t)


def sd_capsule(p, a, b, r):
    return sd_round_cone(p, a, b, r, r)


def sd_box(p, c, half, r=0.0):
    q = np.abs(p - c) - half + r
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(-1), 0) - r


def implicit_mesh(fn, lo, hi, step=.0025, err=.0004):
    """Extrai a isosuperfície 0 de fn (pontos (N,3) -> distâncias) por marching cubes."""
    from skimage.measure import marching_cubes
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    n = np.ceil((hi - lo) / step).astype(int) + 1
    xs = [np.linspace(lo[i], lo[i] + (n[i] - 1) * step, n[i]) for i in range(3)]
    X, Y, Z = np.meshgrid(*xs, indexing='ij')
    pts = np.stack([X, Y, Z], -1).reshape(-1, 3)
    vals = fn(pts).reshape(n)
    verts, faces, _, _ = marching_cubes(vals, 0.0, spacing=(step, step, step))
    verts = verts + lo
    if err:
        used, faces = simplify(verts, faces, .02, err)
        verts = verts[used]
    eps = step * .5
    g = np.stack([(fn(verts + e) - fn(verts - e)) / (2 * eps) for e in np.eye(3) * eps], -1)
    nrm = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
    return verts, nrm, faces


_SIMPLIFY_JS = """
import { MeshoptSimplifier as S } from 'meshoptimizer';
import { readFileSync, writeFileSync } from 'node:fs';
await S.ready;
const [, inV, inF, out, target, err] = process.argv;
const v = new Float32Array(readFileSync(inV).buffer.slice(0));
const f = new Uint32Array(readFileSync(inF).buffer.slice(0));
const [idx] = S.simplify(f, v, 3, Number(target), Number(err), ['ErrorAbsolute']);
writeFileSync(out, Buffer.from(idx.buffer, idx.byteOffset, idx.byteLength));
"""


def simplify(V, F, ratio, error=.0006):
    """Reduz triângulos com o simplificador do meshoptimizer (já dependência do projeto) mantendo os vértices originais."""
    import os
    import subprocess
    import tempfile
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    with tempfile.TemporaryDirectory() as tmp:
        pv, pf, po = (os.path.join(tmp, n) for n in ('v.bin', 'f.bin', 'o.bin'))
        V.astype(np.float32).tofile(pv)
        F.astype(np.uint32).tofile(pf)
        subprocess.run(['node', '--input-type=module', '-e', _SIMPLIFY_JS, pv, pf, po, str(max(1, int(len(F) * ratio)) * 3), str(error)],
                       check=True, cwd=root)
        F2 = np.fromfile(po, np.uint32).reshape(-1, 3).astype(np.int64)
    used = np.unique(F2)
    remap = np.full(len(V), -1)
    remap[used] = np.arange(len(used))
    return used, remap[F2]


def bone_weights(model, n, pairs):
    W = np.zeros((n, len(model.bone_names)), np.float32)
    for bone, w in pairs:
        W[:, model.bone_index(bone)] += w
    return W


def region_fit_morphs(model, verts_ids, center, pos, skip_expr=True):
    """Morphs rígidos (translação + escala por eixo) ajustados a um grupo de vértices do corpo."""
    out = {}
    P = model.coords[verts_ids]
    rel = P - center
    den = (rel * rel).sum(0)
    for name in model.morph_names:
        if skip_expr and name.startswith('expr_'):
            continue
        d = model.morphs[name][verts_ids]
        if np.abs(d).max() < 2e-4:
            continue
        t = d.mean(0)
        s = ((d - t) * rel).sum(0) / den
        out[name] = t + s * (pos - center)
    return out


def blend_morphs(model, pos, w_rigid, rigid_ids, center, min_d=.002):
    """w_rigid * ajuste rígido (cabeça) + (1 - w_rigid) * morphs da pele mais próxima (pescoço, peito)."""
    rigid = region_fit_morphs(model, rigid_ids, center, pos)
    out = {}
    w = np.asarray(w_rigid, float)[:, None]
    if (w < .999).any():
        ids, bary, _ = model.bind(pos)
        surf = {k: v for k, v in model.bound_morphs(ids, bary).items() if not k.startswith('expr_')}
    else:
        surf = {}
    for k in set(rigid) | set(surf):
        d = w * rigid.get(k, 0) + (1 - w) * surf.get(k, 0)
        d = np.broadcast_to(d, pos.shape)
        if np.abs(d).max() > min_d:
            out[k] = d
    return out


def emit(b, name, pos, nrm, uv, tris, mat, W, morphs, attrs=None):
    print(f"    {name}: {len(pos)} v, {len(tris)} t, {len(morphs)} morphs")
    b._emit(name, np.asarray(pos, float), np.asarray(nrm, float), np.asarray(uv, float), np.asarray(tris), mat, W,
            {k: v for k, v in morphs.items() if np.abs(v).max() > 2e-4}, attrs)


def stripe_texture(colors, widths, size=(64, 1024), bevel=.12):
    """Textura de listras horizontais (eixo v) com fio dourado em relevo leve no albedo."""
    w, h = size
    v = (np.arange(h) + .5) / h
    cum = np.cumsum(widths) / np.sum(widths)
    idx = np.searchsorted(cum, (v * 1.0) % 1.0)
    img = np.array([cloth.srgb(colors[i % len(colors)]) for i in idx])
    # Sombreamento suave nas divisas (aspecto pintado).
    edge = np.min(np.abs(v[:, None] - np.concatenate([[0], cum])[None]), axis=1)
    img = img * (1 - .18 * np.exp(-(edge / (bevel / len(widths))) ** 2))[:, None]
    arr = np.repeat(img[:, None, :], w, 1)
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), 'RGB'), idx


def noise_normal(size=256, freq=24, strength=1.5, seed=3):
    yy, xx = np.mgrid[0:size, 0:size] / size
    pts = np.stack([xx.ravel() * freq, yy.ravel() * freq * .35, np.zeros(size * size)], 1)
    h = fbm(pts, 1, 3, seed).reshape(size, size)
    gx = np.gradient(h, axis=1) * size / freq * strength
    gy = np.gradient(h, axis=0) * size / freq * strength
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return Image.fromarray(((n * .5 + .5) * 255).astype(np.uint8), 'RGB')


def head_ids(model):
    c = model.coords[:13380]
    return np.flatnonzero(c[:, 1] > model.heads['Neck'][1] + .03)


class BodyField:
    """Distância com sinal até a pele (corpo alisado), opcionalmente só das faces de alguns ossos."""

    def __init__(self, model, bones=None, smooth=True):
        self.m = model
        self.coords = model.smoothed() if smooth else model.coords
        tris = model.body_tris
        if bones is not None:
            dom = np.array(model.bone_names)[np.argmax(model.weights, 1)]
            tris = tris[np.isin(dom[tris], bones).any(1)]
        self.tris = tris
        self.nrm = vertex_normals(self.coords, model.body_tris)

    def __call__(self, P):
        P = np.asarray(P, float).reshape(-1, 3)
        ids, bary, off = self.m.bind(P, self.tris, coords=self.coords)
        n = (self.nrm[ids] * bary[..., None]).sum(1)
        d = np.linalg.norm(off, axis=1)
        return np.where((off * n).sum(1) < 0, -d, d)

    def project(self, p, direction, start=.25, gap=.0):
        """Ponto a `gap` da pele ao longo de uma reta (busca por bisseção)."""
        p, direction = np.asarray(p, float), np.asarray(direction, float) / np.linalg.norm(direction)
        lo, hi = 0.0, start
        for _ in range(40):
            mid = (lo + hi) / 2
            if self(p + direction * mid)[0] > gap:
                lo = mid
            else:
                hi = mid
        q = p + direction * lo
        e = 1e-3
        g = np.array([(self(q + v)[0] - self(q - v)[0]) / (2 * e) for v in np.eye(3) * e])
        return q, g / np.linalg.norm(g)


def shell(field, region, g0, g1, prefilter=.012):
    """SDF de casca entre g0 e g1 da pele, recortada por `region` (SDF da área coberta)."""
    def fn(p):
        r = region(p)
        d = np.full(len(p), .05)
        m = r < prefilter
        if m.any():
            d[m] = field(p[m])
        a = g0(p) if callable(g0) else np.full(len(p), g0)
        b_ = g1(p) if callable(g1) else np.full(len(p), g1)
        sh = np.abs(d - (a + b_) / 2) - (b_ - a) / 2
        return smax(sh, r, .002)
    return fn


def skin_bind(model, pos, bones=None, rigid_bone=None, weight_bones=None):
    """Pesos e morphs (sem expressões) da pele mais próxima; rigid_bone força o osso."""
    tris = model.body_tris
    if bones is not None:
        dom = np.array(model.bone_names)[np.argmax(model.weights, 1)]
        tris = tris[np.isin(dom[tris], bones).all(1)]
    ids, bary, _ = model.bind(pos, tris)
    if rigid_bone:
        W = bone_weights(model, len(pos), [(rigid_bone, 1)])
    else:
        W = model.bound_weights(ids, bary).astype(np.float32)
        if weight_bones is not None:
            keep = np.isin(model.bone_names, weight_bones)
            W[:, ~keep] = 0
            W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    morphs = {k: v for k, v in model.bound_morphs(ids, bary).items() if not k.startswith('expr_') and np.abs(v).max() > 5e-4}
    return W, morphs


def band_material(b, name, colors, widths, metals, roughs, size=512):
    """Material com faixas ao longo de v (ouro metálico x lápis-lazúli): albedo + ORM."""
    alb, idx = stripe_texture(colors, widths, (8, size), bevel=.05)
    orm = np.zeros((size, 8, 3), np.uint8)
    orm[..., 0] = 255
    orm[..., 1] = (np.array(roughs)[idx % len(roughs)] * 255).astype(np.uint8)[:, None]
    orm[..., 2] = (np.array(metals)[idx % len(metals)] * 255).astype(np.uint8)[:, None]
    tex = b.glb.texture(Image.fromarray(orm, 'RGB'), fmt='png')
    return b.glb.material(name, base=b.glb.texture(alb, fmt='png'), orm=tex, metallic=1.0, roughness=1.0)


def gold_mat(b, name='gold'):
    return flat_material(b, name, GOLD, roughness=.3, metallic=.92)


def gem_mat(b, name='gem', hexstr='#2f6bff', glow=(.03, .08, .3)):
    return b.glb.material(name, color=(*lin(hexstr), 1), roughness=.08, metallic=.1, emissive=glow, clearcoat=(1, .05))


def split_emit(b, name, V, N, uv, F, mat, W, morphs):
    used = np.unique(F)
    remap = np.full(len(V), -1)
    remap[used] = np.arange(len(used))
    emit(b, name, V[used], N[used], uv[used], remap[F], mat, W[used], {k: v[used] for k, v in morphs.items()})


def disk_sdf(c, n, r, h, rim=.0):
    """Disco (moeda) de raio r e meia-espessura h centrado em c, normal n; aro opcional em relevo."""
    n = n / np.linalg.norm(n)

    def fn(p):
        rel = p - c
        a = rel @ n
        rad = np.linalg.norm(rel - a[:, None] * n, axis=1)
        d = np.maximum(rad - r, np.abs(a) - h)
        if rim:
            ring = np.maximum(np.abs(rad - r * .86) - r * .07, np.abs(a - h * .6) - h * 1.1)
            d = np.minimum(d, ring)
        return d
    return fn


# --------------------------------------------------------------------------- máscara de Anúbis

def mask_anubis(model, layout, item_id='mask_anubis'):
    b = ItemBuilder(model, item_id, 'headwear')
    hc = np.array([0, 1.713, .062])
    neck = model.heads['Neck']

    def head_sdf(p):
        d = sd_ellipsoid(p, hc + [0, .02, -.008], np.array([.094, .108, .112]))
        d = smin(d, sd_ellipsoid(p, hc + [0, -.045, .03], np.array([.08, .075, .095])), .03)
        # Focinho: estreito, longo, linha superior caindo até o nariz.
        q = p.copy()
        q[..., 0] = q[..., 0] * 1.45
        d = smin(d, sd_round_cone(q, hc + [0, -.008, .1], hc + [0, -.052, .262], .048, .017), .03)
        d = smin(d, sd_round_cone(q, hc + [0, -.066, .09], hc + [0, -.074, .235], .032, .011), .018)
        # Arcos das sobrancelhas e maçãs.
        for sx in (1, -1):
            d = smin(d, sd_ellipsoid(p, hc + [sx * .04, .02, .112], np.array([.024, .012, .018])), .02)
            d = smin(d, sd_ellipsoid(p, hc + [sx * .05, -.03, .08], np.array([.028, .026, .032])), .025)
        # Pescoço de pelo até a base (o colar cobre a emenda).
        d = smin(d, sd_round_cone(p, hc + [0, -.08, .012], np.array([0, neck[1] - .04, neck[2] + .008]), .058, .064), .04)
        # Boca: vinco leve.
        d = smax(d, -sd_capsule(p, hc + [0, -.062, .12], hc + [0, -.066, .258], .0026), .004)
        return d

    def ear_sdf(p):
        out = np.full(p.shape[:-1], 9.0)
        for sx in (1, -1):
            a = hc + [sx * .05, .1, -.01]
            tip = hc + [sx * .088, .3, -.035]
            q = p.copy()
            # Achata a orelha no eixo frente-trás (folha).
            q[..., 2] = (q[..., 2] - a[2]) * 2.4 + a[2]
            e = sd_round_cone(q, a, tip, .042, .006)
            hollow = sd_round_cone(q + np.array([0, 0, -.022 * 2.4]), a + [0, .025, 0], tip + [0, -.01, 0], .026, .001)
            e = smax(e, -hollow, .006)
            out = np.minimum(out, e)
        return out

    def body_sdf(p):
        return smin(head_sdf(p), ear_sdf(p), .015)

    lo = np.array([-.13, neck[1] - .14, -.1])
    hi = np.array([.14, hc[1] + .32, hc[2] + .34])
    V, N, F = implicit_mesh(body_sdf, lo, hi, .0026)
    # Interior escuro das orelhas: vértices da face côncava da orelha recebem material próprio.
    inner = np.zeros(len(V), bool)
    inner |= (V[:, 1] > hc[1] + .12) & (N[:, 2] > .35)
    face_inner = inner[F].all(1)
    fur = b.glb.material('fur', color=(*lin('#16120f'), 1), roughness=.55, normal=b.glb.texture(noise_normal(256, 18, 1.2, 5), fmt='png'),
                         normal_scale=.3, sheen=((.09, .08, .1), .45))
    ear_in = b.glb.material('ear_inner', color=(*lin('#3a2b30'), 1), roughness=.8)
    uv = np.stack([V[:, 0] * 6 + .5, V[:, 1] * 6], 1)
    hid = head_ids(model)
    head_center = model.coords[hid].mean(0)
    w_head = smoothstep(neck[1] - .01, neck[1] + .06, V[:, 1])
    W = bone_weights(model, len(V), [('Head', 1)])
    W[:, model.bone_index('Head')] = w_head
    W[:, model.bone_index('Neck')] = 1 - w_head
    morphs = blend_morphs(model, V, w_head, hid, head_center)
    for name, mat, sel in (('head', fur, ~face_inner), ('ears_inner', ear_in, face_inner)):
        used = np.unique(F[sel])
        remap = np.full(len(V), -1)
        remap[used] = np.arange(len(used))
        emit(b, name, V[used], N[used], uv[used], remap[F[sel]], mat, W[used], {k: v[used] for k, v in morphs.items()})

    # Nemes: capuz listrado que cobre topo e nuca e cai em abas na frente dos ombros.
    # Perfis do tronco (frente a x=±.11 e costas no meio) para as abas assentarem no corpo.
    c13 = model.coords[:13380]
    ys = np.arange(1.30, 1.72, .02)
    front = np.array([c13[(np.abs(c13[:, 1] - y) < .012) & (np.abs(np.abs(c13[:, 0]) - .11) < .02), 2].max(initial=-1) for y in ys])
    backz = np.array([c13[(np.abs(c13[:, 1] - y) < .012) & (np.abs(c13[:, 0]) < .03), 2].min(initial=1) for y in ys])

    def nemes_sdf(p):
        cap = sd_ellipsoid(p, hc + [0, .02, -.012], np.array([.104, .112, .122])) - .002
        cap = smax(cap, -sd_ellipsoid(p, hc + [0, .02, -.012], np.array([.092, .1, .11])), .004)
        # Abre na frente (rosto do chacal) e corta abaixo da nuca.
        front_cut = (p[..., 2] - (hc[2] + .055)) - (p[..., 1] - (hc[1] + .07)) * .35
        cap = smax(cap, front_cut, .01)
        d = cap
        y = p[..., 1]
        t = np.clip((hc[1] - .04 - y) / .27, 0, 1)
        fz = np.interp(y, ys, front)
        for sx in (1, -1):
            # Aba: placa que nasce atrás da mandíbula e desce assentada sobre o peito, alargando.
            cx = sx * (.1 + .028 * t)
            cz = np.maximum(hc[2] - .01 + .02 * t, fz + .03)
            q = p - np.stack([cx, np.full_like(cx, hc[1] - .15), cz], -1)
            half = np.stack([.026 + .014 * t, np.full_like(t, .15), np.full_like(t, .011)], -1)
            k = np.abs(q) - half + .007
            lap = np.linalg.norm(np.maximum(k, 0), axis=-1) + np.minimum(k.max(-1), 0) - .007
            # Junta da aba com a lateral do capuz.
            side = sd_box(p, hc + [sx * .095, -.025, .0], np.array([.014, .06, .05]), .01)
            d = smin(d, smin(lap, side, .02), .025)
        # Parte de trás: desce pela nuca e assenta nas costas.
        bz = np.minimum(np.interp(y, ys, backz) - .022, hc[2] - .085)
        q = p - np.stack([np.zeros_like(y), np.full_like(y, hc[1] - .16), bz], -1)
        k = np.abs(q) - np.array([.075, .15, .011]) + .008
        back = np.linalg.norm(np.maximum(k, 0), axis=-1) + np.minimum(k.max(-1), 0) - .008
        d = smin(d, back, .03)
        # Não deixa a aba cortar o focinho/rosto.
        d = smax(d, -(sd_ellipsoid(p, hc + [0, -.03, .1], np.array([.07, .1, .09]))), .01)
        return d

    lo2 = np.array([-.19, hc[1] - .34, -.13])
    hi2 = np.array([.19, hc[1] + .16, hc[2] + .17])
    V2, N2, F2 = implicit_mesh(nemes_sdf, lo2, hi2, .003)
    # Remove pedaços que atravessam a cabeça de pelo (orelhas passam por cima do pano).
    keep = body_sdf(V2[F2].mean(1)) > -.002
    F2 = F2[keep]
    stripe_img, _ = stripe_texture([GOLD, LAPIS], [1, 1], (32, 512))
    stripes = b.glb.material('nemes', base=b.glb.texture(stripe_img, fmt='png'), roughness=.45, metallic=0,
                             normal=b.glb.texture(noise_normal(256, 60, 1.0, 9), fmt='png'), normal_scale=.3)
    uv2 = np.stack([V2[:, 0] * 2 + .5, (hc[1] + .2 - V2[:, 1]) * 9.5], 1)
    used = np.unique(F2)
    remap = np.full(len(V2), -1)
    remap[used] = np.arange(len(used))
    V2u = V2[used]
    w2 = smoothstep(neck[1] - .03, neck[1] + .05, V2u[:, 1])
    W2 = bone_weights(model, len(V2u), [])
    W2[:, model.bone_index('Head')] = w2
    W2[:, model.bone_index('Neck')] = (1 - w2) * .55
    W2[:, model.bone_index('Spine2')] = (1 - w2) * .45
    m2 = blend_morphs(model, V2u, w2, hid, head_center)
    emit(b, 'nemes', V2u, N2[used], uv2[used], remap[F2], stripes, W2, m2)

    # Diadema dourado com gema e olhos dourados brilhantes; nariz preto.
    gold = flat_material(b, 'gold', GOLD, roughness=.28, metallic=.95)
    def band_sdf(p):
        ring = sd_ellipsoid(p, hc + [0, .045, -.004], np.array([.1, .05, .106])) - .001
        ring = smax(ring, -sd_ellipsoid(p, hc + [0, .045, -.004], np.array([.094, .044, .1])), .003)
        ring = smax(ring, np.abs(p[..., 1] - (hc[1] + .052 + .02 * (p[..., 2] - hc[2]) / .12)) - .009, .003)
        ring = smax(ring, -(p[..., 2] - (hc[2] - .02)), .004)
        cobra = sd_ellipsoid(p, hc + [0, .082, .1], np.array([.012, .022, .01]))
        return smin(ring, cobra, .008)
    V3, N3, F3 = implicit_mesh(band_sdf, hc + [-.12, -.02, -.05], hc + [.12, .13, .14], .003)
    W3 = bone_weights(model, len(V3), [('Head', 1)])
    emit(b, 'diadem', V3, N3, np.zeros((len(V3), 2)), F3, gold, W3, blend_morphs(model, V3, np.ones(len(V3)), hid, head_center))
    gem = b.glb.material('gem', color=(*lin('#2f6bff'), 1), roughness=.08, metallic=.1, emissive=(.03, .08, .3), clearcoat=(1, .05))
    eye = b.glb.material('eyes', color=(*lin('#ffcf4a'), 1), roughness=.2, emissive=(.9, .55, .08), clearcoat=(1, .05))
    nose = b.glb.material('nose', color=(.01, .01, .012, 1), roughness=.25, clearcoat=(1, .1))
    pieces = [('gem', gem, hc + [0, .068, .107], lambda p: sd_ellipsoid(p, hc + [0, .068, .107], np.array([.008, .011, .006]))),
              ('nose', nose, hc + [0, -.049, .268], lambda p: sd_ellipsoid(p, hc + [0, -.049, .268], np.array([.0135, .01, .012])))]
    for sx in (1, -1):
        c = hc + [sx * .046, .002, .118]
        pieces.append((f'eye_{"l" if sx > 0 else "r"}', eye, c, lambda p, c=c, sx=sx: sd_ellipsoid(
            np.stack([(p[..., 0] - c[0]) * np.cos(.5) - sx * (p[..., 1] - c[1]) * np.sin(.5) + c[0],
                      sx * (p[..., 0] - c[0]) * np.sin(.5) + (p[..., 1] - c[1]) * np.cos(.5) + c[1], p[..., 2]], -1),
            c, np.array([.016, .007, .009]))))
    for name, mat, c, fn in pieces:
        V4, N4, F4 = implicit_mesh(fn, c - .022, c + .022, .0018)
        emit(b, name, V4, N4, np.zeros((len(V4), 2)), F4, mat, bone_weights(model, len(V4), [('Head', 1)]),
             blend_morphs(model, V4, np.ones(len(V4)), hid, head_center))
    return b.save({'hides': ['head']})


# --------------------------------------------------------------------------- colar usekh

TORSO = ['Neck', 'Spine2', 'Spine1', 'Spine', 'LeftShoulder', 'RightShoulder']


def neck_usekh(model, layout, item_id='neck_usekh'):
    """Colar largo em faixas de ouro e lápis-lazúli, borda de contas e disco solar no peito."""
    b = ItemBuilder(model, item_id, 'neck')
    field = BodyField(model, TORSO)
    A, B = np.array([0, 1.47, .0]), np.array([0, 1.66, .03])
    r_in = .066

    def polar(p):
        ab = B - A
        t = np.clip(((p - A) @ ab) / (ab @ ab), 0, 1)
        rel = p - (A + t[:, None] * ab)
        return np.linalg.norm(rel, axis=1), np.arctan2(rel[:, 0], rel[:, 2])

    def r_out(th):
        base = .17 + .012 * np.cos(th) + .045 * np.sin(th) ** 2 - .012 * np.clip(-np.cos(th), 0, 1)
        return base + .007 * (.5 + .5 * np.cos(th * 16))

    def u_of(p):
        dn, th = polar(p)
        return np.clip((dn - r_in) / (r_out(th) - r_in), 0, 1), dn, th

    # Faixas: ouro, lápis, ouro, lápis, ouro, lápis, contas de ouro.
    widths = [1.1, 1.5, .7, 1.6, .7, 1.4, 1.6]
    cum = np.cumsum(widths) / np.sum(widths)

    def g1(p):
        u, _, _ = u_of(p)
        edge = np.min(np.abs(u[:, None] - cum[None, :-1]), axis=1)
        rib = np.exp(-(edge / .025) ** 2)
        beads = smoothstep(cum[-2], cum[-2] + .05, u) * .004
        return .0095 + .0032 * rib + beads - .003 * u ** 2

    def region(p):
        dn, th = polar(p)
        return np.maximum(r_in - dn, dn - r_out(th))

    fn = shell(field, region, .0035, g1)
    V, N, F = implicit_mesh(fn, [-.28, 1.3, -.17], [.28, 1.64, .22], .003, err=.0003)
    u, _, th = u_of(V)
    uv = np.stack([np.full(len(V), .5), u], 1)
    mat = band_material(b, 'usekh', [GOLD, LAPIS, GOLD, LAPIS, GOLD, LAPIS, GOLD], widths,
                        [.95, .05, .95, .05, .95, .05, .95], [.28, .3, .28, .3, .28, .3, .3])
    W, morphs = skin_bind(model, V, TORSO, weight_bones=TORSO)
    emit(b, 'collar', V, N, uv, F, mat, W, morphs)
    # Disco solar com gema no centro, assentado sobre o colar.
    c, n = field.project(np.array([0, 1.43, .3]), [0, 0, -1], .3, .016)
    gold = gold_mat(b)
    V2, N2, F2 = implicit_mesh(disk_sdf(c, n, .03, .004, rim=True), c - .04, c + .04, .0012, err=.0002)
    W2, m2 = skin_bind(model, V2, TORSO, rigid_bone='Spine2')
    m2 = {k: np.broadcast_to(v.mean(0), v.shape) for k, v in m2.items()}
    emit(b, 'sun_disk', V2, N2, np.zeros((len(V2), 2)), F2, gold, W2, m2)
    gc = c + n * .006
    V3, N3, F3 = implicit_mesh(lambda p: sd_ellipsoid(p, gc, np.array([.012, .012, .007])), gc - .02, gc + .02, .0012, err=.0002)
    W3, m3 = skin_bind(model, V3, TORSO, rigid_bone='Spine2')
    m3 = {k: np.broadcast_to(v.mean(0), v.shape) for k, v in m3.items()}
    emit(b, 'gem', V3, N3, np.zeros((len(V3), 2)), F3, gem_mat(b), W3, m3)
    return b.save({})


# --------------------------------------------------------------------------- faixas cruzadas e braçadeiras

def polyline_dist(p, pts):
    """Distância de p (N,3) à polilinha pts (K,3)."""
    best = np.full(len(p), np.inf)
    for a, c in zip(pts[:-1], pts[1:]):
        ab = c - a
        t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        best = np.minimum(best, np.linalg.norm(p - (a + t[:, None] * ab), axis=1))
    return best


def surface_path(field, xy, side, gap=0.0):
    """Projeta pontos (x, y) na frente (side=+1) ou nas costas (side=-1) do corpo."""
    return np.array([field.project(np.array([x, y, side * .32]), [0, 0, -side], .4, gap)[0] for x, y in xy])


def limb_band(model, side, limb, t0, t1):
    """Eixo do osso, ponto central e meia-largura de uma faixa entre t0 e t1 do osso."""
    a, c = model.heads[f'{side}{limb}'], model.tails[f'{side}{limb}']
    axis = (c - a) / np.linalg.norm(c - a)
    L = np.linalg.norm(c - a)
    return axis, a + axis * L * (t0 + t1) / 2, L * (t1 - t0) / 2


def top_anubis_harness(model, layout, item_id='top_anubis_harness'):
    """Faixas douradas cruzadas no peito e nas costas, medalhão central e braçadeiras."""
    b = ItemBuilder(model, item_id, 'top')
    bones = TORSO + ['Hips']
    field = BodyField(model, bones)
    w = .036
    straps = []
    for sx in (1, -1):
        n = 9
        xs = np.linspace(sx * .125, -sx * .135, n)
        ys = np.linspace(1.47, 1.0, n)
        front = surface_path(field, list(zip(xs, ys)), 1)
        back = surface_path(field, list(zip(xs, ys)), -1)
        top = field.project(np.array([sx * .135, 1.75, -.01]), [0, -1, 0], .4, 0)[0]
        straps.append(np.vstack([front[::-1], top[None], back]))

    def dist(p):
        return np.minimum(polyline_dist(p, straps[0]), polyline_dist(p, straps[1]))

    def region(p):
        return dist(p) - w / 2

    def g1(p):
        e = dist(p) / (w / 2)
        return .0058 + .0016 * smoothstep(.62, .8, e) * (1 - smoothstep(.9, 1.0, e))

    fn = shell(field, region, .0018, g1)
    V, N, F = implicit_mesh(fn, [-.26, .95, -.2], [.26, 1.62, .22], .003, err=.0003)
    uv = np.stack([np.full(len(V), .5), np.clip(dist(V) / (w / 2), 0, 1)], 1)
    mat = band_material(b, 'strap', [LAPIS, GOLD, GOLD_DARK], [.5, .38, .12], [.05, .95, .9], [.32, .28, .35])
    W, morphs = skin_bind(model, V, bones, weight_bones=bones)
    emit(b, 'straps', V, N, uv, F, mat, W, morphs)
    # Medalhão no cruzamento do peito: disco de ouro, aro, miolo de lápis e gema.
    c, n = field.project(np.array([0, 1.245, .3]), [0, 0, -1], .4, .007)
    gold = gold_mat(b)
    lap = flat_material(b, 'lapis', LAPIS, roughness=.3, clearcoat=(.8, .1))
    for name, mat_, fn_ in (('medal', gold, disk_sdf(c, n, .036, .0045, rim=True)),
                             ('medal_inlay', lap, disk_sdf(c + n * .0035, n, .022, .0015)),
                             ('medal_gem', gem_mat(b), lambda p, c=c + n * .006: sd_ellipsoid(p, c, np.array([.011, .014, .008])))):
        V2, N2, F2 = implicit_mesh(fn_, c - .045, c + .045, .0012, err=.0002)
        W2, m2 = skin_bind(model, V2, bones, rigid_bone='Spine1')
        m2 = {k: np.broadcast_to(v.mean(0), v.shape) for k, v in m2.items()}
        emit(b, name, V2, N2, np.zeros((len(V2), 2)), F2, mat_, W2, m2)
    # Braçadeiras no meio do braço.
    arm_mat = band_material(b, 'armband', [GOLD, LAPIS, GOLD, LAPIS, GOLD], [.22, .16, .24, .16, .22],
                            [.95, .05, .95, .05, .95], [.28, .3, .28, .3, .28])
    for side in ('Left', 'Right'):
        axis, mid, half = limb_band(model, side, 'Arm', .36, .52)
        af = BodyField(model, [f'{side}Arm'])

        def reg(p, axis=axis, mid=mid, half=half):
            return np.abs((p - mid) @ axis) - half

        def g1a(p, axis=axis, mid=mid, half=half):
            v = np.abs((p - mid) @ axis) / half
            return .0065 + .002 * np.exp(-((v - .55) / .12) ** 2) + .0015 * (v > .85)

        lo, hi = mid - .1, mid + .1
        V3, N3, F3 = implicit_mesh(shell(af, reg, .002, g1a), lo, hi, .0025, err=.00025)
        uv3 = np.stack([np.full(len(V3), .5), np.clip(((V3 - mid) @ axis) / half * .5 + .5, 0, 1)], 1)
        W3, m3 = skin_bind(model, V3, [f'{side}Arm'], rigid_bone=f'{side}Arm')
        emit(b, f'armband_{side[0].lower()}', V3, N3, uv3, F3, arm_mat, W3, m3)
    return b.save({})


def bracers_gold(model, layout, item_id='bracers_gold'):
    """Braceletes largos de ouro com faixas de lápis-lazúli e gema oval no dorso do antebraço."""
    b = ItemBuilder(model, item_id, 'wrist')
    mat = band_material(b, 'bracer', [GOLD, LAPIS, GOLD, LAPIS, GOLD], [.16, .22, .24, .22, .16],
                        [.95, .05, .95, .05, .95], [.26, .3, .26, .3, .26])
    for side in ('Left', 'Right'):
        bone = f'{side}ForeArm'
        axis, mid, half = limb_band(model, side, 'ForeArm', .5, .97)
        af = BodyField(model, [bone, f'{side}Hand'])

        def reg(p, axis=axis, mid=mid, half=half):
            return np.abs((p - mid) @ axis) - half

        def g1(p, axis=axis, mid=mid, half=half):
            v = np.abs((p - mid) @ axis) / half
            # Bordas em relevo e frisos entre as faixas.
            return .0072 + .0022 * smoothstep(.82, .9, v) + .0015 * np.exp(-((v - .35) / .07) ** 2) - .0012 * v ** 2

        lo, hi = mid - .16, mid + .16
        V, N, F = implicit_mesh(shell(af, reg, .0022, g1), lo, hi, .0025, err=.00025)
        uv = np.stack([np.full(len(V), .5), np.clip(((V - mid) @ axis) / half * .5 + .5, 0, 1)], 1)
        W, morphs = skin_bind(model, V, [bone], rigid_bone=bone)
        emit(b, f'bracer_{side[0].lower()}', V, N, uv, F, mat, W, morphs)
        # Gema no dorso (lado de fora do antebraço na pose de descanso).
        out = np.array([np.sign(mid[0]), .35, .0])
        out -= axis * (out @ axis)
        out /= np.linalg.norm(out)
        c, n = af.project(mid + out * .2, -out, .3, .009)
        gold = gold_mat(b)
        for name, mat_, fn_ in ((f'setting_{side[0].lower()}', gold, disk_sdf(c, n, .015, .003, rim=True)),
                                 (f'gem_{side[0].lower()}', gem_mat(b), lambda p, c=c + n * .004: sd_ellipsoid(p, c, np.array([.009, .009, .006])))):
            V2, N2, F2 = implicit_mesh(fn_, c - .025, c + .025, .001, err=.00015)
            W2, m2 = skin_bind(model, V2, [bone], rigid_bone=bone)
            m2 = {k: np.broadcast_to(v.mean(0), v.shape) for k, v in m2.items()}
            emit(b, name, V2, N2, np.zeros((len(V2), 2)), F2, mat_, W2, m2)
    return b.save({})


def register(item):
    item('mask_anubis', 'headwear')(mask_anubis)
    item('neck_usekh', 'neck')(neck_usekh)
    item('top_anubis_harness', 'top')(top_anubis_harness)
    item('bracers_gold', 'wrist')(bracers_gold)
