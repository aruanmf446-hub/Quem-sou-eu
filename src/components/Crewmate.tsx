import type { Skin } from '../game/types';

function shade(hex: string, amt: number) {
  const n = parseInt(hex.replace('#', ''), 16);
  const r = Math.max(0, Math.min(255, (n >> 16) + amt));
  const g = Math.max(0, Math.min(255, ((n >> 8) & 0xff) + amt));
  const b = Math.max(0, Math.min(255, (n & 0xff) + amt));
  return `rgb(${r},${g},${b})`;
}

export function Hat({ id }: { id: string }) {
  switch (id) {
    case 'bone':
      return (
        <g>
          <path d="M30 30 Q50 6 74 26 L74 32 L30 32 Z" fill="#2a59c9" stroke="#111" strokeWidth="3" />
          <path d="M66 30 L92 34 L66 36 Z" fill="#1d3f94" stroke="#111" strokeWidth="3" />
        </g>
      );
    case 'festa':
      return (
        <g>
          <path d="M40 30 L54 -6 L66 30 Z" fill="#ff5fa2" stroke="#111" strokeWidth="3" />
          <circle cx="54" cy="-6" r="5" fill="#ffe14d" stroke="#111" strokeWidth="2" />
          <path d="M45 18 L62 20 M48 8 L58 10" stroke="#ffe14d" strokeWidth="3" />
        </g>
      );
    case 'cartola':
      return (
        <g>
          <rect x="36" y="-4" width="34" height="30" fill="#222" stroke="#111" strokeWidth="3" />
          <rect x="28" y="24" width="50" height="7" rx="3" fill="#222" stroke="#111" strokeWidth="3" />
          <rect x="36" y="16" width="34" height="5" fill="#c0263d" />
        </g>
      );
    case 'chifres':
      return (
        <g fill="#e23b3b" stroke="#111" strokeWidth="3">
          <path d="M34 30 Q26 10 36 4 Q38 18 44 26 Z" />
          <path d="M72 30 Q80 10 70 4 Q68 18 62 26 Z" />
        </g>
      );
    case 'planta':
      return (
        <g stroke="#111" strokeWidth="3">
          <path d="M54 28 L54 8" fill="none" />
          <path d="M54 12 Q40 0 36 10 Q46 18 54 12 Z" fill="#43c463" />
          <path d="M54 8 Q66 -6 72 4 Q64 14 54 8 Z" fill="#43c463" />
        </g>
      );
    case 'coroa':
      return (
        <path d="M34 30 L36 6 L46 18 L54 2 L62 18 L72 6 L74 30 Z" fill="#ffd23a" stroke="#111" strokeWidth="3" />
      );
    case 'aureola':
      return <ellipse cx="54" cy="4" rx="22" ry="6" fill="none" stroke="#ffe46b" strokeWidth="5" />;
    default:
      return null;
  }
}

export function Crewmate({ skin, size = 80, dead = false, className }: { skin: Skin; size?: number; dead?: boolean; className?: string }) {
  const dark = shade(skin.body, -55);
  return (
    <svg className={className} width={size} height={size * 1.15} viewBox="0 -12 100 127" aria-hidden="true" style={{ opacity: dead ? 0.35 : 1 }}>
      {/* mochila */}
      <rect x="10" y="44" width="18" height="38" rx="8" fill={dark} stroke="#111" strokeWidth="4" />
      {/* corpo */}
      <path
        d="M28 40 Q28 18 54 18 Q82 18 82 44 L82 96 Q82 104 74 104 L66 104 Q60 104 60 96 L60 90 L48 90 L48 96 Q48 104 40 104 L34 104 Q28 104 28 96 Z"
        fill={skin.body}
        stroke="#111"
        strokeWidth="4"
      />
      <path d="M32 84 Q54 92 78 84 L78 92 Q54 98 32 92 Z" fill={dark} opacity="0.5" />
      {/* visor */}
      <rect x="48" y="32" width="42" height="24" rx="12" fill={skin.visor} stroke="#111" strokeWidth="4" />
      <rect x="58" y="36" width="20" height="6" rx="3" fill="#fff" opacity="0.8" />
      <g transform="translate(0,-10)">
        <Hat id={skin.hat} />
      </g>
      {dead && <path d="M50 30 L88 58 M88 30 L50 58" stroke="#111" strokeWidth="5" />}
    </svg>
  );
}
