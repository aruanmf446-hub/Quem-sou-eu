import type { AvatarConfig } from '../avatar/config';
import { BUNDLES, MOTIONS, type BundleId } from '../avatar/catalog';

/** Personagens (pacotes completos de visual). Os três primeiros mantêm IDs e preços legados. */
export const CHARACTERS = BUNDLES.map(b => ({ id: b.id, name: b.name, subtitle: b.subtitle, price: b.price, color: b.color }));
/** Danças e comemorações compartilham a posse (owned_dances) e os preços do servidor. */
export const DANCES = MOTIONS.map(m => ({ id: m.id, name: m.name, subtitle: m.subtitle, price: m.price }));
export type CharacterId = BundleId;
export type DanceId = string;
/**
 * Visual equipado. `character`, `dance`, `color` e `height` mantêm o formato antigo
 * (validado pelo banco). `creator` guarda o avatar completo criado no estúdio.
 */
export interface AvatarLook { character: CharacterId; dance: DanceId; color: string; height: number; celebration?: string; creator?: AvatarConfig; }
export const DEFAULT_LOOK: AvatarLook = { character: 'street', dance: 'groove', color: '#8463df', height: 1 };
