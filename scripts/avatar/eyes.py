"""Olhos procedurais: esclera, íris com profundidade e córnea com reflexo."""
from __future__ import annotations

import numpy as np
from PIL import Image

from model import top4


def sphere(radius, seg=40, rings=28, max_angle=np.pi):
    """Esfera com polo em +Z; retorna (pos, tris, theta). theta = ângulo a partir de +Z."""
    th = np.linspace(0, max_angle, rings + 1)
    ph = np.linspace(0, 2 * np.pi, seg + 1)[:-1]
    T, P = np.meshgrid(th, ph, indexing='ij')
    pos = np.stack([np.sin(T) * np.cos(P), np.sin(T) * np.sin(P), np.cos(T)], -1).reshape(-1, 3) * radius
    tris = []
    for r in range(rings):
        for s in range(seg):
            a, b = r * seg + s, r * seg + (s + 1) % seg
            c, d = (r + 1) * seg + s, (r + 1) * seg + (s + 1) % seg
            if r > 0:
                tris.append((a, c, b))
            tris.append((b, c, d))
    return pos, np.array(tris), T.reshape(-1)


def iris_texture(size=512, seed=2):
    rng = np.random.default_rng(seed)
    yy, xx = (np.mgrid[0:size, 0:size] + .5) / size * 2 - 1
    r = np.hypot(xx, yy)
    a = np.arctan2(yy, xx)
    fibers = np.zeros_like(r)
    for k, amp in ((48, .5), (97, .3), (190, .2)):
        phase = rng.uniform(0, 2 * np.pi, 8)
        fibers += amp * (.5 + .5 * np.sin(a * k + 3 * np.sin(a * 5 + phase[0]) + r * 6))
    collar = np.exp(-((r - .52) / .06) ** 2)
    lum = .55 + .35 * fibers * (r > .36) - .25 * (r - .4).clip(0) * 1.4 + .25 * collar
    lum = lum * (1 - .75 * np.clip((r - .86) / .14, 0, 1))  # anel límbico
    pupil = np.clip((r - .36) / .03, 0, 1)
    lum = lum * pupil
    img = np.clip(np.stack([lum, lum, lum], -1), 0, 1)
    return Image.fromarray((img * 255).astype(np.uint8), 'RGB')


def sclera_texture(size=512, seed=3):
    rng = np.random.default_rng(seed)
    yy, xx = (np.mgrid[0:size, 0:size] + .5) / size * 2 - 1
    r = np.hypot(xx, yy)
    base = np.stack([np.full_like(r, .86), np.full_like(r, .82), np.full_like(r, .79)], -1)
    veins = np.zeros_like(r)
    for _ in range(40):
        ang = rng.uniform(0, 2 * np.pi)
        wob = rng.uniform(4, 9)
        a = np.arctan2(yy, xx)
        d = np.abs(np.sin((a - ang) * 1.0 + np.sin(r * wob) * .08)) * r
        veins += np.exp(-(d / .006) ** 2) * np.clip((r - .55) / .4, 0, 1) * rng.uniform(.2, .6)
    tint = np.array([.78, .38, .38])
    edge = np.clip((r - .6) / .4, 0, 1)[..., None]
    img = base * (1 - .3 * edge ** 1.5) + (tint - base) * np.clip(veins, 0, 1)[..., None] * .5
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGB')


def build(model, glb, skin_index):
    iris_tex = glb.texture(iris_texture(), fmt='jpeg', quality=92)
    sclera_tex = glb.texture(sclera_texture(), fmt='jpeg', quality=90)
    m_sclera = glb.material('EyeSclera', base=sclera_tex, roughness=.25)
    m_iris = glb.material('EyeIris', base=iris_tex, roughness=.35, extras={'irisColor': True})
    m_cornea = glb.material('EyeCornea', color=(1, 1, 1, .06), roughness=.02, alpha=('BLEND', 0),
                            clearcoat=(1.0, .02), extras={'cornea': True})
    # Duas variantes: realista e estilo animação (íris maior), escolhidas no runtime pelo estilo.
    for variant, iris_ratio in (('real', .5), ('toon', .64)):
        build_side(model, glb, skin_index, m_sclera, m_iris, m_cornea, variant, iris_ratio)


def build_side(model, glb, skin_index, m_sclera, m_iris, m_cornea, variant, iris_ratio):
    for side, src in (('Left', 'l'), ('Right', 'r')):
        helper = model.mesh.group_vertices(f'helper-{src}-eye')
        hp = model.coords[helper]
        c = hp.mean(0)
        radius = np.linalg.norm(hp - c, axis=1).mean() * .97
        iris_angle = np.arcsin(iris_ratio)
        # Esclera + íris (a íris é um plano recuado, como no olho real).
        pos, tris, theta = sphere(radius)
        flat = theta < iris_angle
        iris_z = radius * np.cos(iris_angle)
        pos[flat, 2] = iris_z + (pos[flat, 2] - iris_z) * .12
        tri_theta = theta[tris].mean(1)
        uv = np.stack([.5 + pos[:, 0] / (2 * radius * iris_ratio), .5 - pos[:, 1] / (2 * radius * iris_ratio)], 1)
        uv_s = np.stack([.5 + pos[:, 0] / (2 * radius), .5 - pos[:, 1] / (2 * radius)], 1)
        nrm = pos / np.linalg.norm(pos, axis=1, keepdims=True)
        nrm[flat] = nrm[flat] * .3 + np.array([0, 0, .7])
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        cornea, ctris, _ = sphere(radius * 1.015, 40, 14, np.radians(48))
        bulge = np.clip(1 - np.arccos(np.clip(cornea[:, 2] / (radius * 1.015), -1, 1)) / np.radians(48), 0, 1)
        cornea[:, 2] += radius * .07 * bulge ** 2
        # O olho em repouso olha levemente para cima: a pálpebra superior cobre o topo da íris.
        tilt = np.radians(-7)
        rot = np.array([[1, 0, 0], [0, np.cos(tilt), -np.sin(tilt)], [0, np.sin(tilt), np.cos(tilt)]])
        pos, nrm, cornea = pos @ rot.T, nrm @ rot.T, cornea @ rot.T
        world = pos + c
        cnrm = cornea / np.linalg.norm(cornea, axis=1, keepdims=True)
        cworld = cornea + c
        # Morph rígido: translação + escala ajustadas ao helper do MakeHuman.
        def morphs_for(points):
            names, out = [], []
            for name in model.morph_names:
                d = model.morphs[name][helper]
                if np.abs(d).max() < 1e-5:
                    continue
                t = d.mean(0)
                rel = hp - c
                s = ((d - t) * rel).sum() / (rel * rel).sum()
                names.append(name)
                out.append((t + s * (points - c), None))
            return names, out
        bone = model.bone_index(f'{side}Eye')
        for part, verts, faces, mat, uvs, normals in (
            ('sclera', world, tris[tri_theta >= iris_angle], m_sclera, uv_s, nrm),
            ('iris', world, tris[tri_theta < iris_angle], m_iris, uv, nrm),
            ('cornea', cworld, ctris, m_cornea, uv_s[:len(cworld)] * 0, cnrm),
        ):
            used = np.unique(faces)
            remap = np.full(len(verts), -1)
            remap[used] = np.arange(len(used))
            W = np.zeros((len(used), len(model.bone_names)), np.float32)
            W[:, bone] = 1
            joints, weights = top4(W)
            names, morphs = morphs_for(verts[used])
            prim = glb.primitive(verts[used], normals[used], uvs[used], remap[faces], mat, joints, weights, morphs)
            mid = glb.mesh(f'eye_{part}_{src}_{variant}', [prim], names, extras={'layer': 'eyes', 'eyeSet': variant})
            node = glb.node(name=f'eye_{part}_{src}_{variant}', mesh=mid, skin=skin_index)
            glb.doc['scenes'][0]['nodes'].append(node)
