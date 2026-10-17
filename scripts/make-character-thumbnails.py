"""Requires Pillow. Render PNG sources remain in work/, deliver WebP only."""
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parent.parent
out=root/'public'/'characters';out.mkdir(parents=True,exist_ok=True)
for identity in ['street','striker','night-clown']:
    image=Image.open(root/'work'/'renders'/f'{identity}.png')
    image.save(out/f'{identity}.webp','WEBP',quality=90,method=6)
