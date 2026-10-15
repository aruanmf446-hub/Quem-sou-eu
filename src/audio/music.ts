import { assetUrl, MUSIC_TRACKS, SFX, type SfxId, type TrackId } from '../config/assets';

/**
 * Toca a música do R2 quando existe; se o arquivo não estiver configurado
 * ou falhar ao carregar, gera um chiptune simples com WebAudio.
 */
class AudioManager {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private el: HTMLAudioElement | null = null;
  private synthTimer: number | null = null;
  private current: TrackId | null = null;
  musicVolume = 0.5;
  sfxVolume = 0.7;

  private ensureCtx() {
    if (!this.ctx) {
      const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new Ctx();
      this.master = this.ctx.createGain();
      this.master.connect(this.ctx.destination);
    }
    if (this.ctx.state === 'suspended') void this.ctx.resume();
    return this.ctx;
  }

  setMusicVolume(v: number) {
    this.musicVolume = v;
    if (this.el) this.el.volume = v;
    if (this.master) this.master.gain.value = v * 0.25;
  }

  setSfxVolume(v: number) {
    this.sfxVolume = v;
  }

  play(track: TrackId) {
    if (this.current === track) return;
    this.stop();
    this.current = track;
    const url = assetUrl(MUSIC_TRACKS[track]);
    if (url) {
      const el = new Audio(url);
      el.loop = track !== 'victory';
      el.volume = this.musicVolume;
      el.onerror = () => {
        if (this.current === track && this.el === el) this.startSynth(track);
      };
      this.el = el;
      el.play().catch(() => {
        /* autoplay bloqueado: tenta de novo no próximo clique */
        const retry = () => {
          if (this.el === el) el.play().catch(() => this.startSynth(track));
          window.removeEventListener('pointerdown', retry);
        };
        window.addEventListener('pointerdown', retry);
      });
    } else {
      this.startSynth(track);
    }
  }

  stop() {
    this.current = null;
    if (this.el) {
      this.el.pause();
      this.el = null;
    }
    if (this.synthTimer !== null) {
      clearInterval(this.synthTimer);
      this.synthTimer = null;
    }
  }

  private startSynth(track: TrackId) {
    const ctx = this.ensureCtx();
    if (!this.master) return;
    this.master.gain.value = this.musicVolume * 0.25;
    const songs: Record<TrackId, { bpm: number; lead: number[]; bass: number[] }> = {
      menu: { bpm: 112, lead: [72, 76, 79, 76, 74, 77, 81, 77, 72, 76, 79, 84, 83, 79, 76, 74], bass: [48, 48, 53, 53, 45, 45, 55, 55] },
      match: { bpm: 128, lead: [69, 0, 72, 69, 76, 0, 74, 72, 69, 0, 72, 74, 71, 0, 67, 0], bass: [45, 45, 41, 41, 43, 43, 40, 40] },
      story: { bpm: 140, lead: [76, 76, 0, 76, 0, 72, 76, 0, 79, 0, 0, 0, 67, 0, 0, 0], bass: [48, 0, 55, 0, 52, 0, 55, 0] },
      victory: { bpm: 150, lead: [72, 76, 79, 84, 0, 79, 84, 84, 0, 0, 0, 0, 0, 0, 0, 0], bass: [48, 52, 55, 60, 0, 0, 0, 0] },
    };
    const song = songs[track];
    const stepMs = 60000 / song.bpm / 2;
    let step = 0;
    const tick = () => {
      if (track === 'victory' && step >= song.lead.length) return this.stop();
      const t = ctx.currentTime;
      const lead = song.lead[step % song.lead.length];
      const bass = song.bass[Math.floor(step / 2) % song.bass.length];
      if (lead) this.tone(lead, t, stepMs / 1000 * 0.9, 'square', 0.18);
      if (bass && step % 2 === 0) this.tone(bass, t, stepMs / 1000 * 1.8, 'triangle', 0.35);
      step++;
    };
    tick();
    this.synthTimer = window.setInterval(tick, stepMs);
  }

  private tone(midi: number, at: number, dur: number, type: OscillatorType, vol: number, dest?: AudioNode) {
    const ctx = this.ctx!;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.value = 440 * Math.pow(2, (midi - 69) / 12);
    gain.gain.setValueAtTime(vol, at);
    gain.gain.exponentialRampToValueAtTime(0.001, at + dur);
    osc.connect(gain).connect(dest ?? this.master!);
    osc.start(at);
    osc.stop(at + dur);
  }

  sfx(id: SfxId) {
    if (this.sfxVolume <= 0) return;
    const url = assetUrl(SFX[id]);
    if (url) {
      const a = new Audio(url);
      a.volume = this.sfxVolume;
      a.play().catch(() => undefined);
      return;
    }
    const ctx = this.ensureCtx();
    const out = ctx.createGain();
    out.gain.value = this.sfxVolume * 0.5;
    out.connect(ctx.destination);
    const t = ctx.currentTime;
    const seqs: Record<SfxId, [number, number][]> = {
      click: [[84, 0.05]],
      hit: [[76, 0.08], [84, 0.08], [91, 0.15]],
      miss: [[60, 0.12], [55, 0.2]],
      coin: [[88, 0.06], [95, 0.18]],
      jump: [[67, 0.05], [74, 0.08]],
    };
    let at = t;
    for (const [note, dur] of seqs[id]) {
      this.tone(note, at, dur, 'square', 0.3, out);
      at += dur;
    }
  }
}

export const audio = new AudioManager();
