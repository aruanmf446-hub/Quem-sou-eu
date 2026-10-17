"""Copia do MPFB2 (assets CC0) apenas os arquivos que o avatar usa.

Uso: python3 scripts/avatar/vendor.py /caminho/para/mpfb2/src/mpfb/data
Os arquivos ficam versionados em scripts/avatar/data, então builds futuros não
precisam de rede.
"""
import os
import shutil
import sys

from spec import required_targets

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data')


def main(src):
    os.makedirs(OUT, exist_ok=True)
    copies = {
        '3dobjs/base.obj': 'base.obj',
        'rigs/standard/rig.mixamo.json': 'rig.mixamo.json',
        'rigs/standard/weights.mixamo.json': 'weights.mixamo.json',
    }
    for mask in ('face', 'lips', 'fingernails', 'toenails', 'eyelids', 'ears', 'inside-mouth', 'aureolae'):
        copies[f'textures/mpfb_{mask}.jpg'] = f'masks/{mask}.jpg'
    for name in required_targets():
        copies[f'targets/{name}.target.gz'] = f'targets/{name}.target.gz'
    missing = []
    for a, b in copies.items():
        source = os.path.join(src, a)
        if not os.path.exists(source):
            missing.append(a)
            continue
        os.makedirs(os.path.dirname(os.path.join(OUT, b)), exist_ok=True)
        shutil.copyfile(source, os.path.join(OUT, b))
    print(f'{len(copies) - len(missing)} arquivos copiados')
    if missing:
        print('Ausentes:', *missing, sep='\n  ')


if __name__ == '__main__':
    main(sys.argv[1])
