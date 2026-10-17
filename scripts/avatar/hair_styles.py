"""Penteados estilizados das coleções (mechas esculpidas)."""
from __future__ import annotations

import numpy as np

import hair
import hair_styled as H
import overlays
from items import ItemBuilder


def styled_material(b, name, roughness=.5, tips=False):
    alb, nrm = hair.strand_texture(seed=11)
    return b.glb.material(name, base=b.glb.texture(alb, fmt='jpeg', quality=90), normal=b.glb.texture(nrm, fmt='png'),
                          normal_scale=.6, roughness=roughness, extras={'hair': True, 'tips': tips})


def emit(b, name, mat, paths, widths, vol, tip_scale=1.0, flat=.42, twist=None):
    pos, nrm, uv, tris, along = H.clump_mesh(paths, widths, vol, flat=flat, twist=twist)
    # Raiz mais escura (oclusão) e pontas iluminadas; _TIP controla as pontas descoloridas.
    tip = (np.clip(along, 0, 1) ** 1.4 * tip_scale).astype(np.float32)
    b.bound(name, pos, tris, uv, mat, nrm=nrm, bone='Head', extra_attrs={'_TIP': tip})


def scalp_base(model, layout, item_id, style='full'):
    from build_items import overlay_item
    return overlay_item(model, layout, item_id, 'hair', overlays.scalp_alpha(model, layout, style), .0006, 'hair', name='scalp')


def wild_ponytail(model, layout, item_id='hair_wild_ponytail'):
    """Rabo de cavalo alto e volumoso, franja lateral e mechas soltas (mecânica dos céus)."""
    rng = np.random.default_rng(21)
    vol = H.HeadVolume(model)
    L = vol.L
    b = scalp_base(model, layout, item_id)
    mat = styled_material(b, 'hair', .48, tips=True)
    c, r = vol.center, vol.radii
    G = c + np.array([0, r[1] * .62, -r[2] * .78])
    G = G + vol.surface_dir(G) * .012
    P, N, az = H.roots(model, .013, lambda P, N, aaz: P[:, 1] > hair.scalp_line(L, aaz) + .004)
    paths, widths = [], []
    for p, a in zip(P, az):
        path = H.cap_path(vol, p, G + rng.normal(0, .006, 3), 16, lift=(.005, .012 + rng.uniform(0, .006)))
        paths.append(path)
        widths.append(H.taper(16, rng.uniform(.017, .024), .55, .6))
    emit(b, 'cap', mat, paths, widths, vol, tip_scale=.25)
    # Rabo: mechas que sobem e caem em cachos largos.
    paths, widths = [], []
    for i in range(26):
        ang = 2 * np.pi * i / 26
        off = np.array([np.cos(ang) * .014, np.sin(ang) * .008, 0]) + rng.normal(0, .004, 3)
        # Leque: sobe um pouco, abre para os lados e cai sobre a nuca em ondas largas.
        d = np.array([np.cos(ang) * .55, .55 + .25 * np.sin(ang), -.8])
        path = H.free_path(vol, G + off, d, rng.uniform(.16, .22), 20, gravity=2.2, stiff=.1,
                           wave=(rng.uniform(.01, .018), rng.uniform(.9, 1.4), rng.uniform(0, 6)),
                           curl=(rng.uniform(.008, .014), rng.uniform(1.2, 1.8)), margin=.014, seed=i)
        paths.append(path)
        widths.append(H.taper(20, rng.uniform(.03, .042), .14))
    emit(b, 'ponytail', mat, paths, widths, vol, tip_scale=1)
    # Franja varrida para o lado e mechas que emolduram o rosto.
    paths, widths = [], []
    for i in range(7):
        s = -1 + 2 * i / 6
        root = c + np.array([s * r[0] * .5, r[1] * .55, r[2] * .75])
        root = vol.push_out(root[None], .004)[0]
        d = np.array([.55 + s * .3, -.25, .55])
        path = H.free_path(vol, root, d, rng.uniform(.06, .095), 14, gravity=.7, stiff=.5,
                           wave=(.004, .8, rng.uniform(0, 6)), curl=(.004, .8), margin=.009, seed=50 + i)
        paths.append(path)
        widths.append(H.taper(14, rng.uniform(.028, .036), .14))
    for side in (1, -1):
        for i in range(3):
            root = c + np.array([side * r[0] * .82, r[1] * .2 - i * .008, r[2] * (.45 - i * .12)])
            root = vol.push_out(root[None], .004)[0]
            path = H.free_path(vol, root, np.array([side * .3, -1, .15]), rng.uniform(.09, .14), 16, gravity=1, stiff=.3,
                               wave=(.008, 1.3, rng.uniform(0, 6)), curl=(.006, 1.4), margin=.008, seed=80 + i + side * 7)
            paths.append(path)
            widths.append(H.taper(16, rng.uniform(.016, .022), .1))
    emit(b, 'bangs', mat, paths, widths, vol, tip_scale=.8)
    # Elástico do rabo.
    ring = [G + .011 * (np.cos(a) * np.array([1, 0, 0]) + np.sin(a) * np.array([0, .6, .8])) for a in np.linspace(0, 2 * np.pi, 25)]
    pos, nrm, uv, tris, _ = hair.tube_mesh([np.array(ring)], [np.full(25, .004)], sides=6)
    band = b.glb.material('tie', color=(.45, .06, .04, 1), roughness=.5)
    b.bound('tie', pos, tris, uv, band, nrm=nrm, bone='Head')
    return b.save({'tips': True})
