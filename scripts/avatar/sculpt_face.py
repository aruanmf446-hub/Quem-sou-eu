"""Escultura procedural de rosto cartoon cinematográfico.

A deformação é um delta do morph compartilhado "style_toon"; nenhuma junta,
ordem de vértice, pose, forma de guardar o perfil ou nome de morph é modificado.
Todos os overlays e acessórios recebem o mesmo alvo via transferência baricêntrica.

Referências: animação 3D estilizada, volumes limpos, olhos grandes e mandíbula
curta. Não tenta reconstruir fotogrametria de uma fotografia 2D.
"""
from __future__ import annotations

import numpy as np


def smooth(a, b, x):
    t = np.clip((x - a) / max(b - a, 1e-8), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def gaussian(x, cx, rx, y, cy, ry, z=None, cz=None, rz=None):
    q = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
    if z is not None:
        q += ((z - cz) / rz) ** 2
    return np.exp(-1.4 * q)


def cinematic_delta(model):
    """Retorna delta (N,3) sem deformações descontínuas ao redor do pescoço.

    Medidas são proporcionais à distância interpupilar da própria malha:
    funciona nas variantes base, feminina e infantil via morphs preexistentes.
    Inclui helpers dos olhos e dentes, para não descolar globos e pálpebras.
    """
    P = model.coords
    eye_l = model.mesh.joint('helper-l-eye', P)
    eye_r = model.mesh.joint('helper-r-eye', P)
    ey = .5 * (eye_l[1] + eye_r[1])
    ez = .5 * (eye_l[2] + eye_r[2])
    ex = max(abs(eye_l[0] - eye_r[0]) * .5, .028)
    unit = ex / .038
    x, y, z = P.T
    d = np.zeros_like(P, dtype=np.float64)

    # Junta as áreas, mas suaviza para zero antes da cervical. Isto mantém
    # todas as peças com os mesmos pesos e reduz degraus na nuca.
    head = smooth(ey - .235 * unit, ey - .153 * unit, y)
    head *= 1 - smooth(ey + .242 * unit, ey + .315 * unit, y)
    upper = smooth(ey - .055 * unit, ey + .055 * unit, y)
    front = smooth(ez - .072 * unit, ez + .022 * unit, z)
    skin = np.zeros(len(P), dtype=np.float64)
    skin[model.mesh.group_vertices('body')] = 1.
    face = head * front * skin

    # 1. Silhueta: crânio largo/arredondado, testa suavemente projetada.
    #    O topo permanece alto; o terço inferior é comprimido em torno dos olhos.
    skull = head * upper
    d[:, 0] += x * (.14 * skull)
    d[:, 2] += (z - (ez - .075 * unit)) * (.085 * skull)
    lower = head * (1 - smooth(ey - .018 * unit, ey + .023 * unit, y))
    d[:, 1] += np.maximum(ey - y, 0.) * .22 * lower

    # 2. Órbitas: abertura maior e ligeiramente mais oval; inclui os próprios
    #    helpers do globo, logo os alvos do olho acompanham a pele.
    for side in (-1., 1.):
        cx = side * ex
        orbital = gaussian(x, cx, .059 * unit, y, ey, .050 * unit,
                           z, ez, .105 * unit) * head
        d[:, 0] += (x - cx) * .23 * orbital
        d[:, 1] += (y - ey) * .31 * orbital

        # Arcada e pálpebras são saliências em geometria, não maquiagem plana.
        arc = gaussian(x, side * ex * .99, .050 * unit,
                       y, ey + .033 * unit, .024 * unit)
        lid_up = gaussian(x, cx, .050 * unit, y, ey + .015 * unit, .012 * unit)
        lid_low = gaussian(x, cx, .048 * unit, y, ey - .019 * unit, .013 * unit)
        d[:, 2] += face * unit * (.0085 * arc + .0050 * lid_up + .0030 * lid_low)

        # Maçãs do rosto: massas arredondadas sob as órbitas.
        apple = gaussian(x, side * ex * 1.04, .055 * unit,
                         y, ey - .058 * unit, .054 * unit,
                         z, ez + .012 * unit, .095 * unit)
        d[:, 2] += .018 * unit * apple * face
        d[:, 0] += side * .0045 * unit * apple * face

    # 3. Mandíbula curta, menos pontiaguda; transição suave para o pescoço.
    jaw = gaussian(x, 0., .135 * unit, y, ey - .135 * unit,
                   .066 * unit) * face
    d[:, 0] -= x * .105 * jaw
    d[:, 2] += .005 * unit * jaw

    # 4. Ponte e ponta do nariz simplificadas, sem eliminar o seu perfil.
    nose = gaussian(x, 0., .037 * unit, y, ey - .044 * unit,
                    .063 * unit) * face
    d[:, 0] -= x * .11 * nose
    d[:, 2] -= .0040 * unit * nose
    # 5. Lábios volumétricos e cantos controlados: expressão é animação, não
    #    uma abertura forçada permanente na malha.
    lip = gaussian(x, 0., .043 * unit, y, ey - .079 * unit,
                   .019 * unit) * face
    d[:, 2] += .004 * unit * lip

    if not np.all(np.isfinite(d)):
        raise ValueError('Escultura facial inválida')
    return d.astype(np.float32)
