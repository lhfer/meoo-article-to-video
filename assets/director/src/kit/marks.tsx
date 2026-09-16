/** kit/marks.tsx — stamps, chips, tags, markers, callouts, connectors, sparks, flash and shake (mostly impact preset). */
import React from 'react';
import {AbsoluteFill, Easing, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {EASE, SPRING, jitter, mulOpacity, progress, pulse, ramp, rgba, useTheme} from './core';
import type {Rect} from './core';
import {useClock} from './clock';

type CSS = React.CSSProperties;
export type Tone = 'accent' | 'secondary' | 'warm' | 'red' | 'gold' | 'muted' | 'white';
export const toneColor = (p: ReturnType<typeof useTheme>['palette'], tone: Tone | string): string =>
  ({accent: p.accentBright, secondary: p.secondary, warm: p.warm, red: p.red, gold: p.gold, muted: p.muted, white: p.white} as Record<string, string>)[tone] ?? tone;

/** Full-frame white flash: at most 4 frames, peak ≤ 0.6 (house limit). Pass the REAL frame when the shot uses a hit-stop. */
export const Flash: React.FC<{at: number | number[]; frames?: number; color?: string; max?: number; frame?: number}> = ({at, frames = 4, color = '#ffffff', max = 0.6, frame: override}) => {
  const live = useClock(); const frame = override ?? live; const {preset} = useTheme();
  if (preset === 'product') return null;   // the product preset never flashes
  const list = Array.isArray(at) ? at : [at]; let o = 0;
  for (const a of list) { const d = frame - a; if (d < 0 || d > Math.min(frames, 4)) continue; o = Math.max(o, Math.min(max, 0.6) * Math.pow(1 - d / Math.min(frames, 4), 1.8)); }
  if (o <= 0.002) return null;
  return <AbsoluteFill style={{background: color, opacity: o, pointerEvents: 'none'}} />;
};

/** Whole-frame shake transform string (≤ 12 px, ≤ 7 frames, quadratic decay). Zero in the product preset. */
export const useShake = (at: number | number[], amp = 10, frames = 6, override?: number): string => {
  const live = useCurrentFrame(); const frame = override ?? live; const {preset} = useTheme();
  if (preset === 'product') return 'translate(0px, 0px)';
  const list = Array.isArray(at) ? at : [at]; let x = 0; let y = 0; const a0 = Math.min(amp, 12); const f0 = Math.min(frames, 7);
  for (const a of list) { const d = frame - a; if (d < 0 || d > f0) continue; const k = a0 * Math.pow(1 - d / f0, 2); x += k * jitter(frame, a + 1); y += k * 0.62 * jitter(frame, a + 37); }
  return `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px)`;
};

/** Angled stamp landing from 2.5× with a blur, optional restrikes (impact); product preset shows a plain badge. */
export const Stamp: React.FC<{text: string; at: number; color?: string; size?: number; rotate?: number; restrike?: number | number[]; tone?: 'solid' | 'outline'; sub?: string; style?: CSS}> = ({text, at, color, size = 72, rotate = -13, restrike, tone = 'outline', sub, style}) => {
  const {palette, fonts, preset} = useTheme(); const frame = useClock(); const col = color ?? palette.red; const impact = preset === 'impact';
  const p = progress(frame, at, impact ? 7 : 14); const e = EASE(p);
  let scale = impact ? 2.5 + (1 - 2.5) * e : 0.96 + 0.04 * e;
  const list = restrike === undefined ? [] : Array.isArray(restrike) ? restrike : [restrike];
  if (impact) for (const r of list) if (frame >= r) scale *= 1 + 0.14 * (1 - EASE(progress(frame, r, 8)));
  return (
    <div style={{...style, opacity: mulOpacity(style, progress(frame, at, 2)), transform: `rotate(${impact ? rotate : 0}deg) scale(${scale.toFixed(3)})`, filter: impact ? `blur(${(5 * (1 - e)).toFixed(2)}px)` : undefined}}>
      <div style={{border: `${impact ? 4 : 2}px solid ${col}`, background: tone === 'solid' ? col : rgba(col, 0.1), color: tone === 'solid' ? palette.white : col, fontFamily: impact ? fonts.display : fonts.sans, fontWeight: impact ? 400 : 800, fontSize: size, lineHeight: 1, letterSpacing: impact ? 4 : 1, padding: '10px 26px 14px', whiteSpace: 'nowrap', borderRadius: impact ? 6 : 999}}>
        {text}
        {sub ? <div style={{fontFamily: fonts.body, fontSize: size * 0.42, opacity: 0.85, letterSpacing: 2, marginTop: 4}}>{sub}</div> : null}
      </div>
    </div>
  );
};

/** Pill label popping from `origin` (the on-screen thing being named) to its own position — gaze continuity. */
export const Chip: React.FC<{at: number; label: string; sub?: string; icon?: React.ReactNode; tone?: Tone | string; size?: number; origin?: {x: number; y: number}; frames?: number; filled?: boolean; style?: CSS}> = ({at, label, sub, icon, tone = 'accent', size = 32, origin, frames = 16, filled, style}) => {
  const {palette, fonts, weights, preset} = useTheme(); const frame = useClock(); const {fps} = useVideoConfig();
  const s = spring({frame: frame - at, fps, config: preset === 'product' ? SPRING.calm : SPRING.pop, durationInFrames: frames});
  const col = toneColor(palette, tone); const dx = origin ? origin.x * (1 - s) : 0; const dy = origin ? origin.y * (1 - s) : 0;
  return (
    <div style={{...style, transform: `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px) scale(${(0.72 + 0.28 * s).toFixed(3)})`, opacity: mulOpacity(style, progress(frame, at, 4)), display: 'inline-flex', alignItems: 'center', gap: 12, padding: `${Math.round(size * 0.34)}px ${Math.round(size * 0.66)}px`, borderRadius: 999, border: `1px solid ${rgba(col, 0.6)}`, background: filled ? col : rgba(col, 0.14), color: filled ? palette.bg : col, fontFamily: fonts.sans, fontWeight: weights.black, fontSize: size, lineHeight: 1.1, whiteSpace: 'nowrap'}}>
      {icon}<span>{label}</span>{sub ? <span style={{fontWeight: weights.bold, fontSize: size * 0.7, opacity: 0.72}}>{sub}</span> : null}
    </div>
  );
};

/** Small square-cornered tag for annotations ('示意', '原文', '26 年 · 无人拿走'). */
export const Tag: React.FC<{at: number; label: string; tone?: Tone | string; size?: number; frames?: number; style?: CSS}> = ({at, label, tone = 'muted', size = 24, frames = 12, style}) => {
  const {palette, fonts, weights} = useTheme(); const frame = useClock(); const p = EASE(progress(frame, at, frames)); const col = toneColor(palette, tone);
  return <div style={{...style, opacity: mulOpacity(style, p), transform: `translateY(${((1 - p) * 10).toFixed(1)}px)`, display: 'inline-block', padding: `${Math.round(size * 0.24)}px ${Math.round(size * 0.5)}px`, border: `1px solid ${rgba(col, 0.5)}`, background: rgba(col, 0.1), color: col, fontFamily: fonts.body, fontWeight: weights.bold, fontSize: size, letterSpacing: 1, lineHeight: 1.2, whiteSpace: 'nowrap'}}>{label}</div>;
};

/** Highlight box drawn over a region of a screen. */
export const Marker: React.FC<{at: number; r: Rect; tone?: Tone | string; len?: number; label?: string; labelSize?: number; radius?: number}> = ({at, r, tone = 'accent', len = 12, label, labelSize = 26, radius = 6}) => {
  const {palette, fonts, weights, preset} = useTheme(); const frame = useClock(); const p = ramp(frame, at, at + len, 0, 1); const col = toneColor(palette, tone);
  if (frame < at - 1) return null;
  return (
    <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, border: `2px solid ${col}`, borderRadius: radius, opacity: p, transform: `scale(${(0.86 + 0.14 * p).toFixed(3)})`, boxShadow: preset === 'impact' ? `0 0 ${26 * p}px ${rgba(col, 0.33)}, inset 0 0 ${20 * p}px ${rgba(col, 0.13)}` : `0 0 0 ${4 * p}px ${rgba(col, 0.18)}`, pointerEvents: 'none'}}>
      {label ? <div style={{position: 'absolute', left: 0, top: -labelSize - 14, fontFamily: fonts.sans, fontWeight: weights.black, fontSize: labelSize, color: col, letterSpacing: 2, textShadow: `0 2px 10px ${rgba(palette.bg, 0.9)}`}}>{label}</div> : null}
    </div>
  );
};

/** Label that pops out of a point (ax, ay) to (lx, ly) with a leader line; earlier callouts shrink to make room (`shrink` 0..1). */
export const Callout: React.FC<{at: number; ax: number; ay: number; lx: number; ly: number; text: string; sub?: string; tone?: Tone | string; size?: number; shrink?: number; anchorSide?: 'left' | 'right'}> = ({at, ax, ay, lx, ly, text, sub, tone = 'accent', size = 34, shrink = 0, anchorSide = 'left'}) => {
  const {palette, preset} = useTheme(); const frame = useClock(); const {fps} = useVideoConfig();
  const p = spring({frame: frame - at, fps, config: preset === 'product' ? SPRING.calm : {damping: 185, stiffness: 160, mass: 0.7}});
  if (frame < at - 1) return null;
  const col = toneColor(palette, tone); const k = 1 - shrink * 0.22; const dx = (lx - ax) * p; const dy = (ly - ay) * p;
  return (
    <>
      <svg style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', pointerEvents: 'none'}} width={1} height={1}>
        <circle cx={ax} cy={ay} r={5 * p} fill={col} opacity={0.95 - shrink * 0.5} />
        <circle cx={ax} cy={ay} r={14 * p} fill="none" stroke={col} strokeWidth={1.5} opacity={(1 - p) * 0.9} />
        <path d={`M${ax} ${ay} L${ax + dx} ${ay + dy}`} stroke={col} strokeWidth={1.5} opacity={(0.85 - shrink * 0.45) * p} fill="none" />
      </svg>
      <div style={{position: 'absolute', left: lx, top: ly, opacity: Math.min(1, p * 2.2), transform: `translate(${anchorSide === 'right' ? '-100%' : '0'}, -50%) scale(${(k * (0.82 + 0.18 * p)).toFixed(3)})`, transformOrigin: anchorSide === 'right' ? 'right center' : 'left center'}}>
        <Chip at={at} label={text} sub={sub} tone={tone} size={size} style={{opacity: 1 - shrink * 0.32}} />
      </div>
    </>
  );
};

/** Thin animated line connecting two points with a travelling dot. */
export const Connector: React.FC<{at: number; len?: number; x1: number; y1: number; x2: number; y2: number; color?: string; width?: number}> = ({at, len = 14, x1, y1, x2, y2, color, width = 2}) => {
  const {palette} = useTheme(); const frame = useClock(); const p = ramp(frame, at, at + len, 0, 1); const col = color ?? palette.accent;
  if (p <= 0) return null;
  return (
    <svg style={{position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'visible'}} width="100%" height="100%">
      <path d={`M${x1} ${y1} L${x1 + (x2 - x1) * p} ${y1 + (y2 - y1) * p}`} stroke={col} strokeWidth={width} fill="none" opacity={0.9} />
      <circle cx={x1 + (x2 - x1) * p} cy={y1 + (y2 - y1) * p} r={4} fill={col} opacity={0.9} />
    </svg>
  );
};

/** Sparks bursting from a point (deterministic). Impact only. */
export const Sparks: React.FC<{at: number; x: number; y: number; count?: number; spread?: number; len?: number; color?: string}> = ({at, x, y, count = 34, spread = 620, len = 34, color}) => {
  const {palette, preset} = useTheme(); const frame = useClock(); const col = color ?? palette.gold;
  if (preset === 'product' || frame < at || frame > at + len) return null;
  const t = (frame - at) / len;
  return (
    <svg style={{position: 'absolute', inset: 0, pointerEvents: 'none'}} width="100%" height="100%">
      {new Array(count).fill(0).map((_, i) => {
        const a = random(`a${i}`) * Math.PI * 2; const d = (0.35 + random(`d${i}`) * 0.65) * spread * Easing.out(Easing.cubic)(t); const r = 2 + random(`r${i}`) * 3.4;
        return <circle key={i} cx={x + Math.cos(a) * d} cy={y + Math.sin(a) * d * 0.82} r={r * (1 - t * 0.6)} fill={i % 4 === 0 ? palette.white : col} opacity={(1 - t) * 0.95} />;
      })}
    </svg>
  );
};

/** Pulse helper re-exported for shots that draw their own flashes. */
export {pulse};
