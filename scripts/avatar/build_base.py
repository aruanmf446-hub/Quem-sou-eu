"""Gera public/avatar/base.glb: corpo com regiões ocultáveis, olhos, cílios, dentes e esqueleto.

python3 scripts/avatar/build_base.py
"""
from __future__ import annotations

import json
import os

import numpy as np

import mh
from glb import GLB
from model import AvatarModel, top4, vertex_normals
import skin_textures
from bodyuv import BodyLayout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'public', 'avatar')

# Faixas do corpo. Uma roupa declara quais faixas cobre por completo e o runtime as oculta.
BONE_REGION = {
    'Head': 'head', 'LeftEye': 'head', 'RightEye': 'head', 'Neck': 'neck',
    'Spine2': 'chest', 'Spine1': 'chest', 'LeftShoulder': 'chest', 'RightShoulder': 'chest',
    'Spine': 'belly', 'Hips': 'hips',
    'LeftArm': 'upperarm', 'RightArm': 'upperarm', 'LeftForeArm': 'forearm', 'RightForeArm': 'forearm',
    'LeftUpLeg': 'thigh', 'RightUpLeg': 'thigh', 'LeftLeg': 'shin', 'RightLeg': 'shin',
    'LeftFoot': 'feet', 'RightFoot': 'feet', 'LeftToeBase': 'feet', 'RightToeBase': 'feet',
}
SPLIT = {'upperarm', 'forearm', 'thigh', 'shin'}


def region_of(model: AvatarModel, verts):
    w = model.weights[verts].sum(axis=0)
    bone = model.bone_names[int(np.argmax(w))]
    if 'Hand' in bone:
        return 'hands'
    region = BONE_REGION.get(bone, 'chest')
    if region in SPLIT:
        head, tail = model.heads[bone], model.tails[bone]
        p = model.coords[verts].mean(axis=0)
        t = np.dot(p - head, tail - head) / np.dot(tail - head, tail - head)
        region += '_' + 'abcd'[int(np.clip(t * 4, 0, 3))]
    return region


def build_body(model: AvatarModel, glb: GLB, skin_index, materials, layout: BodyLayout):
    normals = vertex_normals(model.coords, model.body_tris)
    morph_normals = {name: vertex_normals(model.coords + d, model.body_tris) - normals for name, d in model.morphs.items()}
    groups: dict[tuple[str, str], list] = {}
    for mat, corners in layout.faces:
        region = region_of(model, [v for v, _ in corners])
        groups.setdefault((region, mat), []).append(corners)
    regions = {}
    for (region, mat), fs in sorted(groups.items()):
        index = {}
        verts, uvs, tris = [], [], []
        for corners in fs:
            ids = []
            for v, uv in corners:
                key = (v, round(float(uv[0]), 6), round(float(uv[1]), 6))
                if key not in index:
                    index[key] = len(verts)
                    verts.append(v)
                    uvs.append(uv)
                ids.append(index[key])
            for i in range(1, len(ids) - 1):
                tris.append((ids[0], ids[i], ids[i + 1]))
        v = np.array(verts)
        joints, weights = top4(model.weights[v])
        names, morphs = [], []
        for name in model.morph_names:
            d = model.morphs[name][v]
            if np.abs(d).max() > 1e-5:
                names.append(name)
                morphs.append((d, morph_normals[name][v]))
        prim = glb.primitive(model.coords[v], normals[v], np.array(uvs), np.array(tris), materials[mat],
                             joints, weights, morphs)
        mid = glb.mesh(f'body_{region}_{mat}', [prim], names, extras={'region': region, 'layer': 'skin'})
        node = glb.node(name=f'body_{region}_{mat}', mesh=mid, skin=skin_index)
        glb.doc['scenes'][0]['nodes'].append(node)
        regions.setdefault(region, []).append(f'body_{region}_{mat}')
    return regions


def underwear(model, glb, skin_index, layout):
    """Roupa íntima neutra: o avatar nunca aparece sem roupa, mesmo sem peças carregadas."""
    from garments import Anatomy
    A = Anatomy(model)
    from wardrobe import nipple_centers
    nip = nipple_centers(model)
    mat = glb.material('Underwear', color=(.035, .038, .05, 1), roughness=.75, sheen=((.3, .3, .35), .6))
    hips_y = model.heads['Hips'][1]

    def bottom(v):
        b = A.bone[v]
        y = model.coords[v, 1]
        return ((np.isin(b, ('Hips', 'Spine')) & (y < hips_y + .055)) | (np.isin(b, ('LeftUpLeg', 'RightUpLeg')) & (A.t[v] < .1))).all()

    def top(v):
        b = A.bone[v]
        y = model.coords[v, 1]
        return (np.isin(b, ('Spine1', 'Spine2', 'LeftShoulder', 'RightShoulder', 'Spine')) & (y > nip[:, 1].mean() - .075) & (y < nip[:, 1].mean() + .07)).all()
    for name, pred, off in (('underwear_bottom', bottom, .0014), ('underwear_top', top, .0018)):
        faces = [c for m, c in layout.faces if m == 'body' and pred(np.array([v for v, _ in c]))]
        index, verts, uvs, tris = {}, [], [], []
        for corners in faces:
            ids = []
            for v, uv in corners:
                key = (v, round(float(uv[0]), 6), round(float(uv[1]), 6))
                if key not in index:
                    index[key] = len(verts)
                    verts.append(v)
                    uvs.append(uv)
                ids.append(index[key])
            for i in range(1, len(ids) - 1):
                tris.append((ids[0], ids[i], ids[i + 1]))
        v = np.array(verts)
        pos = model.coords[v] + model.normals[v] * off
        joints, weights = top4(model.weights[v])
        names, morphs = [], []
        for mname in model.morph_names:
            d = model.morphs[mname][v]
            if np.abs(d).max() > 1e-5 and not mname.startswith('expr_'):
                names.append(mname)
                morphs.append((d, None))
        prim = glb.primitive(pos, model.normals[v], np.array(uvs), np.array(tris), mat, joints, weights, morphs)
        mid = glb.mesh(name, [prim], names, extras={'layer': name})
        glb.doc['scenes'][0]['nodes'].append(glb.node(name=name, mesh=mid, skin=skin_index))


def helper_part(model, glb, skin_index, group, material, name, uv_override=None, extra=None):
    mesh = model.mesh
    faces = mesh.groups[group]
    corners, verts, uvs, tris = {}, [], [], []
    for f in faces:
        ids = []
        for v, t in f:
            if (v, t) not in corners:
                corners[(v, t)] = len(verts)
                verts.append(v)
                uv = mesh.uvs[t] if t >= 0 else np.zeros(2)
                uvs.append([uv[0], 1 - uv[1]])
            ids.append(corners[(v, t)])
        for i in range(1, len(ids) - 1):
            tris.append((ids[0], ids[i], ids[i + 1]))
    v = np.array(verts)
    tris = np.array(tris)
    pos = model.coords[v]
    local = {g: i for i, g in enumerate(v)}
    nrm = vertex_normals(pos, tris)
    joints, weights = top4(model.weights[v])
    names, morphs = [], []
    for mname in model.morph_names:
        d = model.morphs[mname][v]
        if np.abs(d).max() > 1e-5:
            names.append(mname)
            morphs.append((d, None))
    uv = np.array(uvs) if uv_override is None else uv_override(pos, np.array(uvs))
    prim = glb.primitive(pos, nrm, uv, tris, material, joints, weights, morphs)
    mid = glb.mesh(name, [prim], names, extras=dict(extra or {}, layer=name))
    node = glb.node(name=name, mesh=mid, skin=skin_index)
    glb.doc['scenes'][0]['nodes'].append(node)
    return local


def build(out_path=None):
    model = AvatarModel()
    glb = GLB()
    roots, skin_index = glb.skeleton(model.bones, model.heads)
    armature = glb.node(name='AvatarRig', children=roots)
    glb.doc['scenes'][0]['nodes'].append(armature)
    layout = BodyLayout(model)
    tex = skin_textures.generate(model, layout)
    materials = {
        'body': glb.material('Skin', base=glb.texture(tex['body_albedo'], fmt='jpeg', quality=90),
                             normal=glb.texture(tex['body_normal'], fmt='webp', quality=92), orm=glb.texture(tex['body_orm'], fmt='jpeg', quality=88),
                             roughness=1, extras={'skin': True}),
        'head': glb.material('SkinHead', base=glb.texture(tex['head_albedo'], fmt='jpeg', quality=92),
                             normal=glb.texture(tex['head_normal'], fmt='webp', quality=92), orm=glb.texture(tex['head_orm'], fmt='jpeg', quality=88),
                             roughness=1, extras={'skin': True}),
    }
    regions = build_body(model, glb, skin_index, materials, layout)
    lash = glb.material('Eyelashes', color=(.05, .04, .04, 1), base=glb.texture(tex['lashes'], fmt='png'), roughness=.7,
                        alpha=('BLEND', 0), double=True, extras={'hairColor': 'brows'})
    for side in 'lr':
        center = model.mesh.joint(f'helper-{side}-eye', model.coords)

        def lash_uv(pos, _uv, center=center):
            rel = pos - center
            ang = np.arctan2(rel[:, 1], rel[:, 0] * (1 if side == 'l' else -1))
            u = (ang - ang.min()) / max(ang.max() - ang.min(), 1e-6)
            r = np.linalg.norm(rel[:, :2], axis=1)
            v = (r - r.min()) / max(r.max() - r.min(), 1e-6)
            return np.stack([u, v], 1)
        for i in (1, 2):
            helper_part(model, glb, skin_index, f'helper-{side}-eyelashes-{i}', lash, f'lashes_{side}{i}', lash_uv)
    teeth = glb.material('Teeth', color=(.92, .89, .82, 1), roughness=.35)
    helper_part(model, glb, skin_index, 'helper-upper-teeth', teeth, 'teeth_upper')
    helper_part(model, glb, skin_index, 'helper-lower-teeth', teeth, 'teeth_lower')
    tongue = glb.material('Tongue', color=(.62, .27, .28, 1), roughness=.45)
    helper_part(model, glb, skin_index, 'helper-tongue', tongue, 'tongue')
    import eyes
    eyes.build(model, glb, skin_index)
    underwear(model, glb, skin_index, layout)
    extras = {
        'avatar': 1,
        'morphs': model.morph_names,
        'jointDeltas': model.joint_deltas,
        'regions': regions,
        'bones': model.bone_names,
    }
    os.makedirs(OUT, exist_ok=True)
    size = glb.save(out_path or os.path.join(OUT, 'base.glb'), extras)
    print(f'base.glb {size / 1024:.0f} KB, {len(model.morph_names)} morphs')
    return model


if __name__ == '__main__':
    build()
