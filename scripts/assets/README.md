# Anatomical source assets

The base mesh, young male/athletic morphs and skin weights are from [MakeHuman](https://github.com/makehumancommunity/makehuman), fetched on 2026-10-17. These assets are explicitly released under **CC0 1.0**; the license is included as `CC0-1.0.txt`. The OBJ and target files retain their upstream release notices. The weight JSON also declares CC0.

Upstream paths:

- `makehuman/data/3dobjs/base.obj` → `human-base.obj`
- `makehuman/data/targets/macrodetails/caucasian-male-young.target` → `male-young.target`
- `makehuman/data/targets/macrodetails/universal-male-young-maxmuscle-averageweight.target` → `athletic.target`
- `makehuman/data/rigs/default_weights.mhw` → `body-weights.json`

The application uses the derived, compressed GLB assets in `public/models/`. Outfit designs, hairstyle geometry, face paint, materials, skeleton remapping and choreography are authored for this project. No proprietary game character or celebrity model is included.

To regenerate, install Blender 4.3+ and Python Pillow, run `npm ci`, then `npm run assets:build`. Rendering intermediates go in `work/`; GLB and WebP deliverables go in `public/`. Regular application builds do not require Blender or Python.
