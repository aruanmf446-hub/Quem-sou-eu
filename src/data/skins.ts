export interface ColorItem {
  id: string;
  name: string;
  color: string;
  price: number;
}

export interface HatItem {
  id: string;
  name: string;
  price: number;
  rarity: 'comum' | 'raro' | 'épico' | 'lendário';
}

export const SKIN_COLORS: ColorItem[] = [
  { id: 'vermelho', name: 'Vermelho', color: '#e8384f', price: 0 },
  { id: 'azul', name: 'Azul', color: '#2f6fe4', price: 0 },
  { id: 'verde', name: 'Verde', color: '#2bb673', price: 0 },
  { id: 'amarelo', name: 'Amarelo', color: '#f5c518', price: 0 },
  { id: 'rosa', name: 'Rosa', color: '#f26bb5', price: 100 },
  { id: 'laranja', name: 'Laranja', color: '#f5841f', price: 100 },
  { id: 'roxo', name: 'Roxo', color: '#7e4fd8', price: 150 },
  { id: 'ciano', name: 'Ciano', color: '#2ad4d4', price: 150 },
  { id: 'preto', name: 'Preto', color: '#30343b', price: 250 },
  { id: 'branco', name: 'Branco', color: '#e9edf2', price: 250 },
  { id: 'dourado', name: 'Dourado', color: '#d4a017', price: 800 },
  { id: 'galaxia', name: 'Galáxia', color: '#3a1c71', price: 1200 },
];

export const HATS: HatItem[] = [
  { id: 'bone', name: 'Boné', price: 150, rarity: 'comum' },
  { id: 'festa', name: 'Chapéu de festa', price: 200, rarity: 'comum' },
  { id: 'cartola', name: 'Cartola', price: 400, rarity: 'raro' },
  { id: 'chifres', name: 'Chifrinhos', price: 450, rarity: 'raro' },
  { id: 'planta', name: 'Plantinha', price: 500, rarity: 'raro' },
  { id: 'coroa', name: 'Coroa', price: 1000, rarity: 'épico' },
  { id: 'aureola', name: 'Auréola', price: 1500, rarity: 'lendário' },
];

export const VISORS: ColorItem[] = [
  { id: 'gelo', name: 'Gelo', color: '#9fe7ff', price: 0 },
  { id: 'menta', name: 'Menta', color: '#a8ffcf', price: 120 },
  { id: 'lava', name: 'Lava', color: '#ffb36b', price: 120 },
  { id: 'neon', name: 'Neon', color: '#ff7cf2', price: 300 },
];

export const RARITY_COLORS: Record<HatItem['rarity'], string> = {
  comum: '#6fbf4a',
  raro: '#3a8dde',
  épico: '#a74fe0',
  lendário: '#f0a020',
};
