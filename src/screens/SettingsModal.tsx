import { hasRemoteAssets } from '../config/assets';
import { setProfile, useProfile } from '../lib/profile';
import { isOnlineAvailable } from '../lib/supabase';

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const p = useProfile();
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Configurações</h2>
        <label className="slider">
          Música
          <input type="range" min={0} max={1} step={0.05} value={p.settings.music} onChange={(e) => setProfile({ settings: { ...p.settings, music: Number(e.target.value) } })} />
        </label>
        <label className="slider">
          Efeitos
          <input type="range" min={0} max={1} step={0.05} value={p.settings.sfx} onChange={(e) => setProfile({ settings: { ...p.settings, sfx: Number(e.target.value) } })} />
        </label>
        <ul className="status-list">
          <li>Online: {isOnlineAvailable ? (p.id.startsWith('local-') ? 'conectando...' : 'conectado ✓') : 'desativado'}</li>
          <li>Arte e músicas: {hasRemoteAssets ? 'Cloudflare R2 ✓' : 'placeholders'}</li>
        </ul>
        <button className="btn-primary" onClick={onClose}>
          Fechar
        </button>
      </div>
    </div>
  );
}
