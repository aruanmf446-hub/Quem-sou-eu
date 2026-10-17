export const CHARACTERS = [
  { id: 'street', name: 'Original', subtitle: 'Seu estilo começa aqui', price: 0, color: '#7857ff', skin: '#bd8058', hair: '#261b26', theme: 'street' },
  { id: 'striker', name: 'Camisa 10', subtitle: 'Talento de sobra, dentro e fora do campo', price: 150, color: '#f7cf35', skin: '#b9784e', hair: '#e2bc6c', theme: 'football' },
  { id: 'night-clown', name: 'Riso da Meia-Noite', subtitle: 'Um espetáculo de arrepiar', price: 250, color: '#dce0ec', skin: '#eff0f6', hair: '#ed501f', theme: 'clown' },
] as const;
export const DANCES = [
  { id: 'groove', name: 'No embalo', subtitle: 'Um groove para qualquer ocasião', price: 0 },
  { id: 'samba', name: 'Passinho do craque', subtitle: 'Leve o ritmo para o campo', price: 100 },
  { id: 'robot', name: 'Curto-circuito', subtitle: 'Precisão em cada movimento', price: 150 },
  { id: 'thriller', name: 'Baile da meia-noite', subtitle: 'A pista também tem seus monstros', price: 200 },
] as const;
export type CharacterId = typeof CHARACTERS[number]['id'];
export type DanceId = typeof DANCES[number]['id'];
export interface AvatarLook { character: CharacterId; dance: DanceId; color: string; height: number; }
export const DEFAULT_LOOK: AvatarLook = { character: 'street', dance: 'groove', color: '#7857ff', height: 1 };
