"""Construtor de peças modulares compatíveis com o avatar-base.

Uma peça pode ser:
- camada de pele (faces do próprio corpo deslocadas pela normal): pesos e morphs exatos;
- geometria livre (roupa, sapato, cabelo, acessório) amarrada à superfície do corpo
  por baricêntricas: pesos e morphs transferidos automaticamente.
"""
from __future__ import annotations

import os

import numpy as np

from glb import GLB
from model import AvatarModel, top4, vertex_normals

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'public', 'avatar', 'items')


class ItemBuilder:
    def __init__(self, model: AvatarModel, item_id: str, slot: str):
        self.model = model
        self.id = item_id
        self.slot = slot
        self.glb = GLB()
        roots, self.skin = self.glb.skeleton(model.bones, model.heads)
        self.glb.doc['scenes'][0]['nodes'].append(self.glb.node(name='AvatarRig', children=roots))
        self.count = 0
        self.tris = 0

    def _emit(self, name, pos, nrm, uv, tris, material, weights, morphs, extra_attrs=None, morph_normals=None):
        joints, w = top4(weights)
        names, deltas = [], []
        for mname in self.model.morph_names:
            d = morphs.get(mname)
            if d is None or np.abs(d).max() < 1e-5:
                continue
            names.append(mname)
            deltas.append((d, morph_normals.get(mname) if morph_normals else None))
        prim = self.glb.primitive(pos, nrm, uv, tris, material, joints, w, deltas)
        if extra_attrs:
            for k, v in extra_attrs.items():
                prim['attributes'][k] = self.glb.accessor(v, target=34962)
        mid = self.glb.mesh(f'{self.id}_{name}', [prim], names, extras={'layer': self.slot})
        node = self.glb.node(name=f'{self.id}_{name}', mesh=mid, skin=self.skin)
        self.glb.doc['scenes'][0]['nodes'].append(node)
        self.count += 1
        self.tris += len(tris)

    def skin_layer(self, name, corners_faces, offset, material, uv_fn=None, offset_fn=None, attrs_fn=None, normal_fn=None):
        """corners_faces: lista de faces [(v, uv)]. Desloca a pele pela normal."""
        index, verts, uvs, tris = {}, [], [], []
        for corners in corners_faces:
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
        m = self.model
        n = m.normals[v]
        off = offset if offset_fn is None else offset_fn(m.coords[v], n)
        off = np.broadcast_to(np.asarray(off, float).reshape(-1, 1) if np.ndim(off) else np.full((len(v), 1), off), (len(v), 1))
        pos = m.coords[v] + n * off
        morphs = {k: d[v] for k, d in m.morphs.items()}
        uv = np.array(uvs) if uv_fn is None else uv_fn(pos, np.array(uvs))
        tris = np.array(tris)
        if normal_fn is not None:
            n = normal_fn(pos, tris, n)
        attrs = attrs_fn(m.coords[v], pos) if attrs_fn else None
        self._emit(name, pos, n, uv, tris, material, m.weights[v], morphs, attrs)
        return v

    def bound(self, name, pos, tris, uv, material, nrm=None, surface=None, bone=None, rigid=False, extra_attrs=None):
        """Geometria livre amarrada ao corpo. bone força pesos 100% em um osso (cabelo, óculos)."""
        m = self.model
        pos = np.asarray(pos, float)
        tris = np.asarray(tris)
        if rigid and bone and surface is None:
            # Peça rígida presa a um osso: os morphs (proporções) vêm só da pele desse osso. Sem isso, um
            # cajado longo herdaria a média de cabeça, tronco e pernas e se descolaria da mão.
            dom = np.argmax(m.weights, 1)
            own = m.body_tris[(dom[m.body_tris] == m.bone_index(bone)).all(1)]
            if len(own):
                surface = own
        ids, bary, _ = m.bind(pos, surface)
        if bone:
            W = np.zeros((len(pos), len(m.bone_names)), np.float32)
            W[:, m.bone_index(bone)] = 1
        else:
            W = m.bound_weights(ids, bary)
        if rigid:
            # Translação média (sem deformar) para acessórios rígidos.
            morphs = {}
            for k, d in m.bound_morphs(ids, bary).items():
                morphs[k] = np.broadcast_to(d.mean(0), d.shape).copy()
        else:
            morphs = m.bound_morphs(ids, bary)
        # Morphs que mexem menos de meio milímetro na peça não valem o peso no arquivo.
        morphs = {k: v for k, v in morphs.items() if np.abs(v).max() > 5e-4}
        if nrm is None:
            nrm = vertex_normals(pos, tris)
        self._emit(name, pos, nrm, uv, tris, material, W, morphs, extra_attrs)

    def derived(self, name, s, material, weight_smooth=3, normals=None, attrs=None):
        """Superfície derivada da anatomia (garments.Surface): pesos/morphs do vértice de origem."""
        from garments import smooth_values, vertex_normals_canon
        m = self.model
        W = m.weights[s.vid]
        if weight_smooth:
            W = smooth_values(s, W, weight_smooth)
        morphs = {k: d[s.vid] for k, d in m.morphs.items() if not k.startswith('expr_')}
        n = vertex_normals_canon(s) if normals is None else normals
        self._emit(name, s.pos, n, s.uv, s.tris, material, W, morphs, attrs)

    def save(self, extras):
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, f'{self.id}.glb')
        size = self.glb.save(path, dict(extras, slot=self.slot, id=self.id))
        print(f'  {self.id}: {size / 1024:.0f} KB, {self.tris} tris')
        return path
