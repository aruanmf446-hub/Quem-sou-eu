import { beforeEach, describe, expect, it, vi } from 'vitest';
vi.mock('./supabase', () => ({ isOnlineAvailable: false, purchaseRemote: vi.fn(), awardCoinsRemote: vi.fn() }));
vi.mock('../audio/music', () => ({ audio: { sfx: vi.fn() } }));
import { buy, priceOf } from './economy';
import { defaultProfile, getProfile, setProfile } from './profile';

beforeEach(() => setProfile(defaultProfile()));
describe('catálogo 3D e compras', () => {
  it('compra e mantém posse sem cobrar novamente', async () => {
    await buy('character', 'striker');
    await buy('character', 'striker');
    expect(getProfile().coins).toBe(50);
    expect(getProfile().ownedCharacters).toEqual(['street', 'striker']);
  });
  it('não gasta o mesmo saldo em compras simultâneas', async () => {
    const results = await Promise.allSettled([buy('character', 'striker'), buy('dance', 'samba')]);
    expect(results.map(r => r.status)).toEqual(['fulfilled', 'rejected']);
    expect(getProfile().coins).toBe(50);
    expect(getProfile().ownedDances).toEqual(['groove']);
  });
  it('rejeita itens inexistentes e saldo insuficiente sem mudar o perfil', async () => {
    await expect(buy('dance', 'inventada')).rejects.toThrow('Item inexistente');
    await expect(buy('character', 'night-clown')).rejects.toThrow('Moedas insuficientes');
    expect(getProfile().coins).toBe(200);
    expect(priceOf('dance', 'samba')).toBe(100);
  });
});
