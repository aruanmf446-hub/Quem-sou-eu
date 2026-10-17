# Camisa 10 — image-to-3D production brief

## Status

The reference is AI-generated **2D concept art**. No Meshy or Tripo generation has been submitted yet. Do not show this concept as a render of the current game asset.

The player connected Meshy and Tripo, but neither plugin's generation tools were exposed to the current execution. Continue with the native tools once available; inspect their input and cost contracts before submitting. Preserve task IDs and parameters here when results arrive. Never store credentials.

## Goal and input

Replace the current `striker` preset with a substantially better original stylized game character, preserving its catalog ID, ownership, price and saved profiles.

`reference-front.png` establishes the desired face, anatomy, hairstyle, outfit, colors and materials. Use the same input for both providers. The image shows one front-facing full-body football hero in A-pose, with separated fingers, yellow/green technical jersey, navy shorts, white/green socks and trainers, and original geometric/floral arm tattoos.

## Generation instruction

Create one complete high-quality textured 3D humanoid matching the reference image. Preserve face structure, medium-brown skin, curly fade haircut with blond tips, trimmed facial hair, hands with five separated fingers, athletic proportions, jersey fabric and stitching, garment folds, navy shorts, socks, detailed shoes and original arm tattoos. Maintain a symmetric neutral A-pose appropriate for rigging. Reconstruct sides and back coherently. No environment, floor, pedestal, football, camera, extra characters, text, watermark or additional props. Use physically based materials with neutral albedo, normal and roughness detail. Avoid baking strong lighting into textures.

## Quality and delivery

- One candidate per provider for direct comparison; no silent bulk generation or repeated paid retries.
- Prioritize face, silhouette, fingers, garment shape and coherent back geometry.
- Inspect a high-quality result before simplifying topology or textures.
- Initial web target: around 30k–60k triangles, 2K textures; adjust after visual/performance checks. Preserve the original high-quality output.
- Export GLB and FBX when supported; retain source results for Blender cleanup.

## Rig and animation

Auto-rig the chosen model. Inspect joint placement, weights and shoulders/hips/hands. Preserve the provider's skeleton and implement an explicit adapter in the app; do not assume compatibility with the current handmade 17-bone rig.

Use animation clips when available. Verify root motion, foot contact, elbows, wrists and knees. Check licensing for in-game sale/unlock of emotes. Do not describe procedural motion as motion capture.

## Before production

Render front, side, back and face close-up. Compare candidates with the reference. Inspect a neutral pose and full dance cycle for foot contact, self-intersection and materials. Keep the current production asset until a candidate materially improves appearance. Then optimize, update the thumbnail, test, commit to `main`, deploy and verify live URLs.
