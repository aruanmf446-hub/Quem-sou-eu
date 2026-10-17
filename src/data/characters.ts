import type { AvatarConfig } from '../avatar/config';
import { MOTIONS } from '../avatar/catalog';

/** Personagens originais (IDs e preços legados). Cada um é um pacote completo de visual no Estúdio 3D. */
export const CHARACTERS = [
  { id: 'street', name: 'Nova', subtitle: 'Seu estilo começa aqui', price: 0, color: '#8463df' },
  { id: 'striker', name: 'Camisa 10', subtitle: 'Talento de sobra, dentro e fora do campo', price: 150, color: '#efc51d' },
  { id: 'night-clown', name: 'Riso da Meia-Noite', subtitle: 'Um espetáculo de arrepiar', price: 250, color: '#c2b9a4' },
] as const;
/** Danças e comemorações compartilham a posse (owned_dances) e os preços do servidor. */
export const DANCES = MOTIONS.map(m => ({ id: m.id, name: m.name, subtitle: m.subtitle, price: m.price }));
export type CharacterId = typeof CHARACTERS[number]['id'];
export type DanceId = string;
/**
 * Visual equipado. `character`, `dance`, `color` e `height` mantêm o formato antigo
 * (validado pelo banco). `creator` guarda o avatar completo criado no estúdio.
 */
export interface AvatarLook { character: CharacterId; dance: DanceId; color: string; height: number; celebration?: string; creator?: AvatarConfig; }
export const DEFAULT_LOOK: AvatarLook = { character: 'street', dance: 'groove', color: '#8463df', height: 1 };
