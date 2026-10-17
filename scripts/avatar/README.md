# Pipeline do avatar 3D

Gera, sem Blender e sem serviços externos, a base do avatar e todas as peças do guarda-roupa em `public/avatar/`.

```bash
pip install -r scripts/avatar/requirements.txt   # numpy, scipy, Pillow
npm run assets:build                              # base + peças + compressão Meshopt
npm run dev & npm run assets:thumbs               # miniaturas das peças e dos 8 personagens (bundle_<id>)
```

`npm run build` usa os arquivos já versionados; só é preciso rodar o pipeline ao mudar peças.

## Fontes e licenças

| Origem | O que usamos | Licença |
| --- | --- | --- |
| [MakeHuman](https://github.com/makehumancommunity/makehuman) / [MPFB2](https://github.com/makehumancommunity/mpfb2) — `data/` | malha-base `base.obj`, alvos de forma (corpo, rosto, expressões), esqueleto `mixamo` e pesos, máscaras de UV | **CC0 1.0** (`data/LICENSE-CC0.md`), uso comercial livre |

Somente os **dados** (assets) do MPFB2 foram copiados por `vendor.py`. Nenhum código GPL do MPFB foi incorporado: os leitores, o rig, o IK, a modelagem de roupas e as texturas são código original deste repositório.

Tudo o mais é original do projeto, gerado proceduralmente: texturas de pele, olhos, cílios, sobrancelhas, barbas, cabelos (cachos em hélice, casca volumétrica), roupas, calçados, acessórios, estampas, escudo e números. Não há fontes tipográficas, fotos, marcas reais nem modelos de terceiros embutidos.

## Arquitetura

- `mh.py`, `model.py`: corpo-base (adulto atlético) a partir dos macros do MakeHuman, 67 morphs nomeados (corpo, rosto, expressões), deltas das juntas por morph e pesos do rig Mixamo (52 ossos + olhos).
- `build_base.py`: `base.glb` com o corpo dividido em regiões ocultáveis (`chest`, `belly`, `thigh_a`…), olhos, cílios, dentes, roupa íntima neutra e o esqueleto.
- `items.py`: amarra qualquer geometria ao corpo (vértice de origem ou baricêntricas) e transfere pesos e morphs. Não há rig manual por peça nem por jogador.
- `garments.py`, `cloth.py`: roupas derivadas da anatomia (folga, alisamento, caimento, barras retas, golas/punhos, espessura) e texturas PBR por projeção triplanar.
- `overlays.py`, `hair.py`, `eyes.py`, `skin_textures.py`: pelos sobre a pele, cabelos com volume, olhos e pele.
- `wardrobe.py` (+ módulos de peças) e `build_items.py`: catálogo de peças. Cada ID precisa existir também em `src/avatar/catalog.ts`.
- `collection_*.py`: as cinco coleções estilizadas (Mecânica dos Céus, Astrônoma, Arlequina, Guardião Anúbis, Cientista Voltaico); `hair_styled.py`/`hair_styles.py`: cabelo em mechas esculpidas; `isosurface.py`: extração de superfície (surface nets, só numpy) para as formas modeladas por campos de distância do Anúbis.
- `optimize.mjs`: Meshopt + quantização. O runtime recupera a dequantização embutida nas matrizes inversas.
- `preview/`: ferramentas de validação visual (Playwright): `shoot.mjs`, `studio.mjs`, `e2e.mjs`.

Para criar uma peça nova: escreva a função em `wardrobe*.py`, registre o ID em `build_items.py`, adicione o item em `src/avatar/catalog.ts` (preço, slot, pacote) e na migração de preços do Supabase, rode `python3 scripts/avatar/build_items.py <id>`, `node scripts/avatar/optimize.mjs` e `npm run assets:thumbs`.
