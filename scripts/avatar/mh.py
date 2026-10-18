"""Leitura dos dados CC0 do MakeHuman/MPFB usados pelo avatar.

Coordenadas: o OBJ do MakeHuman é Y-up, em decímetros, com o personagem olhando
para +Z. Convertemos para metros e apoiamos os pés em y=0, que é exatamente a
convenção glTF/three.js.
"""
from __future__ import annotations

import gzip
import json
import os
from dataclasses import dataclass, field

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
SCALE = 0.1


@dataclass
class BaseMesh:
    coords: np.ndarray            # (V, 3) posição em metros, já apoiada no chão
    uvs: np.ndarray               # (T, 2) coordenadas de textura (origem embaixo, como no OBJ)
    groups: dict[str, list]       # grupo -> lista de faces [(vi, ti), ...]
    ground: float                 # deslocamento aplicado em y
    vertex_groups: dict[str, np.ndarray] = field(default_factory=dict)

    def group_vertices(self, name: str) -> np.ndarray:
        if name not in self.vertex_groups:
            ids = sorted({v for f in self.groups[name] for v, _ in f})
            self.vertex_groups[name] = np.array(ids, dtype=np.int64)
        return self.vertex_groups[name]

    def joint(self, name: str, coords: np.ndarray | None = None) -> np.ndarray:
        c = self.coords if coords is None else coords
        return c[self.group_vertices(name)].mean(axis=0)


def load_base(path: str | None = None) -> BaseMesh:
    path = path or os.path.join(DATA, 'base.obj')
    verts, uvs, groups, current = [], [], {}, 'body'
    with open(path) as fh:
        for line in fh:
            if line.startswith('v '):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('vt '):
                uvs.append([float(x) for x in line.split()[1:3]])
            elif line.startswith('g '):
                current = line.split()[1]
            elif line.startswith('f '):
                face = []
                for item in line.split()[1:]:
                    parts = item.split('/')
                    face.append((int(parts[0]) - 1, int(parts[1]) - 1 if len(parts) > 1 and parts[1] else -1))
                groups.setdefault(current, []).append(face)
    coords = np.array(verts, dtype=np.float64) * SCALE
    mesh = BaseMesh(coords=coords, uvs=np.array(uvs, dtype=np.float64), groups=groups, ground=0.0)
    ground = mesh.joint('joint-ground')[1]
    mesh.coords[:, 1] -= ground
    mesh.ground = ground
    return mesh


def load_target(name: str, count: int) -> np.ndarray:
    """Retorna deltas densos (V, 3) em metros de um arquivo .target(.gz)."""
    path = os.path.join(DATA, 'targets', name + '.target.gz')
    delta = np.zeros((count, 3), dtype=np.float64)
    with gzip.open(path, 'rt') as fh:
        for line in fh:
            if not line.strip() or line.startswith('#'):
                continue
            a = line.split()
            delta[int(a[0])] = (float(a[1]), float(a[2]), float(a[3]))
    return delta * SCALE


class TargetCache:
    def __init__(self, count: int):
        self.count = count
        self.cache: dict[str, np.ndarray] = {}

    def __call__(self, name: str) -> np.ndarray:
        if name not in self.cache:
            self.cache[name] = load_target(name, self.count)
        return self.cache[name]

    def has(self, name: str) -> bool:
        return os.path.exists(os.path.join(DATA, 'targets', name + '.target.gz'))


ETHNIC = ('african', 'asian', 'caucasian')


def macro_delta(t: TargetCache, gender: float, muscle: float = .5, weight: float = .5,
                height: float = .5, proportions: float = .5, ethnic=(1/3, 1/3, 1/3), age: float = 1.0) -> np.ndarray:
    """Avalia os macro-modificadores do MakeHuman para um adulto jovem.

    Implementação própria das regras públicas do macro.json: cada eixo é uma
    interpolação linear entre seus extremos e as combinações são produtos dos pesos.
    """
    g = {'female': 1 - gender, 'male': gender}

    def axis(v, low, mid, high):
        if v < .5:
            return {low: (.5 - v) * 2, mid: v * 2}
        return {mid: (1 - v) * 2, high: (v - .5) * 2}

    m = axis(muscle, 'minmuscle', 'averagemuscle', 'maxmuscle')
    w = axis(weight, 'minweight', 'averageweight', 'maxweight')
    # Idade: 1 = adulto jovem, 0 = criança (interpolação linear entre os dois conjuntos de alvos).
    ages = [(a, aw) for a, aw in (('young', age), ('child', 1 - age)) if aw > 0]
    out = np.zeros((t.count, 3))
    for a, aw in ages:
        for race, rw in zip(ETHNIC, ethnic):
            for sex, sw in g.items():
                if rw * sw > 0:
                    out += t(f'macrodetails/{race}-{sex}-{a}') * rw * sw * aw
        for sex, sw in g.items():
            for mk, mw in m.items():
                for wk, ww in w.items():
                    k = sw * mw * ww * aw
                    if k <= 0:
                        continue
                    out += t(f'macrodetails/universal-{sex}-{a}-{mk}-{wk}') * k
                    if height != .5:
                        side = 'maxheight' if height > .5 else 'minheight'
                        out += t(f'macrodetails/height/{sex}-{a}-{mk}-{wk}-{side}') * k * abs(height - .5) * 2
                    if proportions != .5:
                        side = 'idealproportions' if proportions > .5 else 'uncommonproportions'
                        name = f'macrodetails/proportions/{sex}-{a}-{mk}-{wk}-{side}'
                        if t.has(name):
                            out += t(name) * k * abs(proportions - .5) * 2
                    if sex == 'female':
                        name = f'breast/female-{a}-{mk}-{wk}-averagecup-averagefirmness'
                        if t.has(name):
                            out += t(name) * k
    return out


@dataclass
class Bone:
    name: str
    parent: str | None
    head: np.ndarray
    tail: np.ndarray


def _bone_point(mesh: BaseMesh, spec: dict, coords: np.ndarray) -> np.ndarray:
    if spec['strategy'] == 'CUBE':
        return mesh.joint(spec['cube_name'], coords)
    if spec['strategy'] in ('MEAN', 'VERTEX'):
        return coords[np.array(spec['vertex_indices'])].mean(axis=0)
    raise ValueError(spec['strategy'])


def load_rig(mesh: BaseMesh, coords: np.ndarray, name='mixamo') -> list[Bone]:
    """Esqueleto padrão Mixamo (52 ossos) posicionado pelos cubos de junta da malha."""
    spec = json.load(open(os.path.join(DATA, f'rig.{name}.json')))['bones']
    bones = []
    for bname, b in spec.items():
        short = bname.replace('mixamorig:', '')
        parent = b['parent'].replace('mixamorig:', '') if b.get('parent') else None
        bones.append(Bone(short, parent, _bone_point(mesh, b['head'], coords), _bone_point(mesh, b['tail'], coords)))
    # Ordem topológica: pais antes dos filhos.
    order, seen = [], set()
    by = {b.name: b for b in bones}

    def visit(b):
        if b.name in seen:
            return
        if b.parent:
            visit(by[b.parent])
        seen.add(b.name)
        order.append(b)
    for b in sorted(bones, key=lambda b: b.name):
        visit(b)
    return order


def rig_points(name='mixamo'):
    return json.load(open(os.path.join(DATA, f'rig.{name}.json')))['bones']


def load_weights(count: int, name='mixamo') -> tuple[list[str], np.ndarray]:
    """Matriz densa (V, ossos) de pesos de deformação."""
    data = json.load(open(os.path.join(DATA, f'weights.{name}.json')))['weights']
    names = [n.replace('mixamorig:', '') for n in data]
    W = np.zeros((count, len(names)), dtype=np.float32)
    for j, (bname, pairs) in enumerate(data.items()):
        for idx, w in pairs:
            W[idx, j] += w
    return names, W


def triangulate(faces):
    tris = []
    for f in faces:
        for i in range(1, len(f) - 1):
            tris.append((f[0], f[i], f[i + 1]))
    return tris
