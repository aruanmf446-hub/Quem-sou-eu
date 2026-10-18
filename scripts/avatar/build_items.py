"""Gera as peças do guarda-roupa em public/avatar/items/.

python3 scripts/avatar/build_items.py [id ...]
"""
from __future__ import annotations

import sys
import time

from bodyuv import BodyLayout
from items import ItemBuilder
from model import AvatarModel
import overlays
import hair
import wardrobe
import numpy as np

REGISTRY = {}


def item(item_id, slot):
    def deco(fn):
        REGISTRY[item_id] = (slot, fn)
        return fn
    return deco


def overlay_item(model, layout, item_id, slot, values, offset, color_key, extras=None, name='layer'):
    b = ItemBuilder(model, item_id, slot)
    tex = b.glb.texture(overlays.alpha_image(model, layout, values), fmt='webp', quality=90)
    mat = b.glb.material(f'{item_id}_mat', color=(1, 1, 1, 1), base=tex, roughness=.78,
                         alpha=('BLEND', 0), extras={color_key: True, 'overlay': True} if color_key != 'brows' else {'hairColor': 'brows', 'overlay': True})
    faces = overlays.faces_in(layout, model, values)
    b.skin_layer(name, faces, offset, mat)
    return b


def sculpt_brows(b, model, style):
    """Sobrancelhas com fios 3D finos em curva, nunca placas sólidas.

    A máscara de textura preenche visualmente a sobrancelha, e cinco/sete
    mechas esculpidas captam recortes de luz sobre a pele. Geometria presa ao
    mesmo osso e morphs que os outros acessórios.
    """
    from scipy.spatial import cKDTree
    L = overlays.Landmarks(model)
    skin = model.coords[model.mesh.group_vertices('body')]
    front = skin[(skin[:, 1] > L.eye_y - .035) &
                 (skin[:, 1] < L.eye_y + .09) &
                 (skin[:, 2] > L.eyeL[2] - .035) &
                 (np.abs(skin[:, 0]) < L.eye_x * 2.2)]
    if len(front) < 20:
        raise ValueError('Superfície facial não localizada para sobrancelhas')
    tree = cKDTree(front[:, :2])
    params = {
        'natural': (5, .008, .0055),
        'thick': (7, .007, .0065),
        'thin': (3, .009, .0033),
        'arched': (5, .014, .0050),
    }
    nstrands, arch, spread = params[style]
    material = b.glb.material(f'brow_sculpt_{style}', color=(.15, .11, .085, 1),
                              roughness=.84, extras={'hairColor': 'brows'})
    for side in (-1., 1.):
        paths, radii = [], []
        for j in range(nstrands):
            offset = (j / max(nstrands - 1, 1) * 2 - 1) * spread
            path, rr = [], []
            for i in range(27):
                t = i / 26
                taper = max(0.0, np.sin(np.pi * t)) ** .75
                x = side * (.012 + .050 * t)
                y = L.eye_y + .018 + arch * np.sin(np.pi * t) + .003 * (1 - t) + offset * taper
                _, ix = tree.query([x, y], k=5)
                nearby = front[np.atleast_1d(ix)]
                dist = np.linalg.norm(nearby[:, :2] - [x, y], axis=1)
                ww = 1 / np.maximum(dist, .001) ** 2
                z = float(np.average(nearby[:, 2], weights=ww)) + .0015
                path.append((x, y, z))
                rr.append((.00055 + .00065 * taper) * max(.08, taper))
            paths.append(np.asarray(path))
            radii.append(np.asarray(rr))
        pos, nrm, uv, tris, _ = hair.tube_mesh(paths, radii, sides=6)
        b.bound(f'brow_strands_{"r" if side > 0 else "l"}', pos, tris, uv,
                material, nrm=nrm, bone='Head')


for style in ('natural', 'thick', 'thin', 'arched'):
    def _brow(model, layout, style=style):
        b = overlay_item(model, layout, f'brows_{style}', 'brows', overlays.brows_alpha(model, layout, style), .00035, 'brows')
        sculpt_brows(b, model, style)
        return b.save({})
    item(f'brows_{style}', 'brows')(_brow)

for style in ('stubble', 'goatee', 'chinstrap', 'full'):
    def _beard(model, layout, style=style):
        b = overlay_item(model, layout, f'beard_{style}', 'beard', overlays.beard_alpha(model, layout, style), .0004, 'hair')
        return b.save({})
    item(f'beard_{style}', 'beard')(_beard)


@item('hair_buzz', 'hair')
def hair_buzz(model, layout):
    b = overlay_item(model, layout, 'hair_buzz', 'hair', overlays.scalp_alpha(model, layout, 'buzz'), .0006, 'hair')
    return b.save({})


def hair_material(b, name, roughness=.48):
    alb, nrm = hair.strand_texture()
    return b.glb.material(name, base=b.glb.texture(alb, fmt='jpeg', quality=90), normal=b.glb.texture(nrm, fmt='png'),
                          roughness=roughness, extras={'hair': True, 'tips': True})


def add_coils(b, model, mat, roots, normals, rng, sides=6, **kw):
    paths, radii = hair.coils(roots, normals, rng, **kw)
    pos, nrm, uv, tris, along = hair.tube_mesh(paths, radii, sides=sides)
    per = np.repeat(rng.uniform(.55, 1, len(paths)), [len(p) * sides for p in paths])
    tip = np.clip(along ** 1.3 * per, 0, 1).astype(np.float32)
    b.bound('coils', pos, tris, uv, mat, nrm=nrm, bone='Head', extra_attrs={'_TIP': tip})


def curl_shell(b, model, layout, region_fn, thickness, name='volume', seed=3, freq=420, tips=True, offset_override=None):
    """Casca volumétrica com relevo de cachos (dá densidade sem milhares de tubos)."""
    from raster import Bake, fbm, smoothstep, to_image, normal_to_image
    bake = overlays.head_bake(model, layout)
    p = bake.pos[bake.mask].astype(np.float64)
    region = region_fn(p)
    h, cell = hair.curl_height(p, freq, seed)
    lump = fbm(p, 55, 2, seed + 4)
    albedo = np.clip(.42 + .5 * h + .15 * (lump - .5), 0, 1)
    alpha = np.clip(region * 2.5 - .3 + (h - .5) * .4, 0, 1)
    img = np.zeros((overlays.SIZE, overlays.SIZE, 4), np.float32)
    img[bake.mask, 0] = albedo
    img[bake.mask, 1] = albedo
    from raster import _hash
    q = np.floor(p * freq).astype(np.int64)
    blond = (_hash(q[:, 0], q[:, 1], q[:, 2], seed + 40) > .55) * smoothstep(.35, .85, h) * smoothstep(.3, .9, region)
    img[bake.mask, 2] = blond if tips else 0
    img[bake.mask, 3] = alpha
    from raster import dilate
    img = dilate(img, bake.mask)
    from PIL import Image
    tex = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGBA')
    nmap = bake.normal_map(lambda q: hair.curl_height(q, freq, seed)[0] * .0016 + fbm(q, 900, 2, seed + 9) * .0004)
    mat = b.glb.material(name, base=b.glb.texture(tex, fmt='webp', quality=88), normal=b.glb.texture(normal_to_image(nmap, bake.mask), fmt='webp', quality=90),
                         normal_scale=1.0, roughness=.6, alpha=('MASK', .5), extras={'hair': True, 'tips': tips})
    faces = overlays.faces_in(layout, model, region)

    def offset_fn(pos, n):
        r = region_fn(pos)
        if offset_override is not None:
            return offset_override(pos, n) * smoothstep(0, .9, r) * (.9 + .2 * fbm(pos, 45, 2, seed + 5)) + .001
        return thickness * smoothstep(0, .9, r) * (.75 + .5 * fbm(pos, 45, 2, seed + 5)) + .001

    def attrs(base_pos, pos):
        lumps = fbm(base_pos, 70, 2, seed + 6)
        return {'_TIP': (np.clip((lumps - .5) * 1.6, 0, 1) * smoothstep(.2, .9, region_fn(base_pos))).astype(np.float32)}
    b.skin_layer(name, faces, 0, mat, offset_fn=offset_fn, attrs_fn=attrs)
    return offset_fn


@item('hair_curly_fade', 'hair')
def hair_curly_fade(model, layout):
    from raster import smoothstep
    b = overlay_item(model, layout, 'hair_curly_fade', 'hair', overlays.scalp_alpha(model, layout, 'fade'), .0006, 'hair', name='scalp')
    L = overlays.Landmarks(model)

    def region(P):
        rel = P - L.center
        aaz = np.abs(np.degrees(np.arctan2(rel[:, 0], rel[:, 2])))
        floor = np.maximum(hair.scalp_line(L, aaz) + .006, L.eye_y + .05 + .012 * smoothstep(60, 130, aaz))
        return smoothstep(floor, floor + .016, P[:, 1]) * (1 - smoothstep(145, 160, aaz))
    # Massa escultural (casca) + cachos grandes. Os fios antigos eram tão
    # finos que pareciam arames. Cada coil agora lê como uma mecha de cartoon.
    offset = curl_shell(b, model, layout, region, .024, freq=330)
    rng = np.random.default_rng(10)
    roots, normals, _ = hair.scalp_samples(model, .0113, lambda P, N, h, aaz: region(P) > .5)
    lift = np.array([offset(roots[i:i + 1], normals[i:i + 1])[0] for i in range(len(roots))])
    roots = roots + normals * (lift[:, None] - .004)
    add_coils(b, model, hair_material(b, 'curls', .52), roots, normals, rng,
              length=(.020, .034), radius=(.0038, .0058),
              turns=(1.2, 2.0), thickness=(.0028, .0040),
              lean=np.array([0, .2, .34]), seg_per_turn=11, sides=7)
    return b.save({'tips': True})


@item('hair_afro', 'hair')
def hair_afro(model, layout):
    from raster import smoothstep
    b = overlay_item(model, layout, 'hair_afro', 'hair', overlays.scalp_alpha(model, layout, 'full'), .0006, 'hair', name='scalp')
    L = overlays.Landmarks(model)
    center = L.center + np.array([0, .045, -.03])
    R = .135

    def region(P):
        rel = P - L.center
        aaz = np.abs(np.degrees(np.arctan2(rel[:, 0], rel[:, 2])))
        line = hair.scalp_line(L, aaz)
        return smoothstep(line + .001, line + .012, P[:, 1])

    def to_sphere(pos, n):
        # Distância ao longo da normal até a esfera do volume (forma arredondada do black power).
        d = pos - center
        bq = (d * n).sum(1)
        cq = (d * d).sum(1) - R * R
        disc = np.maximum(bq * bq - cq, 0)
        rel = pos - L.center
        aaz = np.abs(np.degrees(np.arctan2(rel[:, 0], rel[:, 2])))
        ramp = smoothstep(0, .05, pos[:, 1] - hair.scalp_line(L, aaz))
        return np.clip(-bq + np.sqrt(disc), .004, .08) * (.15 + .85 * ramp)
    curl_shell(b, model, layout, region, .05, name='volume', seed=5, freq=300, offset_override=to_sphere)
    rng = np.random.default_rng(12)
    roots, normals, _ = hair.scalp_samples(model, .013, lambda P, N, h, aaz: region(P) > .6, seed=9)
    lift = to_sphere(roots, normals) * .9
    roots = roots + normals * lift[:, None]
    add_coils(b, model, hair_material(b, 'afro', .62), roots, normals, rng, length=(.012, .02), radius=(.004, .006),
              turns=(1.5, 2.2), thickness=(.0025, .0035), lean=np.array([0, .1, 0]), seg_per_turn=7, sides=5)
    return b.save({'tips': True})


@item('top_jersey_10', 'top')
def _jersey(model, layout):
    return wardrobe.jersey_camisa10(model, layout)


@item('bottom_shorts_10', 'bottom')
def _shorts(model, layout):
    return wardrobe.shorts_camisa10(model, layout)


@item('socks_football_10', 'socks')
def _socks(model, layout):
    return wardrobe.socks_football(model, layout)


@item('shoes_cleats_10', 'shoes')
def _cleats(model, layout):
    return wardrobe.cleats_camisa10(model, layout)


import wardrobe2 as W2
import accessories as ACC

for _id, _slot, _fn in (
    ('top_tee', 'top', W2.tee), ('top_tank', 'top', W2.tank), ('top_jersey_away', 'top', W2.jersey_away),
    ('top_track_jacket', 'top', W2.track_jacket), ('top_clown_tunic', 'top', W2.clown_tunic),
    ('socks_crew', 'socks', W2.socks_crew), ('socks_football', 'socks', W2.socks_football_plain),
    ('shoes_sneakers', 'shoes', W2.sneakers), ('shoes_hightops', 'shoes', W2.hightops), ('shoes_clown', 'shoes', W2.clown_shoes),
    ('bottom_shorts', 'bottom', W2.plain_shorts),
    ('cap_snapback', 'headwear', ACC.cap), ('headband', 'headwear', ACC.headband), ('glasses_sport', 'eyewear', ACC.glasses_sport),
    ('glasses_round', 'eyewear', ACC.glasses_round), ('chain_gold', 'neck', ACC.chain), ('wristband', 'wrist', ACC.wristband),
    ('watch', 'wrist', ACC.watch), ('tattoo_sleeve', 'bodyart', ACC.tattoo_sleeve), ('facepaint_midnight', 'bodyart', ACC.facepaint), ('bottom_joggers', 'bottom', W2.joggers), ('bottom_clown_pants', 'bottom', W2.clown_pants),
):
    item(_id, _slot)(lambda model, layout, _fn=_fn: _fn(model, layout))


def sleek_shell(b, model, layout, region_fn, thickness, name='sleek', seed=7):
    """Casca lisa de fios penteados para trás (base de coques e rabos)."""
    from raster import fbm, smoothstep, normal_to_image, dilate
    from PIL import Image
    bake = overlays.head_bake(model, layout)
    p = bake.pos[bake.mask].astype(np.float64)
    L = overlays.Landmarks(model)
    region = region_fn(p)
    rel = p - L.center
    ang = np.arctan2(rel[:, 0], rel[:, 2])

    def strands_h(q):
        r = q - L.center
        a = np.arctan2(r[:, 0], r[:, 2])
        # Fios correm da testa para a nuca: variam no ângulo lateral, pouco ao longo do comprimento.
        lat = a * .1 + (fbm(q, 20, 2, seed) - .5) * .01
        return (np.sin(lat * 2 * np.pi * 900) * .5 + .5) * .00012 + (fbm(q, 150, 2, seed + 1) - .5) * .0002
    lum = np.clip(.62 + .3 * (np.sin((ang * .1) * 2 * np.pi * 300 + fbm(p, 30, 2, seed) * 6) * .5 + .5) * .5 + .15 * (fbm(p, 60, 2, seed + 2) - .5), 0, 1)
    alpha = np.clip(region * 1.4 - .2, 0, 1)
    img = np.zeros((overlays.SIZE, overlays.SIZE, 4), np.float32)
    img[bake.mask, 0] = lum
    img[bake.mask, 1] = lum
    img[bake.mask, 3] = alpha
    img = dilate(img, bake.mask)
    tex = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGBA')
    nmap = bake.normal_map(strands_h)
    mat = b.glb.material(name, base=b.glb.texture(tex, fmt='webp', quality=88), normal=b.glb.texture(normal_to_image(nmap, bake.mask), fmt='webp', quality=88),
                         roughness=.45, alpha=('MASK', .5), extras={'hair': True, 'tips': True})
    faces = overlays.faces_in(layout, model, region)

    def offset_fn(pos, n):
        return thickness * smoothstep(0, .8, region_fn(pos)) + .0008
    b.skin_layer(name, faces, 0, mat, offset_fn=offset_fn, attrs_fn=lambda bp, pos: {'_TIP': np.zeros(len(pos), np.float32)})


def bun_mesh(center, axis, radius=.036, turns=5.5, rope=.0105, seg=180):
    axis = axis / np.linalg.norm(axis)
    ref = np.array([1., 0, 0])
    u = np.cross(axis, ref); u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    t = np.linspace(0, 1, seg)
    lat = .25 + t * 1.15  # latitude a partir do polo (radianos)
    phi = t * turns * 2 * np.pi
    r = radius * (1 - .1 * t)
    path = center + (np.outer(np.cos(lat) * r, axis) + np.outer(np.sin(lat) * np.cos(phi) * r, u) + np.outer(np.sin(lat) * np.sin(phi) * r, v))
    return path, np.full(seg, rope) * (1 - .35 * np.clip((t - .85) / .15, 0, 1))


@item('hair_bun', 'hair')
def hair_bun(model, layout):
    from raster import smoothstep
    b = overlay_item(model, layout, 'hair_bun', 'hair', overlays.scalp_alpha(model, layout, 'full'), .0006, 'hair', name='scalp')
    L = overlays.Landmarks(model)

    def region(P):
        rel = P - L.center
        aaz = np.abs(np.degrees(np.arctan2(rel[:, 0], rel[:, 2])))
        line = hair.scalp_line(L, aaz)
        return smoothstep(line + .001, line + .01, P[:, 1])
    sleek_shell(b, model, layout, region, .0045)
    center = np.array([0, L.top - .012, L.center[2] - .07])
    path, radii = bun_mesh(center, np.array([0, .55, -.85]))
    pos, nrm, uv, tris, along = hair.tube_mesh([path], [radii], sides=8)
    uv[:, 1] *= .25
    b.bound('bun', pos, tris, uv, hair_material(b, 'bun', .5), nrm=nrm, bone='Head', extra_attrs={'_TIP': np.zeros(len(pos), np.float32)})
    # Elástico do coque.
    ring_c = center + np.array([0, -.022, .02])
    t = np.linspace(0, 2 * np.pi, 40)
    ax = np.array([0, .55, -.85]) / np.linalg.norm([0, .55, -.85])
    u = np.array([1., 0, 0]); w = np.cross(ax, u)
    ring = ring_c + np.outer(np.cos(t) * .022, u) + np.outer(np.sin(t) * .022, w)
    rp, rn, ruv, rt, _ = hair.tube_mesh([ring], [np.full(40, .004)], sides=6)
    band = b.glb.material('elastic', color=(.02, .02, .025, 1), roughness=.35)
    b.bound('elastic', rp, rt, ruv, band, nrm=rn, bone='Head')
    return b.save({})


@item('hair_clown', 'hair')
def hair_clown(model, layout):
    from raster import smoothstep
    L = overlays.Landmarks(model)
    bake = overlays.head_bake(model, layout)
    p = bake.pos[bake.mask].astype(np.float64)
    rel = p - L.center
    aaz = np.abs(np.degrees(np.arctan2(rel[:, 0], rel[:, 2])))
    side = smoothstep(50, 70, aaz) * (1 - smoothstep(.04, .06, p[:, 1] - L.eye_y))
    values = overlays.scalp_alpha(model, layout, 'buzz') * side
    b = overlay_item(model, layout, 'hair_clown', 'hair', values, .0006, 'hair', name='scalp')
    rng = np.random.default_rng(21)
    ey = L.eye_y

    def pred(P, N, h, aaz):
        line = hair.scalp_line(L, aaz)
        return (aaz > 62) & (aaz < 150) & (P[:, 1] > line + .004) & (P[:, 1] < ey + .055)
    roots, normals, _ = hair.scalp_samples(model, .0085, pred, seed=4)
    paths_all = []
    for sgn in (1, -1):
        m = np.sign(roots[:, 0]) == sgn
        center = np.array([sgn * .115, ey + .025, L.center[2] - .01])

        def envelope(path, center=center):
            rel = (path - center) / np.array([.085, .07, .09])
            r = np.linalg.norm(rel, axis=1, keepdims=True)
            return center + (path - center) * np.minimum(1, 1 / np.maximum(r, 1e-6))
        add_coils(b, model, hair_material(b, f'tuft_{sgn}', .55), roots[m], normals[m], rng, length=(.045, .075), radius=(.006, .01),
                  turns=(2.0, 3.0), thickness=(.0035, .005), lean=np.array([sgn * .9, .35, -.25]), envelope=envelope, seg_per_turn=7, sides=5)
    return b.save({'tips': True})


import hair_styles


@item('hair_wild_ponytail', 'hair')
def _wild(model, layout):
    return hair_styles.wild_ponytail(model, layout)


import collection_mechanic
import collection_astro
import collection_harlequin
import collection_anubis
import collection_volt
for _module in (collection_mechanic, collection_astro, collection_harlequin, collection_anubis, collection_volt):
    _module.register(item)


def main(ids):
    t = time.time()
    model = AvatarModel()
    layout = BodyLayout(model)
    print(f'modelo pronto em {time.time() - t:.1f}s')
    for item_id in ids or REGISTRY:
        slot, fn = REGISTRY[item_id]
        fn(model, layout)


if __name__ == '__main__':
    main(sys.argv[1:])
