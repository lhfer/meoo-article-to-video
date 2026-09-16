/** kit/cards.tsx — code-drawn cards: social posts/statements, quotes, timelines, summary cards, metric tiles, list reveals. */
import React from 'react';
import {Img} from 'remotion';
import {EASE, TABULAR, group1000, progress, ramp, rgba, tintOf, useTheme} from './core';
import {useClock} from './clock';
import {Panel, SlideIn} from './surface';
import {HighlightText, segment} from './text';
import {toneColor} from './marks';
import type {Tone} from './marks';

type CSS = React.CSSProperties;

const SourceTag: React.FC<{text: string; color: string}> = ({text, color}) => {
  const {fonts, weights} = useTheme();
  return <div style={{position: 'absolute', top: 0, right: 0, fontFamily: fonts.body, fontWeight: weights.bold, fontSize: 20, letterSpacing: 2, color, opacity: 0.75, border: `1px solid ${rgba(color, 0.33)}`, padding: '2px 10px'}}>{text}</div>;
};

/**
 * Code-drawn post/statement card (never a screenshot): avatar, name ✓ handle, body (verbatim from claims.json), time.
 * variant: 'x' (blue check), 'mastodon' (secondary), 'xiaohongshu' (warm), 'statement' (light quote panel with a label).
 */
export const SocialCard: React.FC<{at: number; avatar?: string; name: string; handle?: string; verified?: boolean; body: string; sub?: string; time?: string; width: number; variant?: 'x' | 'mastodon' | 'xiaohongshu' | 'statement'; sourceTag?: string; highlight?: string | string[]; highlightAt?: number; from?: 'bottom' | 'left' | 'right' | 'top'; fontSize?: number; style?: CSS}> = ({
  at, avatar, name, handle, verified = true, body, sub, time, width, variant = 'x', sourceTag, highlight, highlightAt, from = 'bottom', fontSize = 30, style,
}) => {
  const t = useTheme(); const tint = tintOf(t); const p = t.palette;
  const accent = variant === 'mastodon' ? p.secondary : variant === 'xiaohongshu' ? p.warm : p.accent;
  const light = variant === 'statement';
  return (
    <SlideIn at={at} from={from} style={style}>
      <Panel width={width} padding={26} tone={light ? 'light' : 'dark'} line={light ? undefined : rgba(accent, 0.5)}>
        <SourceTag text={sourceTag ?? (variant === 'mastodon' ? 'Mastodon' : variant === 'xiaohongshu' ? '原帖' : variant === 'statement' ? '声明' : '原文')} color={light ? p.ink : accent} />
        <div style={{display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16}}>
          {avatar ? <div style={{width: 62, height: 62, borderRadius: variant === 'mastodon' ? 14 : '50%', overflow: 'hidden', border: `1px solid ${rgba(accent, 0.35)}`, flex: '0 0 auto'}}><Img src={avatar} style={{width: '100%', height: '100%', objectFit: 'cover'}} /></div> : null}
          <div style={{display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap'}}>
            <span style={{fontFamily: t.fonts.sans, fontWeight: t.weights.black, fontSize: 32, color: light ? p.ink : p.white}}>{name}</span>
            {verified && !light ? <span style={{width: 26, height: 26, borderRadius: '50%', background: accent, color: '#fff', fontSize: 17, lineHeight: '26px', textAlign: 'center', display: 'inline-block'}}>✓</span> : null}
            {handle ? <span style={{fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize: 26, color: light ? rgba(p.ink, 0.6) : p.muted}}>{handle}</span> : null}
          </div>
        </div>
        <div style={{fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize, lineHeight: 1.42, letterSpacing: 0.4, color: light ? p.ink : p.white}}>
          {highlight ? <HighlightText text={body} needles={highlight} at={highlightAt} base={light ? p.ink : undefined} /> : body}
        </div>
        {sub ? <div style={{marginTop: 12, fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize: fontSize - 6, lineHeight: 1.42, color: light ? rgba(p.ink, 0.65) : p.muted}}>{sub}</div> : null}
        {time ? <div style={{marginTop: 16, paddingTop: 12, borderTop: `1px solid ${light ? rgba(p.ink, 0.15) : tint.lineSoft}`, fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize: 22, color: light ? rgba(p.ink, 0.6) : p.muted, letterSpacing: 0.6}}>{time}</div> : null}
      </Panel>
    </SlideIn>
  );
};

/** Light quote panel with an accent rule; highlights verbatim substrings at `highlightAt`. */
export const QuoteCard: React.FC<{at: number; quote: string; source?: string; label?: string; width: number; highlight?: string | string[]; highlightAt?: number; from?: 'bottom' | 'left' | 'right' | 'top'; fontSize?: number; style?: CSS}> = ({at, quote, source, label, width, highlight, highlightAt, from = 'left', fontSize = 27, style}) => {
  const t = useTheme(); const frame = useClock(); const p = t.palette;
  const k = highlightAt === undefined ? 1 : EASE(progress(frame, highlightAt, 9));
  const segs = segment(quote, highlight ? (Array.isArray(highlight) ? highlight : [highlight]) : []);
  return (
    <SlideIn at={at} from={from} style={style}>
      <Panel tone="light" width={width} padding={24} corners={false}>
        <div style={{display: 'flex', gap: 16}}>
          <div style={{width: 4, background: p.accent, flex: '0 0 auto', opacity: 0.8, borderRadius: 2}} />
          <div style={{flex: 1}}>
            {label ? <div style={{fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize: 21, color: rgba(p.ink, 0.65), marginBottom: 8, letterSpacing: 0.5}}>{label}</div> : null}
            <div style={{fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize, lineHeight: 1.45, color: p.ink, letterSpacing: 0.3}}>
              {segs.map((s, i) => <span key={i} style={s.hit ? {background: rgba(p.accent, 0.24 * k), boxShadow: `0 2px 0 ${rgba(p.accent, 0.8 * k)}`} : undefined}>{s.t}</span>)}
            </div>
            {source ? <div style={{marginTop: 12, fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize: 20, color: rgba(p.ink, 0.55)}}>{source}</div> : null}
          </div>
        </div>
      </Panel>
    </SlideIn>
  );
};

export type Tick = {pos: number; label?: string; tone?: Tone | string; strong?: boolean; at?: number};
/** Horizontal timeline: axis grows, ticks light in order, optional progress sprint (align it to a BGM hit). */
export const TimelineBar: React.FC<{at: number; width: number; ticks: Tick[]; frames?: number; labelFrom?: string; labelTo?: string; axisColor?: string; progressBar?: {at: number; from: number; to: number; frames?: number; color?: string}; labelSide?: 'above' | 'below'; style?: CSS}> = ({at, width, ticks, frames = 20, labelFrom, labelTo, axisColor, progressBar, labelSide = 'below', style}) => {
  const t = useTheme(); const frame = useClock(); const p = t.palette; const grow = EASE(progress(frame, at, frames));
  const pb = progressBar ? {from: progressBar.from, w: (ramp(frame, progressBar.at, progressBar.at + (progressBar.frames ?? 18), progressBar.from, progressBar.to) - progressBar.from) * width, color: progressBar.color ?? p.accent, on: frame >= progressBar.at} : null;
  return (
    <div style={{position: 'relative', width, height: 4, ...style}}>
      <div style={{position: 'absolute', left: 0, top: 1, height: 2, width: width * grow, background: axisColor ?? rgba(p.muted, 0.55)}} />
      {pb && pb.on ? <div style={{position: 'absolute', left: pb.from * width, top: 0, height: 4, width: Math.max(0, pb.w), background: pb.color, boxShadow: t.preset === 'impact' ? `0 0 18px ${pb.color}` : undefined}} /> : null}
      {ticks.map((tk, i) => {
        const on = EASE(progress(frame, tk.at ?? at + frames * tk.pos, 8)); const col = toneColor(p, tk.tone ?? 'muted'); const x = tk.pos * width;
        if (grow < tk.pos - 0.02 && tk.at === undefined) return null;
        return (
          <div key={i} style={{position: 'absolute', left: x, top: 0, opacity: on}}>
            <div style={{position: 'absolute', left: tk.strong ? -7 : -1.5, top: tk.strong ? -5 : -8, width: tk.strong ? 14 : 3, height: tk.strong ? 14 : 20, borderRadius: tk.strong ? '50%' : 0, background: col, boxShadow: tk.strong && t.preset === 'impact' ? `0 0 16px ${col}` : undefined}} />
            {tk.label ? <div style={{position: 'absolute', left: 0, top: labelSide === 'below' ? 22 : undefined, bottom: labelSide === 'above' ? 22 : undefined, transform: 'translateX(-50%)', fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize: 24, color: col, whiteSpace: 'nowrap'}}>{tk.label}</div> : null}
          </div>
        );
      })}
      {labelFrom ? <div style={{position: 'absolute', left: 0, top: labelSide === 'below' ? -40 : 22, fontFamily: t.fonts.sans, fontWeight: t.weights.black, fontSize: 28, color: p.muted, opacity: grow}}>{labelFrom}</div> : null}
      {labelTo ? <div style={{position: 'absolute', right: 0, top: labelSide === 'below' ? -40 : 22, fontFamily: t.fonts.sans, fontWeight: t.weights.black, fontSize: 28, color: p.muted, opacity: grow}}>{labelTo}</div> : null}
    </div>
  );
};

/** Screenshot-worthy summary: 3–5 short items appear one by one (`step` frames apart), then the card settles. */
export const SummaryCard: React.FC<{at: number; title?: string; items: string[]; width: number; step?: number; size?: number; style?: CSS}> = ({at, title, items, width, step = 10, size = 34, style}) => {
  const t = useTheme(); const frame = useClock(); const p = t.palette;
  const done = at + step * items.length + 6; const settle = frame >= done ? 1 - 0.015 * EASE(progress(frame, done, 8)) : 1;
  return (
    <SlideIn at={at} style={{...style, transform: `scale(${settle.toFixed(3)})`}}>
      <Panel width={width} padding={30}>
        {title ? <div style={{fontFamily: t.fonts.sans, fontWeight: t.weights.black, fontSize: size + 6, color: p.white, marginBottom: 18, letterSpacing: 1}}>{title}</div> : null}
        {items.map((it, i) => {
          const k = EASE(progress(frame, at + 6 + i * step, 10));
          return (
            <div key={i} style={{display: 'flex', gap: 16, alignItems: 'flex-start', opacity: k, transform: `translateX(${(1 - k) * 24}px)`, marginBottom: 12}}>
              <div style={{width: 12, height: 12, borderRadius: 6, background: p.accentBright, marginTop: size * 0.45, flex: '0 0 auto'}} />
              <div style={{fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize: size, lineHeight: 1.35, color: p.white}}>{it}</div>
            </div>
          );
        })}
      </Panel>
    </SlideIn>
  );
};

/** One number with unit, label and a growing bar (product preset for metrics; impact uses Counter + Stamp instead). */
export const MetricTile: React.FC<{at: number; value: number; label: string; unit?: string; prefix?: string; decimals?: number; max?: number; width?: number; size?: number; tone?: Tone | string; frames?: number; style?: CSS}> = ({at, value, label, unit = '', prefix = '', decimals = 0, max, width = 320, size = 72, tone = 'accent', frames = 24, style}) => {
  const t = useTheme(); const frame = useClock(); const p = t.palette; const col = toneColor(p, tone);
  const v = ramp(frame, at, at + frames, 0, value); const k = EASE(progress(frame, at, 12));
  const text = decimals > 0 ? v.toFixed(decimals) : group1000(v);
  return (
    <div style={{width, opacity: k, transform: `translateY(${(1 - k) * 16}px)`, ...style}}>
      <Panel padding={22}>
        <div style={{fontFamily: t.fonts.sans, fontWeight: t.weights.black, fontSize: size, lineHeight: 1, color: col, ...TABULAR}}>{prefix}{text}<span style={{fontSize: size * 0.4, marginLeft: 6, color: p.muted}}>{unit}</span></div>
        <div style={{marginTop: 10, fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize: size * 0.34, color: p.muted}}>{label}</div>
        {max ? <div style={{marginTop: 14, height: 6, borderRadius: 3, background: rgba(col, 0.15)}}><div style={{height: 6, borderRadius: 3, width: `${Math.min(100, (v / max) * 100)}%`, background: col}} /></div> : null}
      </Panel>
    </div>
  );
};

/** Rows flash through, then one row stays lit and the rest dim (a list where one entry matters). */
export const ListReveal: React.FC<{at: number; rows: string[]; hit: number; width: number; step?: number; size?: number; placeholder?: boolean; style?: CSS}> = ({at, rows, hit, width, step = 3, size = 32, placeholder = false, style}) => {
  const t = useTheme(); const frame = useClock(); const p = t.palette; const settled = frame >= at + step * rows.length + 4;
  return (
    <div style={{width, ...style}}>
      {rows.map((r, i) => {
        const shown = frame >= at + i * step; const lit = settled ? i === hit : shown && frame < at + (i + 1) * step + 2;
        const isHit = settled && i === hit;
        return (
          <div key={i} style={{display: 'flex', alignItems: 'center', gap: 14, padding: '10px 16px', marginBottom: 6, opacity: shown ? (settled && !isHit ? 0.35 : 1) : 0, background: isHit ? rgba(p.accent, 0.18) : lit ? rgba(p.white, 0.06) : 'transparent', border: `1px solid ${isHit ? rgba(p.accent, 0.7) : 'transparent'}`, borderRadius: 8, transform: `scale(${isHit ? 1.03 : 1})`}}>
            <div style={{fontFamily: t.fonts.sans, fontWeight: t.weights.black, fontSize: size * 0.7, color: isHit ? p.accentBright : p.muted, width: size * 1.2, ...TABULAR}}>{String(i + 1).padStart(2, '0')}</div>
            {placeholder && !isHit ? <div style={{height: size * 0.6, width: '60%', background: rgba(p.muted, 0.3), borderRadius: 4}} /> : <div style={{fontFamily: t.fonts.body, fontWeight: t.weights.bold, fontSize: size, color: isHit ? p.white : p.muted}}>{r}</div>}
          </div>
        );
      })}
    </div>
  );
};
