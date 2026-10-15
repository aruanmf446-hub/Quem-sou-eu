import type { CharacterCard, Deck } from '../game/types';

function cards(prefix: string, list: [string, string][]): CharacterCard[] {
  return list.map(([name, emoji]) => ({
    id: `${prefix}-${name.toLowerCase().normalize('NFD').replace(/[^a-z0-9]+/g, '-')}`,
    name,
    emoji,
    image: `decks/${prefix}/${name.toLowerCase().normalize('NFD').replace(/[^a-z0-9]+/g, '-')}.png`,
  }));
}

export const OFFICIAL_DECKS: Deck[] = [
  {
    id: 'espaco',
    name: 'Tripulação Espacial',
    description: 'O deck clássico: a tripulação inteira da nave.',
    price: 0,
    official: true,
    cover: 'decks/espaco/cover.png',
    cards: cards('espaco', [
      ['Astronauta', '👩‍🚀'], ['Alien', '👽'], ['Robô', '🤖'], ['Capitão', '🧑‍✈️'], ['Mecânico', '🔧'],
      ['Cientista', '🧪'], ['Médica', '🩺'], ['Cozinheiro', '🍳'], ['Piloto', '🛸'], ['Navegadora', '🧭'],
      ['Engenheiro', '⚙️'], ['Hacker', '💻'], ['Fantasma', '👻'], ['Cometa', '☄️'], ['Lua', '🌙'],
      ['Satélite', '🛰️'], ['Foguete', '🚀'], ['Estrela', '⭐'], ['Planeta', '🪐'], ['Sol', '☀️'],
      ['Monstro', '👾'], ['Polvo Espacial', '🐙'], ['Cachorro Astronauta', '🐶'], ['Gato Lunar', '🐱'],
      ['Telescópio', '🔭'], ['Antena', '📡'], ['Bateria', '🔋'], ['Ímã', '🧲'], ['Cristal', '💎'], ['Buraco Negro', '🕳️'],
    ]),
  },
  {
    id: 'profissoes',
    name: 'Profissões',
    description: 'Quem sou eu? Do bombeiro ao pirata.',
    price: 0,
    official: true,
    cover: 'decks/profissoes/cover.png',
    cards: cards('profissoes', [
      ['Bombeiro', '🧑‍🚒'], ['Policial', '👮'], ['Médico', '🧑‍⚕️'], ['Chef', '🧑‍🍳'], ['Professor', '🧑‍🏫'],
      ['Fazendeiro', '🧑‍🌾'], ['Artista', '🧑‍🎨'], ['Cantora', '🎤'], ['Juiz', '🧑‍⚖️'], ['Detetive', '🕵️'],
      ['Ninja', '🥷'], ['Pirata', '🏴‍☠️'], ['Mágico', '🎩'], ['Palhaço', '🤡'], ['Carteiro', '📮'],
      ['Jogador', '⚽'], ['Dentista', '🦷'], ['Padeiro', '🥖'], ['Pescador', '🎣'], ['Mergulhador', '🤿'],
      ['Fotógrafo', '📷'], ['Construtor', '👷'], ['Cientista', '🔬'], ['DJ', '🎧'], ['Princesa', '👸'],
      ['Rei', '🤴'], ['Super-herói', '🦸'], ['Vilão', '🦹'], ['Mago', '🧙'], ['Vampiro', '🧛'],
    ]),
  },
  {
    id: 'folclore',
    name: 'Lendas do Brasil',
    description: 'Saci, Curupira, Boitatá e companhia. Deck premium.',
    price: 600,
    official: true,
    cover: 'decks/folclore/cover.png',
    cards: cards('folclore', [
      ['Saci', '🌪️'], ['Curupira', '👣'], ['Boitatá', '🐍'], ['Iara', '🧜‍♀️'], ['Mula sem Cabeça', '🐴'],
      ['Boto Cor-de-Rosa', '🐬'], ['Cuca', '🐊'], ['Lobisomem', '🐺'], ['Mapinguari', '🦍'], ['Caipora', '🐗'],
      ['Negrinho do Pastoreio', '🐎'], ['Corpo Seco', '💀'], ['Bicho-Papão', '👹'], ['Pisadeira', '🦶'],
      ['Mãe do Ouro', '🪙'], ['Vitória-Régia', '🪷'], ['Cobra Grande', '🐉'], ['Capelobo', '🐜'],
      ['Matinta Perera', '🦉'], ['Tutu Marambá', '🐻'], ['Labatut', '👁️'], ['Uirapuru', '🐦'],
      ['Ipupiara', '🌊'], ['Romãozinho', '🔥'], ['Anhangá', '🦌'], ['Alamoa', '🌫️'], ['Pai do Mato', '🌳'],
      ['Bradador', '📣'], ['Porca dos Sete Leitões', '🐖'], ['Cabeça de Cuia', '🥥'],
    ]),
  },
  {
    id: 'monstros',
    name: 'Monstros Fofos',
    description: 'Criaturas estranhas e adoráveis. Deck premium.',
    price: 400,
    official: true,
    cover: 'decks/monstros/cover.png',
    cards: cards('monstros', [
      ['Slime', '🟢'], ['Dragãozinho', '🐲'], ['Cogumelo', '🍄'], ['Abóbora', '🎃'], ['Múmia', '🧟'],
      ['Yeti', '❄️'], ['Ciclope', '👁️'], ['Gosma', '🫧'], ['Morcego', '🦇'], ['Aranha', '🕷️'],
      ['Caveira', '☠️'], ['Bruxa', '🧙‍♀️'], ['Diabinho', '😈'], ['Ogro', '👺'], ['Troll', '🧌'],
      ['Fada', '🧚'], ['Unicórnio', '🦄'], ['Kraken', '🦑'], ['T-Rex', '🦖'], ['Fênix', '🐦‍🔥'],
      ['Golem', '🪨'], ['Elfo', '🧝'], ['Gênio', '🧞'], ['Zumbi', '🧟‍♂️'], ['Robô Malvado', '🦾'],
      ['Nuvem Brava', '⛈️'], ['Planta Carnívora', '🌱'], ['Olho Voador', '🧿'], ['Sereia', '🧜'], ['Tubarão', '🦈'],
    ]),
  },
];

export const MIN_DECK_CARDS = 12;
export const MAX_DECK_CARDS = 60;
