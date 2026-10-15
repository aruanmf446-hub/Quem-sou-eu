import { Crewmate } from '../components/Crewmate';
import { audio } from '../audio/music';
import { useProfile } from '../lib/profile';

export function Splash({ onStart }: { onStart: () => void }) {
  const profile = useProfile();
  return (
    <div
      className="splash"
      onClick={() => {
        audio.sfx('click');
        onStart();
      }}
    >
      <div className="splash-stars" />
      <h1 className="logo">
        QUEM<span>SOU</span>EU?
      </h1>
      <div className="splash-crew">
        <Crewmate skin={{ body: '#2f6fe4', visor: '#9fe7ff', hat: 'none' }} size={70} className="float d1" />
        <Crewmate skin={profile.skin} size={110} className="float" />
        <Crewmate skin={{ body: '#2bb673', visor: '#9fe7ff', hat: 'festa' }} size={70} className="float d2" />
      </div>
      <p className="blink">TOQUE PARA COMEÇAR</p>
    </div>
  );
}
