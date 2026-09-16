/** kit/product.tsx — launch/product preset parts: device frames, cursor and taps, UI zoom, before/after, prompt bubbles, terminal, step rail. */
import React from 'react';
import {spring, useVideoConfig} from 'remotion';
import {EASE_IO, EASE_SOFT, SPRING, TABULAR, progress, ramp, rgba, useTheme} from './core';
import type {Rect} from './core';
import {useClock} from './clock';

type CSS = React.CSSProperties;

/** Phone / laptop / browser chrome around a screen box `r` (the screen area; chrome draws outside it). */
export const DeviceFrame: React.FC<{kind?: 'phone' | 'laptop' | 'browser'; r: Rect; url?: string; dark?: boolean; children: React.ReactNode}> = ({kind = 'phone', r, url, dark, children}) => {
  const {palette, fonts, preset} = useTheme(); const isDark = dark ?? preset === 'impact';
  const shell = isDark ? '#15181e' : '#e6e8ee'; const bezel = isDark ? '#0b0d11' : '#f8f9fb';
  if (kind === 'phone') {
    const pad = Math.round(r.w * 0.035); const radius = Math.round(r.w * 0.14);
    return (
      <>
        <div style={{position: 'absolute', left: r.x - pad, top: r.y - pad, width: r.w + pad * 2, height: r.h + pad * 2, borderRadius: radius, background: shell, boxShadow: `0 30px 80px ${rgba(palette.ink, 0.35)}, inset 0 0 0 2px ${rgba(palette.white, 0.06)}`}} />
        <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, borderRadius: radius - pad, overflow: 'hidden', background: bezel}}>{children}</div>
        <div style={{position: 'absolute', left: r.x + r.w / 2 - r.w * 0.16, top: r.y + pad * 0.9, width: r.w * 0.32, height: pad * 2.2, borderRadius: pad * 1.2, background: '#000'}} />
      </>
    );
  }
  if (kind === 'laptop') {
    const pad = Math.round(r.w * 0.02); const base = Math.round(r.h * 0.06);
    return (
      <>
        <div style={{position: 'absolute', left: r.x - pad, top: r.y - pad, width: r.w + pad * 2, height: r.h + pad * 2, borderRadius: 18, background: shell, boxShadow: `0 30px 80px ${rgba(palette.ink, 0.35)}`}} />
        <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, borderRadius: 8, overflow: 'hidden', background: bezel}}>{children}</div>
        <div style={{position: 'absolute', left: r.x - r.w * 0.08, top: r.y + r.h + pad, width: r.w * 1.16, height: base, borderRadius: `0 0 ${base}px ${base}px`, background: `linear-gradient(${shell}, ${rgba(shell, 0.7)})`}} />
      </>
    );
  }
  const bar = 54;
  return (
    <>
      <div style={{position: 'absolute', left: r.x, top: r.y - bar, width: r.w, height: r.h + bar, borderRadius: 16, background: shell, boxShadow: `0 30px 80px ${rgba(palette.ink, 0.28)}`, overflow: 'hidden'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 8, height: bar, padding: '0 18px'}}>
          {['#ff5f57', '#febc2e', '#28c840'].map((c) => <div key={c} style={{width: 14, height: 14, borderRadius: 7, background: c}} />)}
          {url ? <div style={{marginLeft: 16, flex: 1, height: 30, borderRadius: 8, background: isDark ? '#0f1216' : '#fff', color: isDark ? palette.muted : '#4b5563', fontFamily: fonts.body, fontSize: 18, lineHeight: '30px', paddingLeft: 12}}>{url}</div> : null}
        </div>
      </div>
      <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, overflow: 'hidden', background: bezel}}>{children}</div>
    </>
  );
};

/** Cursor moving through `path` (frames shot-local, eased between points); `clicks` add ripples. */
export const CursorTrail: React.FC<{path: Array<{x: number; y: number; at: number}>; clicks?: number[]; size?: number; color?: string}> = ({path, clicks = [], size = 36, color}) => {
  const {palette} = useTheme(); const frame = useClock(); const col = color ?? palette.ink;
  if (!path.length || frame < path[0].at) return null;
  let x = path[path.length - 1].x; let y = path[path.length - 1].y;
  for (let i = 0; i < path.length - 1; i++) {
    const a = path[i]; const b = path[i + 1];
    if (frame >= a.at && frame < b.at) { x = ramp(frame, a.at, b.at, a.x, b.x, EASE_IO); y = ramp(frame, a.at, b.at, a.y, b.y, EASE_IO); break; }
  }
  return (
    <>
      {clicks.map((c, i) => { const p = progress(frame, c, 14); return p > 0 && p < 1 ? <div key={i} style={{position: 'absolute', left: x - 30 * p, top: y - 30 * p, width: 60 * p, height: 60 * p, borderRadius: '50%', border: `3px solid ${palette.accent}`, opacity: 1 - p, pointerEvents: 'none'}} /> : null; })}
      <svg style={{position: 'absolute', left: x - 4, top: y - 2, overflow: 'visible', pointerEvents: 'none'}} width={size} height={size} viewBox="0 0 24 24">
        <path d="M4 2 L4 19 L8.5 15 L11.5 22 L14.5 20.8 L11.5 14 L17.5 14 Z" fill={col} stroke="#fff" strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
    </>
  );
};

/** Touch ripple at (x, y) starting at `at` (mobile demos). */
export const TapRipple: React.FC<{at: number; x: number; y: number; color?: string}> = ({at, x, y, color}) => {
  const {palette} = useTheme(); const frame = useClock(); const p = progress(frame, at, 16); const col = color ?? palette.accent;
  if (p <= 0 || p >= 1) return null;
  return <div style={{position: 'absolute', left: x - 40 * p, top: y - 40 * p, width: 80 * p, height: 80 * p, borderRadius: '50%', background: rgba(col, 0.35 * (1 - p)), border: `2px solid ${rgba(col, 1 - p)}`, pointerEvents: 'none'}} />;
};

/** Scales the children (a screen box `r`) about a target rect inside it, ease-in-out over `len` frames, starting at `at`. */
export const UIZoom: React.FC<{r: Rect; target: Rect; at: number; len?: number; scale?: number; hold?: number; back?: boolean; children: React.ReactNode}> = ({r, target, at, len = 18, scale = 1.8, hold = 60, back = true, children}) => {
  const frame = useClock();
  const inP = ramp(frame, at, at + len, 0, 1, EASE_IO); const outP = back ? ramp(frame, at + len + hold, at + len * 2 + hold, 1, 0, EASE_IO) : 1;
  const k = 1 + (scale - 1) * inP * outP;
  const ox = target.x + target.w / 2 - r.x; const oy = target.y + target.h / 2 - r.y;
  return <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, overflow: 'hidden'}}><div style={{position: 'absolute', inset: 0, transform: `scale(${k.toFixed(4)})`, transformOrigin: `${ox}px ${oy}px`}}>{children}</div></div>;
};

/** Two states of the same frame with a slider that sweeps from `split[0]` to `split[1]` (0..1) over `len` frames. */
export const BeforeAfter: React.FC<{at: number; r: Rect; before: React.ReactNode; after: React.ReactNode; split?: [number, number]; len?: number; labels?: [string, string]}> = ({at, r, before, after, split = [0.08, 0.92], len = 24, labels}) => {
  const {palette, fonts, weights} = useTheme(); const frame = useClock(); const s = ramp(frame, at, at + len, split[0], split[1], EASE_IO);
  return (
    <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, overflow: 'hidden', borderRadius: 14}}>
      <div style={{position: 'absolute', inset: 0}}>{after}</div>
      <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${(1 - s) * 100}% 0 0)`}}>{before}</div>
      <div style={{position: 'absolute', top: 0, bottom: 0, left: `${s * 100}%`, width: 3, background: palette.white, boxShadow: `0 0 12px ${rgba(palette.ink, 0.5)}`}} />
      {labels ? <>
        <div style={{position: 'absolute', left: 16, top: 14, padding: '6px 12px', borderRadius: 8, background: rgba(palette.ink, 0.7), color: '#fff', fontFamily: fonts.body, fontWeight: weights.bold, fontSize: 22}}>{labels[0]}</div>
        <div style={{position: 'absolute', right: 16, top: 14, padding: '6px 12px', borderRadius: 8, background: rgba(palette.accent, 0.85), color: '#fff', fontFamily: fonts.body, fontWeight: weights.bold, fontSize: 22}}>{labels[1]}</div>
      </> : null}
    </div>
  );
};

/** Chat bubble (user prompt / AI result), sliding in from its side; `badge` shows a step number. */
export const PromptBubble: React.FC<{at: number; x: number; y: number; w: number; badge?: string; side?: 'right' | 'left'; tone?: 'user' | 'ai'; children: React.ReactNode; padding?: number; style?: CSS}> = ({at, x, y, w, badge, side = 'right', tone = 'user', children, padding = 26, style}) => {
  const {palette, fonts, weights, preset} = useTheme(); const frame = useClock(); const {fps} = useVideoConfig();
  const p = spring({frame: frame - at, fps, config: preset === 'product' ? SPRING.calm : SPRING.snap});
  if (frame < at - 1) return null;
  const dir = side === 'right' ? 1 : -1; const col = tone === 'user' ? palette.accent : palette.secondary;
  return (
    <div style={{position: 'absolute', left: x, top: y, width: w, opacity: Math.min(1, p * 2.4), transform: `translateX(${(1 - p) * 60 * dir}px)`, background: tone === 'user' ? rgba(palette.accent, 0.13) : rgba(palette.bg2, 0.92), border: `1px solid ${rgba(col, 0.55)}`, borderRadius: 18, padding, boxShadow: `0 22px 60px ${rgba(palette.ink, 0.25)}`, color: palette.white, fontFamily: fonts.body, fontWeight: weights.bold, fontSize: 28, lineHeight: 1.45, ...style}}>
      {badge ? <div style={{position: 'absolute', left: side === 'right' ? -20 : undefined, right: side === 'right' ? undefined : -20, top: -20, width: 44, height: 44, borderRadius: 22, background: col, color: palette.bg, fontFamily: fonts.sans, fontWeight: weights.black, fontSize: 24, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{badge}</div> : null}
      {children}
    </div>
  );
};

/** Terminal panel typing `lines` in sequence at `cps` characters per second from `at`. */
export const Terminal: React.FC<{at: number; lines: string[]; cps?: number; width: number; height?: number; prompt?: string; title?: string; style?: CSS}> = ({at, lines, cps = 40, width, height, prompt = '$ ', title = 'terminal', style}) => {
  const {palette, fonts} = useTheme(); const frame = useClock(); const {fps} = useVideoConfig();
  let budget = Math.max(0, ((frame - at) / fps) * cps); const shown: string[] = [];
  for (const l of lines) { if (budget <= 0) break; shown.push(l.slice(0, Math.floor(budget))); budget -= l.length + 6; }
  // Never show an empty box: hidden before `at`, and from `at` the prompt + cursor are on screen before the first character types.
  if (shown.length === 0 && lines.length) shown.push('');
  return (
    <div style={{width, height, borderRadius: 14, overflow: 'hidden', background: '#0d1117', border: `1px solid ${rgba(palette.white, 0.12)}`, boxShadow: `0 20px 60px ${rgba(palette.ink, 0.35)}`, opacity: frame < at ? 0 : 1, ...style}}>
      <div style={{height: 40, display: 'flex', alignItems: 'center', gap: 8, padding: '0 14px', background: '#161b22', color: '#8b949e', fontFamily: fonts.body, fontSize: 18}}>
        {['#ff5f57', '#febc2e', '#28c840'].map((c) => <div key={c} style={{width: 12, height: 12, borderRadius: 6, background: c}} />)}<span style={{marginLeft: 8}}>{title}</span>
      </div>
      <div style={{padding: 18, fontFamily: '"SF Mono","Menlo","Consolas",monospace', fontSize: 24, lineHeight: 1.5, color: '#e6edf3', ...TABULAR, whiteSpace: 'pre-wrap'}}>
        {shown.map((l, i) => <div key={i}><span style={{color: '#7ee787'}}>{lines[i].startsWith('>') ? '' : prompt}</span>{l}{i === shown.length - 1 && l.length < lines[i].length && frame % 16 < 8 ? '▌' : ''}</div>)}
      </div>
    </div>
  );
};

/** Vertical step list: each step checks off at its frame; completed steps dim to 55%. */
export const StepRail: React.FC<{steps: Array<{text: string; at: number}>; width: number; size?: number; style?: CSS}> = ({steps, width, size = 30, style}) => {
  const {palette, fonts, weights} = useTheme(); const frame = useClock();
  const current = steps.reduce((acc, s, i) => (frame >= s.at ? i : acc), -1);
  return (
    <div style={{width, ...style}}>
      {steps.map((s, i) => {
        const done = frame >= s.at; const k = EASE_SOFT(progress(frame, s.at, 12)); const active = i === current;
        return (
          <div key={i} style={{display: 'flex', gap: 16, alignItems: 'center', marginBottom: 14, opacity: done ? (active ? 1 : 0.55) : 0.35}}>
            <div style={{width: size * 1.1, height: size * 1.1, borderRadius: '50%', border: `2px solid ${done ? palette.accent : rgba(palette.muted, 0.5)}`, background: done ? rgba(palette.accent, 0.9 * k) : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: size * 0.7, transform: `scale(${(0.9 + 0.1 * k).toFixed(3)})`}}>{done ? '✓' : ''}</div>
            <div style={{fontFamily: fonts.body, fontWeight: weights.bold, fontSize: size, color: palette.white}}>{s.text}</div>
          </div>
        );
      })}
    </div>
  );
};
