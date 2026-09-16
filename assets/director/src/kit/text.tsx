/** kit/text.tsx — display type: slams, counters, typewriters, highlighted sentences, title bars. */
import React from 'react';
import {useVideoConfig} from 'remotion';
import {EASE, TABULAR, group1000, mulOpacity, progress, ramp, rgba, useTheme} from './core';
import {useClock} from './clock';

type CSS = React.CSSProperties;

/** Big display type in the theme's display face. */
export const Display: React.FC<{text: string; size: number; color?: string; shadow?: boolean; style?: CSS}> = ({text, size, color, shadow, style}) => {
  const {palette, fonts, preset} = useTheme();
  return <div style={{fontFamily: fonts.display, fontSize: size, lineHeight: 1.02, color: color ?? palette.white, letterSpacing: 1, textShadow: (shadow ?? preset === 'impact') ? `0 6px 30px ${rgba(palette.bg, 0.85)}` : undefined, whiteSpace: 'pre-line', ...style}}>{text}</div>;
};

/** Headline slam (impact): scale 1.2→1, blur 10→0, skew converges, 6-frame RGB split. Product preset degrades to a soft rise (no split, no skew). */
export const Slam: React.FC<{text: string; at: number; size: number; color?: string; frames?: number; scaleFrom?: number; blurFrom?: number; skewFrom?: number; rotate?: number; rgb?: boolean; letterSpacing?: number; font?: string; weight?: number; style?: CSS}> = ({
  text, at, size, color, frames = 10, scaleFrom, blurFrom, skewFrom, rotate = 0, rgb, letterSpacing = 2, font, weight, style,
}) => {
  const {palette, fonts, preset} = useTheme(); const frame = useClock(); const impact = preset === 'impact';
  const p = progress(frame, at, impact ? frames : Math.max(frames, 16)); const e = EASE(p);
  const s0 = scaleFrom ?? (impact ? 1.2 : 1.04); const b0 = blurFrom ?? (impact ? 10 : 0); const k0 = skewFrom ?? (impact ? -12 : 0);
  const scale = s0 + (1 - s0) * e; const blur = b0 * (1 - e); const skew = k0 * (1 - e);
  const split = impact && (rgb ?? true) ? Math.max(0, 1 - progress(frame, at, 7)) * 14 : 0;
  const base: CSS = {fontFamily: font ?? fonts.display, fontSize: size, fontWeight: weight ?? (impact ? 400 : 700), lineHeight: 1, letterSpacing, whiteSpace: 'nowrap'};
  return (
    <div style={{...style, opacity: mulOpacity(style, progress(frame, at - 1, 2)), transform: `rotate(${rotate}deg) scale(${scale}) skewX(${skew}deg) translateY(${impact ? 0 : (1 - e) * 24}px)`, filter: blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : undefined}}>
      <div style={{position: 'relative', display: 'inline-block'}}>
        {split > 0.4 ? (
          <>
            <div style={{...base, position: 'absolute', left: -split, top: 0, color: '#ff2f5e', mixBlendMode: 'screen', opacity: 0.85}}>{text}</div>
            <div style={{...base, position: 'absolute', left: split, top: 0, color: '#2fd6ff', mixBlendMode: 'screen', opacity: 0.85}}>{text}</div>
          </>
        ) : null}
        <div style={{...base, position: 'relative', color: color ?? palette.white}}>{text}</div>
      </div>
    </div>
  );
};

/** Rolling number, tabular digits, ease-out over `frames` (default 24 = 0.8 s). */
export const Counter: React.FC<{at: number; from: number; to: number; frames?: number; size: number; color?: string; prefix?: string; suffix?: string; group?: boolean; decimals?: number; weight?: number; font?: string; style?: CSS}> = ({
  at, from, to, frames = 24, size, color, prefix = '', suffix = '', group = true, decimals = 0, weight, font, style,
}) => {
  const {palette, fonts, weights} = useTheme(); const frame = useClock();
  const v = ramp(frame, at, at + frames, from, to);
  const text = decimals > 0 ? v.toFixed(decimals) : group ? group1000(v) : String(Math.round(v));
  const shown = mulOpacity(style, progress(frame, at - 1, 3));
  return <div style={{fontFamily: font ?? fonts.sans, fontWeight: weight ?? weights.black, fontSize: size, lineHeight: 1, color: color ?? palette.gold, ...TABULAR, whiteSpace: 'nowrap', ...style, opacity: shown}}>{prefix}{text}{suffix}</div>;
};

/** Typewriter reveal at `cps` characters per second; layout stays stable (hidden full text reserves the box). */
export const Typewriter: React.FC<{at: number; text: string; cps?: number; caret?: boolean; size?: number; color?: string; font?: string; style?: CSS}> = ({at, text, cps = 26, caret = true, size, color, font, style}) => {
  const {palette, fonts, weights} = useTheme(); const frame = useClock(); const {fps} = useVideoConfig();
  const n = Math.max(0, Math.min(text.length, Math.floor(((frame - at) / fps) * cps))); const done = n >= text.length;
  return (
    <span style={{fontFamily: font ?? fonts.body, fontWeight: weights.bold, fontSize: size, color: color ?? palette.white, position: 'relative', display: 'inline-block', ...TABULAR, ...style}}>
      <span style={{visibility: 'hidden'}}>{text}</span>
      <span style={{position: 'absolute', inset: 0}}>{text.slice(0, n)}{caret && !done && frame >= at ? <span style={{opacity: frame % 16 < 8 ? 1 : 0.15}}>▌</span> : null}</span>
    </span>
  );
};

type Seg = {t: string; hit: boolean};
export const segment = (text: string, needles: string[]): Seg[] => {
  const out: Seg[] = []; let rest = text; const list = needles.filter(Boolean);
  while (rest.length) {
    let best = -1; let bestN = '';
    for (const n of list) { const i = rest.indexOf(n); if (i >= 0 && (best < 0 || i < best)) { best = i; bestN = n; } }
    if (best < 0) { out.push({t: rest, hit: false}); break; }
    if (best > 0) out.push({t: rest.slice(0, best), hit: false});
    out.push({t: bestN, hit: true}); rest = rest.slice(best + bestN.length);
  }
  return out;
};

/** Highlights verbatim substrings of a sentence at `at`; the rest dims. Substrings must exist in `text` (quotes come from claims.json). */
export const HighlightText: React.FC<{text: string; needles: string | string[]; at?: number; color?: string; base?: string; dim?: number; style?: CSS}> = ({text, needles, at, color, base, dim = 0.42, style}) => {
  const {palette} = useTheme(); const frame = useClock();
  const k = at === undefined ? 1 : EASE(progress(frame, at, 9)); const hot = color ?? palette.accentBright;
  const segs = segment(text, Array.isArray(needles) ? needles : [needles]);
  return (
    <span style={style}>
      {segs.map((s, i) => s.hit
        ? <span key={i} style={{color: k > 0.5 ? hot : base ?? palette.white, background: rgba(palette.accent, 0.22 * k), boxShadow: `0 2px 0 ${rgba(palette.accent, 0.9 * k)}`, padding: '0 2px'}}>{s.t}</span>
        : <span key={i} style={{color: base ?? palette.white, opacity: 1 - (1 - dim) * k}}>{s.t}</span>)}
    </span>
  );
};

/** Title strip: accent bar + title + optional sub, sliding in from the left/right. */
export const TitleBar: React.FC<{at: number; title: string; sub?: string; width?: number | string; from?: 'left' | 'right'; size?: number; subSize?: number; accent?: string; style?: CSS}> = ({at, title, sub, width, from = 'left', size = 52, subSize = 27, accent, style}) => {
  const {palette, fonts, weights, preset} = useTheme(); const frame = useClock(); const col = accent ?? palette.accent;
  const p = EASE(progress(frame, at, 16));
  return (
    <div style={{width, display: 'flex', gap: 18, alignItems: 'stretch', opacity: p, transform: `translateX(${(((from === 'left' ? -1 : 1) * (preset === 'impact' ? 90 : 40)) * (1 - p)).toFixed(1)}px)`, ...style}}>
      <div style={{width: 5, background: col, flex: '0 0 auto', boxShadow: preset === 'impact' ? `0 0 18px ${col}` : undefined, borderRadius: 3}} />
      <div style={{flex: 1}}>
        <div style={{fontFamily: fonts.sans, fontWeight: weights.black, fontSize: size, lineHeight: 1.15, color: palette.white, letterSpacing: 1}}>{title}</div>
        {sub ? <div style={{marginTop: 8, fontFamily: fonts.body, fontWeight: weights.bold, fontSize: subSize, lineHeight: 1.3, color: palette.accentBright, opacity: 0.85, letterSpacing: 0.6}}>{sub}</div> : null}
      </div>
    </div>
  );
};
