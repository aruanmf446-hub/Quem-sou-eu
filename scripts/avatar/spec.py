"""Morphs compartilhados por corpo, roupas, cabelos e acessórios.

Cada morph exportado tem o mesmo nome em todos os GLBs. O runtime aplica a mesma
influência em todas as peças, e as peças acompanham o corpo automaticamente.
"""

# Corpo-base: adulto jovem, masculino, proporções levemente heroicas.
BASE = dict(gender=1.0, muscle=.8, weight=.5, height=.55, proportions=.75, ethnic=(.42, .12, .46))

# Ajustes atléticos aplicados ao corpo-base masculino (o morph feminino os remove).
ATHLETIC = [
    ('torso/torso-vshape-incr', .45), ('torso/measure-shoulder-dist-incr', .2),
    ('torso/torso-muscle-pectoral-incr', .35), ('torso/torso-muscle-dorsi-incr', .45),
    ('neck/measure-neck-circ-incr', .35), ('stomach/stomach-tone-incr', .5),
    ('arms/l-upperarm-shoulder-muscle-incr', .25), ('arms/r-upperarm-shoulder-muscle-incr', .25),
    ('arms/l-upperarm-muscle-incr', .35), ('arms/r-upperarm-muscle-incr', .35),
    ('legs/l-lowerleg-muscle-incr', .35), ('legs/r-lowerleg-muscle-incr', .35),
    ('legs/l-upperleg-muscle-incr', .5), ('legs/r-upperleg-muscle-incr', .5),
    ('chin/chin-bones-incr', .25),
]

# Ajustes de rosto da base (mantidos também no corpo feminino): mais jovem e expressivo.
FACE_BASE = [
    ('head/head-age-decr', .45), ('mouth/mouth-upperlip-volume-decr', .7), ('mouth/mouth-lowerlip-volume-decr', .6),
    ('mouth/mouth-scale-horiz-decr', .2), ('nose/nose-scale-horiz-decr', .35), ('nose/nose-point-width-decr', .35),
    ('nose/nose-width2-decr', .3), ('nose/nose-nostrils-width-decr', .4),
    ('cheek/l-cheek-bones-incr', .5), ('cheek/r-cheek-bones-incr', .5), ('cheek/l-cheek-volume-decr', .4), ('cheek/r-cheek-volume-decr', .4), ('mouth/mouth-trans-backward', .6), ('mouth/mouth-scale-depth-decr', .45), ('mouth/mouth-philtrum-volume-decr', .4),
    ('nose/nose-volume-decr', .3), ('nose/nose-scale-depth-decr', .15),
    ('nose/nose-hump-decr', .3), ('nose/nose-point-up', .15), ('head/head-square', .25), ('chin/chin-width-decr', .15),
    ('chin/chin-prominent-incr', .3), ('chin/chin-height-incr', .3), ('head/head-scale-horiz-decr', .28), ('forehead/forehead-temple-decr', .3),
    ('eyes/l-eye-scale-incr', .4), ('eyes/r-eye-scale-incr', .4), ('eyes/l-eye-height2-incr', .4), ('eyes/r-eye-height2-incr', .4),
]

# Morphs de silhueta calculados pelos macro-modificadores (gênero x eixo).
# nome -> (função de construção, descrição)
MACRO_MORPHS = {
    'body_feminine': dict(gender=0.0),
    'muscle_up_m': dict(muscle=1.0), 'muscle_down_m': dict(muscle=.15),
    'muscle_up_f': dict(gender=0.0, muscle=1.0), 'muscle_down_f': dict(gender=0.0, muscle=.15),
    'weight_up_m': dict(weight=1.0), 'weight_down_m': dict(weight=.1),
    'weight_up_f': dict(gender=0.0, weight=1.0), 'weight_down_f': dict(gender=0.0, weight=.1),
    'height_up_m': dict(height=.8), 'height_down_m': dict(height=.25),
    'height_up_f': dict(gender=0.0, height=.8), 'height_down_f': dict(gender=0.0, height=.25),
    # Corpo infantil (macro "child" do MakeHuman, ~11 anos): baixo, cabeça proporcionalmente maior, membros curtos.
    'body_child_m': dict(age=0.0), 'body_child_f': dict(gender=0.0, age=0.0),
}

# Morphs locais: nome -> lista de (target, peso). Alvos l-/r- somados para simetria.
def both(name, w=1.0):
    return [(name.replace('{s}', 'l'), w), (name.replace('{s}', 'r'), w)]

TARGET_MORPHS = {
    # Corpo
    'shoulders_wide': [('torso/measure-shoulder-dist-incr', 1)],
    'shoulders_narrow': [('torso/measure-shoulder-dist-decr', 1)],
    'torso_v': [('torso/torso-vshape-incr', 1)],
    'torso_straight': [('torso/torso-vshape-decr', 1)],
    'legs_long': [('legs/upperlegs-height-incr', .6), ('legs/lowerlegs-height-incr', .6)],
    'legs_short': [('legs/upperlegs-height-decr', .6), ('legs/lowerlegs-height-decr', .6)],
    'head_big': [('head/head-scale-vert-incr', .55), ('head/head-scale-horiz-incr', .55), ('head/head-scale-depth-incr', .55)],
    'head_small': [('head/head-scale-vert-decr', .55), ('head/head-scale-horiz-decr', .55), ('head/head-scale-depth-decr', .55)],
    'belly_round': [('stomach/stomach-pregnant-incr', .5), ('stomach/stomach-tone-decr', .6)],
    'belly_flat': [('stomach/stomach-pregnant-decr', .6), ('stomach/stomach-tone-incr', .4)],
    'hips_wide': [('hip/hip-scale-horiz-incr', 1)],
    'hips_narrow': [('hip/hip-scale-horiz-decr', 1)],
    # Rosto
    'face_oval': [('head/head-oval', 1)],
    'face_round': [('head/head-round', 1)],
    'face_square': [('head/head-square', 1)],
    'face_triangle': [('head/head-invertedtriangular', 1)],
    'face_wide': [('head/head-scale-horiz-incr', .7)],
    'face_narrow': [('head/head-scale-horiz-decr', .7)],
    'jaw_strong': [('chin/chin-bones-incr', 1), ('chin/chin-width-incr', .5)],
    'jaw_soft': [('chin/chin-bones-decr', 1), ('chin/chin-width-decr', .5)],
    'chin_forward': [('chin/chin-prominent-incr', 1)],
    'chin_back': [('chin/chin-prominent-decr', 1)],
    'cheekbones_high': both('cheek/{s}-cheek-bones-incr'),
    'cheekbones_low': both('cheek/{s}-cheek-bones-decr'),
    'eyes_big': both('eyes/{s}-eye-scale-incr'),
    'eyes_small': both('eyes/{s}-eye-scale-decr'),
    'eyes_apart': both('eyes/{s}-eye-trans-out'),
    'eyes_close': both('eyes/{s}-eye-trans-in'),
    'eyes_up': both('eyes/{s}-eye-corner1-up', .6) + both('eyes/{s}-eye-corner2-up', .6),
    'eyes_down': both('eyes/{s}-eye-corner1-down', .6) + both('eyes/{s}-eye-corner2-down', .6),
    'nose_wide': [('nose/nose-scale-horiz-incr', .7), ('nose/nose-nostrils-width-incr', .7)],
    'nose_narrow': [('nose/nose-scale-horiz-decr', .7), ('nose/nose-nostrils-width-decr', .7)],
    'nose_long': [('nose/nose-scale-vert-incr', 1)],
    'nose_short': [('nose/nose-scale-vert-decr', 1)],
    'nose_tip_up': [('nose/nose-point-up', 1)],
    'nose_tip_down': [('nose/nose-point-down', 1)],
    'lips_full': [('mouth/mouth-upperlip-volume-incr', 1), ('mouth/mouth-lowerlip-volume-incr', 1)],
    'lips_thin': [('mouth/mouth-upperlip-volume-decr', 1), ('mouth/mouth-lowerlip-volume-decr', 1)],
    'mouth_wide': [('mouth/mouth-scale-horiz-incr', 1)],
    'mouth_narrow': [('mouth/mouth-scale-horiz-decr', 1)],
    'brows_high': [('eyebrows/eyebrows-trans-up', 1)],
    'brows_low': [('eyebrows/eyebrows-trans-down', 1)],
    'brows_angle_up': [('eyebrows/eyebrows-angle-up', 1)],
    'brows_angle_down': [('eyebrows/eyebrows-angle-down', 1)],
    'ears_big': both('ears/{s}-ear-scale-incr'),
    'ears_small': both('ears/{s}-ear-scale-decr'),
    'ears_pointed': both('ears/{s}-ear-shape-pointed'),
    # Traços de personagem (distinguem rostos além do formato básico).
    'cheeks_full': both('cheek/{s}-cheek-volume-incr') + both('cheek/{s}-cheek-inner-incr', .6) + [('head/head-fat-incr', .5)],
    'cheeks_hollow': both('cheek/{s}-cheek-volume-decr') + both('cheek/{s}-cheek-inner-decr', .6) + [('head/head-fat-decr', .4)],
    'eyes_round': both('eyes/{s}-eye-height1-incr') + both('eyes/{s}-eye-height2-incr', .8) + both('eyes/{s}-eye-height3-incr'),
    'eyes_almond': both('eyes/{s}-eye-height1-decr') + both('eyes/{s}-eye-height3-decr') + both('eyes/{s}-eye-corner2-up', .5) + both('eyes/{s}-eye-epicanthus-out', .4),
    'face_young': [('head/head-age-decr', 1), ('mouth/mouth-laugh-lines-out', .4)],
    'face_mature': [('head/head-age-incr', 1), ('mouth/mouth-laugh-lines-in', .7), ('chin/chin-cleft-incr', .3)],
    'nose_aquiline': [('nose/nose-hump-incr', 1), ('nose/nose-curve-convex', .8), ('nose/nose-greek-incr', .5)],
    'nose_button': [('nose/nose-curve-concave', 1), ('nose/nose-volume-decr', .4), ('nose/nose-point-width-incr', .5)],
    'mouth_corners_up': [('mouth/mouth-angles-up', 1), ('mouth/mouth-dimples-in', .4)],
    'mouth_corners_down': [('mouth/mouth-angles-down', 1)],
    'face_long': [('head/head-scale-vert-incr', .6), ('chin/chin-height-incr', .6), ('forehead/forehead-scale-vert-incr', .3)],
    'face_short': [('head/head-scale-vert-decr', .5), ('chin/chin-height-decr', .6)],
    # Estilo de animação: cabeça e olhos maiores, nariz e boca menores, pescoço fino.
    'style_toon': [('head/head-scale-vert-incr', .9), ('head/head-scale-horiz-incr', 1.0), ('head/head-scale-depth-incr', .8),
                   ('eyes/l-eye-scale-incr', 2.0), ('eyes/r-eye-scale-incr', 2.0), ('eyes/l-eye-height2-incr', .3), ('eyes/r-eye-height2-incr', .3),
                   ('nose/nose-scale-horiz-decr', .7), ('nose/nose-scale-vert-decr', .7), ('nose/nose-scale-depth-decr', .6), ('nose/nose-point-up', .5),
                   ('mouth/mouth-scale-horiz-decr', .35), ('mouth/mouth-scale-vert-decr', .3), ('mouth/mouth-upperlip-volume-decr', .3),
                   ('chin/chin-height-decr', .5), ('chin/chin-width-decr', .4), ('chin/chin-prominent-decr', .3),
                   ('cheek/l-cheek-volume-incr', .45), ('cheek/r-cheek-volume-incr', .45), ('head/head-oval', .35), ('cheek/l-cheek-bones-decr', .4), ('cheek/r-cheek-bones-decr', .4),
                   ('forehead/forehead-scale-vert-incr', .4), ('neck/measure-neck-circ-decr', .5),
                   ('hands/l-hand-scale-incr', .5), ('hands/r-hand-scale-incr', .5)],
}

# Expressões faciais: as unidades existem por grupo étnico; usamos a média, igual à base.
EXPRESSIONS = {
    'expr_blink_l': ['eye-left-closure'],
    'expr_blink_r': ['eye-right-closure'],
    'expr_smile': ['mouth-corner-puller'],
    'expr_squint': ['eye-left-slit', 'eye-right-slit'],
    'expr_brows_up': ['eyebrows-left-up', 'eyebrows-right-up'],
    'expr_brows_down': ['eyebrows-left-down', 'eyebrows-right-down'],
    'expr_mouth_open': ['mouth-open'],
    'expr_pucker': ['mouth-pursing'],
    'expr_grin': ['mouth-upward-retraction'],
}

ETHNIC = ('african', 'asian', 'caucasian')


def required_targets():
    names = set()
    for spec in TARGET_MORPHS.values():
        names.update(t for t, _ in spec)
    names.update(t for t, _ in ATHLETIC)
    names.update(t for t, _ in FACE_BASE)
    for units in EXPRESSIONS.values():
        for u in units:
            for e in ETHNIC:
                names.add(f'expression/units/{e}/{u}')
    for e in ETHNIC:
        for s in ('male', 'female'):
            for a in ('young', 'child'):
                names.add(f'macrodetails/{e}-{s}-{a}')
    for s in ('male', 'female'):
        for a in ('young', 'child'):
            for m in ('minmuscle', 'averagemuscle', 'maxmuscle'):
                for w in ('minweight', 'averageweight', 'maxweight'):
                    names.add(f'macrodetails/universal-{s}-{a}-{m}-{w}')
                    for h in ('maxheight', 'minheight'):
                        names.add(f'macrodetails/height/{s}-{a}-{m}-{w}-{h}')
                    for p in ('idealproportions', 'uncommonproportions'):
                        names.add(f'macrodetails/proportions/{s}-{a}-{m}-{w}-{p}')
    return sorted(names)
