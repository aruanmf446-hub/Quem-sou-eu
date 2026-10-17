"""Escritor mínimo de GLB 2.0 com skin, morph targets e materiais PBR."""
from __future__ import annotations

import io
import json
import struct

import numpy as np
from PIL import Image

FLOAT, USHORT, UINT, UBYTE = 5126, 5123, 5125, 5121
TYPES = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4', 16: 'MAT4'}


class GLB:
    def __init__(self):
        self.doc = {'asset': {'version': '2.0', 'generator': 'quem-sou-eu avatar pipeline'},
                    'scene': 0, 'scenes': [{'nodes': []}], 'nodes': [], 'meshes': [],
                    'accessors': [], 'bufferViews': [], 'buffers': [], 'materials': [],
                    'textures': [], 'images': [], 'samplers': [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}],
                    'skins': [], 'extensionsUsed': []}
        self.bin = bytearray()
        self.texture_cache = {}

    # -- dados binários -------------------------------------------------
    def _view(self, data: bytes, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target:
            view['target'] = target
        self.bin.extend(data)
        self.doc['bufferViews'].append(view)
        return len(self.doc['bufferViews']) - 1

    def accessor(self, array, component=FLOAT, target=None, minmax=False, normalized=False):
        a = np.asarray(array)
        width = 1 if a.ndim == 1 else a.shape[1]
        dtype = {FLOAT: np.float32, USHORT: np.uint16, UINT: np.uint32, UBYTE: np.uint8}[component]
        data = np.ascontiguousarray(a.astype(dtype))
        acc = {'bufferView': self._view(data.tobytes(), target), 'componentType': component,
               'count': int(a.shape[0]), 'type': TYPES[width]}
        if normalized:
            acc['normalized'] = True
        if minmax:
            acc['min'] = [float(x) for x in np.atleast_1d(data.min(axis=0))]
            acc['max'] = [float(x) for x in np.atleast_1d(data.max(axis=0))]
        self.doc['accessors'].append(acc)
        return len(self.doc['accessors']) - 1

    def sparse_accessor(self, delta):
        """Delta de morph em formato esparso (só vértices que mudam)."""
        d = np.asarray(delta, dtype=np.float32)
        nz = np.nonzero(np.abs(d).max(axis=1) > 1e-6)[0].astype(np.uint32)
        acc = {'componentType': FLOAT, 'count': int(d.shape[0]), 'type': 'VEC3',
               'min': [float(x) for x in d.min(axis=0)], 'max': [float(x) for x in d.max(axis=0)]}
        if len(nz):
            acc['sparse'] = {'count': int(len(nz)),
                             'indices': {'bufferView': self._view(nz.tobytes()), 'componentType': UINT},
                             'values': {'bufferView': self._view(np.ascontiguousarray(d[nz]).tobytes())}}
        self.doc['accessors'].append(acc)
        return len(self.doc['accessors']) - 1

    # -- texturas -------------------------------------------------------
    def texture(self, image: Image.Image, key=None, fmt='webp', quality=88, lossless=False):
        if key and key in self.texture_cache:
            return self.texture_cache[key]
        buf = io.BytesIO()
        if fmt == 'webp':
            image.save(buf, 'WEBP', quality=quality, method=6, lossless=lossless)
            mime = 'image/webp'
            if 'EXT_texture_webp' not in self.doc['extensionsUsed']:
                self.doc['extensionsUsed'].append('EXT_texture_webp')
                self.doc.setdefault('extensionsRequired', []).append('EXT_texture_webp')
        elif fmt == 'jpeg':
            image.convert('RGB').save(buf, 'JPEG', quality=quality, optimize=True)
            mime = 'image/jpeg'
        else:
            image.save(buf, 'PNG', optimize=True)
            mime = 'image/png'
        self.doc['images'].append({'bufferView': self._view(buf.getvalue()), 'mimeType': mime})
        img = len(self.doc['images']) - 1
        tex = {'sampler': 0}
        if mime == 'image/webp':
            tex['extensions'] = {'EXT_texture_webp': {'source': img}}
        else:
            tex['source'] = img
        self.doc['textures'].append(tex)
        index = len(self.doc['textures']) - 1
        if key:
            self.texture_cache[key] = index
        return index

    def material(self, name, color=(1, 1, 1, 1), metallic=0.0, roughness=.8, base=None, normal=None,
                 normal_scale=1.0, orm=None, emissive=None, alpha=None, double=False, sheen=None,
                 clearcoat=None, extras=None):
        pbr = {'baseColorFactor': list(color), 'metallicFactor': metallic, 'roughnessFactor': roughness}
        if base is not None:
            pbr['baseColorTexture'] = {'index': base}
        if orm is not None:
            pbr['metallicRoughnessTexture'] = {'index': orm}
        m = {'name': name, 'pbrMetallicRoughness': pbr}
        if orm is not None:
            m['occlusionTexture'] = {'index': orm, 'strength': 1.0}
        if normal is not None:
            m['normalTexture'] = {'index': normal, 'scale': normal_scale}
        if emissive is not None:
            m['emissiveFactor'] = list(emissive)
        if alpha:
            m['alphaMode'] = alpha[0]
            if alpha[0] == 'MASK':
                m['alphaCutoff'] = alpha[1]
        if double:
            m['doubleSided'] = True
        ext = {}
        if sheen:
            ext['KHR_materials_sheen'] = {'sheenColorFactor': list(sheen[0]), 'sheenRoughnessFactor': sheen[1]}
        if clearcoat:
            ext['KHR_materials_clearcoat'] = {'clearcoatFactor': clearcoat[0], 'clearcoatRoughnessFactor': clearcoat[1]}
        for e in ext:
            if e not in self.doc['extensionsUsed']:
                self.doc['extensionsUsed'].append(e)
        if ext:
            m['extensions'] = ext
        if extras:
            m['extras'] = extras
        self.doc['materials'].append(m)
        return len(self.doc['materials']) - 1

    # -- cena -----------------------------------------------------------
    def node(self, **kw):
        self.doc['nodes'].append({k: v for k, v in kw.items() if v is not None})
        return len(self.doc['nodes']) - 1

    def skeleton(self, bones, heads):
        """Ossos com rotação de repouso identidade: só translações relativas ao pai."""
        index = {}
        for b in bones:
            local = heads[b.name] - (heads[b.parent] if b.parent else 0)
            index[b.name] = self.node(name=b.name, translation=[float(x) for x in local])
        for b in bones:
            if b.parent:
                self.doc['nodes'][index[b.parent]].setdefault('children', []).append(index[b.name])
        roots = [index[b.name] for b in bones if not b.parent]
        joints = [index[b.name] for b in bones]
        ibm = np.zeros((len(bones), 16), dtype=np.float32)
        for i, b in enumerate(bones):
            m = np.eye(4)
            m[:3, 3] = -heads[b.name]
            ibm[i] = m.T.reshape(-1)  # column-major
        skin = {'joints': joints, 'inverseBindMatrices': self.accessor(ibm), 'skeleton': roots[0], 'name': 'AvatarSkeleton'}
        self.doc['skins'].append(skin)
        return roots, len(self.doc['skins']) - 1

    def mesh(self, name, primitives, target_names=None, extras=None):
        m = {'name': name, 'primitives': primitives}
        ex = dict(extras or {})
        if target_names:
            ex['targetNames'] = list(target_names)
            m['weights'] = [0.0] * len(target_names)
        if ex:
            m['extras'] = ex
        self.doc['meshes'].append(m)
        return len(self.doc['meshes']) - 1

    def primitive(self, position, normal, uv, indices, material, joints=None, weights=None,
                  morphs=None, uv1=None, color=None):
        """morphs: lista [(delta_pos, delta_normal|None)] na ordem de target_names."""
        attrs = {'POSITION': self.accessor(position, minmax=True, target=34962),
                 'NORMAL': self.accessor(normal, target=34962)}
        if uv is not None:
            attrs['TEXCOORD_0'] = self.accessor(uv, target=34962)
        if uv1 is not None:
            attrs['TEXCOORD_1'] = self.accessor(uv1, target=34962)
        if color is not None:
            attrs['COLOR_0'] = self.accessor(color, target=34962)
        if joints is not None:
            attrs['JOINTS_0'] = self.accessor(joints, USHORT, target=34962)
            attrs['WEIGHTS_0'] = self.accessor(weights, target=34962)
        p = {'attributes': attrs, 'indices': self.accessor(np.asarray(indices).reshape(-1), UINT, target=34963), 'material': material}
        if morphs:
            p['targets'] = []
            for dp, dn in morphs:
                t = {'POSITION': self.sparse_accessor(dp)}
                if dn is not None:
                    t['NORMAL'] = self.sparse_accessor(dn)
                p['targets'].append(t)
        return p

    def save(self, path, extras=None):
        if extras:
            self.doc['scenes'][0]['extras'] = extras
        doc = {k: v for k, v in self.doc.items() if v != [] or k in ('scenes',)}
        self.doc['buffers'] = [{'byteLength': len(self.bin)}]
        doc['buffers'] = self.doc['buffers']
        js = json.dumps(doc, separators=(',', ':')).encode()
        js += b' ' * ((4 - len(js) % 4) % 4)
        while len(self.bin) % 4:
            self.bin.append(0)
        out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(self.bin))
        out += struct.pack('<II', len(js), 0x4E4F534A) + js
        out += struct.pack('<II', len(self.bin), 0x004E4942) + bytes(self.bin)
        with open(path, 'wb') as fh:
            fh.write(out)
        return len(out)
