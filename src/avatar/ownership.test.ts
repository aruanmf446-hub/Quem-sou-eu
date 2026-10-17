import { beforeEach, describe, expect, it, vi } from 'vitest';
vi.mock('../lib/supabase', () => ({ isOnlineAvailable: false, purchaseRemote: vi.fn(), awardCoinsRemote: vi.fn() }));
vi.mock('../audio/music', () => ({ audio: { sfx: vi.fn() } }));
import { buy } from '../lib/economy';
import { defaultProfile, getProfile, setProfile } from '../lib/profile';
import { BUNDLES } from './catalog';
import { cartFor, normalize, ownsItem, resolveConfig, toLook } from './ownership';

beforeEach(() => setProfile(defaultProfile()));

describe('posse, carrinho e equipamento', () => {
  it('perfil novo veste a Nova completa sem custo', () => {
    const p = getProfile();
    const config = resolveConfig(p.avatar);
    expect(config.items.top).toBe('top_track_jacket');
    expect(cartFor(p, config).total).toBe(0);
  });

  it('perfil antigo com o Camisa 10 comprado ganha todas as peças do pacote', () => {
    setProfile({ ownedCharacters: ['street', 'striker'], ownedDances: ['groove', 'samba'], avatar: { character: 'striker', dance: 'samba', color: '#efc51d', height: 1 } });
    const p = getProfile();
    const config = resolveConfig(p.avatar);
    expect(config.items.top).toBe('top_jersey_10');
    expect(config.dance).toBe('samba');
    expect(ownsItem(p, 'shoes_cleats_10')).toBe(true);
    expect(cartFor(p, config).total).toBe(0);
  });

  it('cobra só o que falta, uma vez, e equipa no formato aceito pelo banco', async () => {
    setProfile({ coins: 1000 });
    const draft = normalize({ ...resolveConfig(getProfile().avatar), items: { ...BUNDLES[0].config.items, top: 'top_jersey_away', eyewear: 'glasses_sport' }, dance: 'robot', celebration: 'flex' });
    const cart = cartFor(getProfile(), draft);
    expect(cart.items.map(i => i.id).sort()).toEqual(['glasses_sport', 'top_jersey_away']);
    expect(cart.motions.map(m => m.id).sort()).toEqual(['flex', 'robot']);
    expect(cart.total).toBe(150 + 90 + 150 + 100);
    for (const i of cart.items) await buy('item', i.id);
    for (const m of cart.motions) await buy('dance', m.id);
    await buy('item', 'glasses_sport');
    const p = getProfile();
    expect(p.coins).toBe(1000 - cart.total);
    expect(cartFor(p, draft).total).toBe(0);
    const look = toLook(p, draft, p.avatar);
    expect(look.character).toBe('street');
    expect(look.dance).toBe('robot');
    expect(look.celebration).toBe('flex');
    expect(look.height).toBe(1);
    expect(look.color).toMatch(/^#[0-9a-f]{6}$/i);
    setProfile({ avatar: look });
    expect(resolveConfig(getProfile().avatar).items.eyewear).toBe('glasses_sport');
  });

  it('oferece o personagem completo quando sai mais barato que as peças avulsas', async () => {
    setProfile({ coins: 400 });
    const draft = normalize(structuredClone(BUNDLES[1].config));
    const cart = cartFor(getProfile(), draft);
    expect(cart.bundles.map(b => b.id)).toEqual(['striker']);
    expect(cart.items).toEqual([]);
    expect(cart.total).toBe(150 + 100);
    await buy('character', 'striker');
    await buy('dance', 'samba');
    expect(cartFor(getProfile(), draft).total).toBe(0);
    expect(getProfile().coins).toBe(150);
  });

  it('não completa compra sem saldo e não muda o perfil', async () => {
    setProfile({ coins: 50 });
    const before = getProfile();
    await expect(buy('item', 'top_jersey_away')).rejects.toThrow('Moedas insuficientes');
    expect(getProfile().coins).toBe(before.coins);
    expect(getProfile().ownedItems).toEqual([]);
  });

  it('normaliza slots obrigatórios e itens no slot errado', () => {
    const c = normalize({ ...BUNDLES[1].config, items: { top: null, bottom: 'hair_afro', shoes: undefined as never } });
    expect(c.items.top).toBeTruthy();
    expect(c.items.bottom).not.toBe('hair_afro');
    expect(c.items.shoes).toBeTruthy();
  });
});
