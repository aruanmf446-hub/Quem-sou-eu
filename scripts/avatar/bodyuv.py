"""Layout de UV do corpo: o rosto/cabeça recebe uma textura própria com o dobro de resolução."""
from __future__ import annotations

import numpy as np

import mh


def uv_islands(mesh, faces):
    parent = list(range(len(mesh.uvs)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for f in faces:
        for _, t in f[1:]:
            a, b = find(f[0][1]), find(t)
            if a != b:
                parent[a] = b
    return [find(f[0][1]) for f in faces]


class BodyLayout:
    """faces: lista de (material, [(v, uv_gltf)])"""

    def __init__(self, model):
        mesh = model.mesh
        faces = mesh.groups['body']
        island = uv_islands(mesh, faces)
        head_islands = set()
        for key in set(island):
            vs = [v for f, k in zip(faces, island) if k == key for v, _ in f]
            if model.coords[vs, 1].mean() > model.heads['Neck'][1] - .02:
                head_islands.add(key)
        head_uv = np.array([t for f, k in zip(faces, island) if k in head_islands for _, t in f])
        self.uv_min = mesh.uvs[head_uv].min(0) - .004
        self.uv_max = mesh.uvs[head_uv].max(0) + .004
        self.faces = []
        for f, k in zip(faces, island):
            mat = 'head' if k in head_islands else 'body'
            corners = []
            for v, t in f:
                uv = mesh.uvs[t].copy()
                if mat == 'head':
                    uv = (uv - self.uv_min) / (self.uv_max - self.uv_min)
                corners.append((v, np.array([uv[0], 1 - uv[1]])))
            self.faces.append((mat, corners))

    def original_uv(self, mat, uv):
        """Converte UV (glTF) do material para a UV original do MakeHuman (glTF)."""
        if mat == 'body':
            return uv
        u = uv[..., 0] * (self.uv_max[0] - self.uv_min[0]) + self.uv_min[0]
        v = (1 - uv[..., 1]) * (self.uv_max[1] - self.uv_min[1]) + self.uv_min[1]
        return np.stack([u, 1 - v], -1)

    def triangles(self, mat):
        """Retorna (verts (T,3), uv (T,3,2)) do material."""
        vs, uvs = [], []
        for m, corners in self.faces:
            if m != mat:
                continue
            for tri in mh.triangulate([corners]):
                vs.append([c[0] for c in tri])
                uvs.append([c[1] for c in tri])
        return np.array(vs), np.array(uvs)
