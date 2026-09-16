/** kit/surface.tsx — backgrounds, panels, screens, framed media and small positioning helpers. */
import React from 'react';
import {AbsoluteFill, Img, spring, useVideoConfig} from 'remotion';
import {EASE, EASE_SOFT, SPRING, mulOpacity, progress, ramp, rgba, tintOf, useTheme} from './core';
import type {Box, Rect} from './core';
import {useClock} from './clock';

type CSS = React.CSSProperties;

/** Full-frame background: palette gradient, optional hex pattern (impact) or plain paper (product), optional slow-rotating image. */
export const Backdrop: React.FC<{tone?: 'cold' | 'warm' | 'paper'; pattern?: boolean; image?: string; imageOpacity?: number; rotate?: number; children?: React.ReactNode}> = ({
  tone = 'cold', pattern, image, imageOpacity = 0.07, rotate = 0.04, children,
}) => {
  const t = useTheme(); const f = useClock(); const p = t.palette;
  const paper = tone === 'paper' || t.preset === 'product';
  const showPattern = pattern ?? (!paper && t.preset === 'impact');
  const grad = paper
    ? `radial-gradient(120% 80% at 50% 30%, ${p.bg2} 0%, ${p.bg} 70%)`
    : tone === 'warm'
      ? `radial-gradient(120% 78% at 50% 34%, ${rgba(p.warm, 0.16)}, ${rgba(p.bg, 0)} 58%), radial-gradient(120% 80% at 50% 30%, ${p.bg2} 0%, ${p.bg} 70%)`
      : `radial-gradient(120% 78% at 50% 32%, ${rgba(p.accent, 0.13)}, ${rgba(p.bg, 0)} 60%), radial-gradient(120% 80% at 50% 30%, ${p.bg2} 0%, ${p.bg} 70%)`;
  return (
    <AbsoluteFill style={{background: grad, overflow: 'hidden'}}>
      {showPattern ? (
        <svg width="100%" height="100%" style={{position: 'absolute', inset: 0, opacity: 0.12}}>
          <defs>
            <pattern id="kit-hex" width="72" height="124" patternUnits="userSpaceOnUse">
              <path d="M36 2 L70 21 L70 60 L36 79 L2 60 L2 21 Z M36 64 L70 83 L70 122 L36 141 L2 122 L2 83 Z" fill="none" stroke={p.accentBright} strokeWidth="1.2" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#kit-hex)" />
        </svg>
      ) : null}
      {image ? <Img src={image} style={{position: 'absolute', left: '50%', top: '50%', width: '150%', transform: `translate(-50%,-50%) rotate(${f * rotate}deg)`, opacity: imageOpacity, filter: 'blur(2px)'}} /> : null}
      {children}
    </AbsoluteFill>
  );
};

export const Vignette: React.FC<{strength?: number; style?: CSS}> = ({strength = 0.72, style}) => {
  const {palette} = useTheme();
  return <AbsoluteFill style={{background: `radial-gradient(115% 78% at 50% 42%, ${rgba(palette.bg, 0)} 32%, ${rgba(palette.bg, strength)} 100%)`, pointerEvents: 'none', ...style}} />;
};

const cutPath = (cut: number): string =>
  `polygon(${cut}px 0, calc(100% - ${cut}px) 0, 100% ${cut}px, 100% calc(100% - ${cut}px), calc(100% - ${cut}px) 100%, ${cut}px 100%, 0 calc(100% - ${cut}px), 0 ${cut}px)`;

/** Corner ticks (L shapes) drawn inside a panel. */
export const Corners: React.FC<{size?: number; color?: string; inset?: number; opacity?: number}> = ({size = 14, color, inset = 8, opacity = 0.5}) => {
  const {palette} = useTheme(); const col = color ?? palette.accentBright;
  return (
    <>
      {([{top: inset, left: inset, bt: 1, bl: 1}, {top: inset, right: inset, bt: 1, br: 1}, {bottom: inset, left: inset, bb: 1, bl: 1}, {bottom: inset, right: inset, bb: 1, br: 1}] as Array<Record<string, number>>).map((c, i) => (
        <div key={i} style={{position: 'absolute', width: size, height: size, top: c.top, left: c.left, right: c.right, bottom: c.bottom,
          borderTop: c.bt ? `2px solid ${col}` : undefined, borderBottom: c.bb ? `2px solid ${col}` : undefined, borderLeft: c.bl ? `2px solid ${col}` : undefined, borderRight: c.br ? `2px solid ${col}` : undefined, opacity, pointerEvents: 'none'}} />
      ))}
    </>
  );
};

/** Dark/light translucent panel: hairline accent border, cut corners (impact) or soft radius (product), inner shadow. Media is embedded here, never pasted bare. */
export const Panel: React.FC<{children?: React.ReactNode; tone?: 'dark' | 'light'; width?: number | string; padding?: number | string; cut?: number; line?: string; corners?: boolean; radius?: number; style?: CSS}> = ({
  children, tone = 'dark', width, padding = 26, cut, line, corners, radius, style,
}) => {
  const t = useTheme(); const tint = tintOf(t); const product = t.preset === 'product';
  const border = line ?? (tone === 'dark' ? tint.line : tint.lineLight);
  const fill = tone === 'dark' ? tint.panel : tint.panelLight;
  const c = cut ?? (product ? 0 : 16); const r = radius ?? (product ? 22 : 0); const ticks = corners ?? !product;
  const clip = c > 0 ? cutPath(c) : undefined;
  return (
    <div style={{width, background: border, clipPath: clip, borderRadius: r, boxShadow: product ? `0 14px 40px ${rgba(t.palette.ink, 0.10)}` : tint.glow, ...style}}>
      <div style={{position: 'relative', margin: 1, padding, background: fill, clipPath: c > 0 ? cutPath(c - 1) : undefined, borderRadius: r > 0 ? r - 1 : 0, color: tone === 'dark' ? t.palette.white : t.palette.ink, boxShadow: tone === 'dark' && !product ? tint.inner : 'none'}}>
        {ticks ? <Corners /> : null}
        {children}
      </div>
    </div>
  );
};

/** Chrome drawn around a rect (screens, device bezels): hairline border, inner shadow, corner ticks, optional glow. */
export const PanelChrome: React.FC<{r: Rect; color?: string; glow?: number; radius?: number; children?: React.ReactNode}> = ({r, color, glow = 0, radius = 2, children}) => {
  const {palette} = useTheme(); const col = color ?? palette.accent;
  return (
    <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, borderRadius: radius, border: `1px solid ${col}`, pointerEvents: 'none',
      boxShadow: `inset 0 0 60px ${rgba(palette.bg, 0.6)}, 0 0 ${18 + glow * 46}px ${rgba(col, 0.14 + glow * 0.5)}`}}>
      <Corners opacity={0.9} color={col} />
      {children}
    </div>
  );
};

/** Source media mapped into a rect through an explicit crop + zoom + focus point; children render at the source size. */
export const Screen: React.FC<{r: Rect; source: Box; crop: Rect; zoom?: number; fx?: number; fy?: number; dim?: number; blur?: number; chrome?: boolean; chromeColor?: string; glow?: number; radius?: number; children: React.ReactNode; style?: CSS}> = ({
  r, source, crop, zoom = 1, fx = 0.5, fy = 0.5, dim = 0, blur = 0, chrome = true, chromeColor, glow = 0, radius = 2, children, style,
}) => {
  const {palette} = useTheme();
  const s = Math.max(r.w / crop.w, r.h / crop.h) * zoom;
  const left = r.w / 2 - (crop.x + fx * crop.w) * s;
  const top = r.h / 2 - (crop.y + fy * crop.h) * s;
  return (
    <>
      <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, overflow: 'hidden', background: palette.bg, borderRadius: radius, ...style}}>
        <div style={{position: 'absolute', left, top, width: source.w * s, height: source.h * s, filter: blur > 0 ? `blur(${blur}px)` : undefined}}>{children}</div>
        {dim > 0 ? <div style={{position: 'absolute', inset: 0, background: rgba(palette.bg, dim)}} /> : null}
      </div>
      {chrome ? <PanelChrome r={r} color={chromeColor} glow={glow} radius={radius} /> : null}
    </>
  );
};

/** Maps normalised source coordinates to screen pixels for the same crop/zoom/focus as <Screen>. Basis for markers and callouts. */
export const mapper = (r: Rect, source: Box, crop: Rect, zoom = 1, fx = 0.5, fy = 0.5) => {
  const s = Math.max(r.w / crop.w, r.h / crop.h) * zoom;
  const left = r.x + r.w / 2 - (crop.x + fx * crop.w) * s;
  const top = r.y + r.h / 2 - (crop.y + fy * crop.h) * s;
  return {s, px: (nx: number) => left + nx * source.w * s, py: (ny: number) => top + ny * source.h * s, pw: (nw: number) => nw * source.w * s, ph: (nh: number) => nh * source.h * s};
};

/** Image embedded in a circle/rect mask with a slow push-in (concept art, generated stills). */
export const Framed: React.FC<{src: string; at: number; shape?: 'circle' | 'rect'; size: number | Box; zoom?: [number, number]; frames?: number; enter?: number; rotate?: number; ring?: boolean; objectPosition?: string; imgStyle?: CSS; style?: CSS; children?: React.ReactNode}> = ({
  src, at, shape = 'circle', size, zoom = [1, 1.25], frames = 75, enter = 14, rotate = 0, ring = true, objectPosition = 'center', imgStyle, style, children,
}) => {
  const t = useTheme(); const tint = tintOf(t); const frame = useClock();
  const w = typeof size === 'number' ? size : size.w; const h = typeof size === 'number' ? size : size.h;
  const k = ramp(frame, at, at + frames, zoom[0], zoom[1], t.preset === 'product' ? EASE_SOFT : EASE);
  const inP = EASE(progress(frame, at, enter));
  return (
    <div style={{...style, width: w, height: h, borderRadius: shape === 'circle' ? '50%' : 18, overflow: 'hidden', position: 'relative', opacity: mulOpacity(style, inP), transform: `scale(${(0.93 + 0.07 * inP).toFixed(3)})`, border: ring ? `1px solid ${tint.line}` : undefined, boxShadow: ring ? `${tint.glow}, inset 0 0 60px ${rgba(t.palette.bg, 0.55)}` : undefined}}>
      <Img src={src} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition, transform: `scale(${k.toFixed(4)}) rotate(${rotate.toFixed(2)}deg)`, ...imgStyle}} />
      {children}
    </div>
  );
};

/** Spring slide-in for panels, cards and stacks. Product preset uses the calm spring. */
export const SlideIn: React.FC<{at: number; from?: 'bottom' | 'top' | 'left' | 'right'; distance?: number; frames?: number; fade?: boolean; children: React.ReactNode; style?: CSS}> = ({
  at, from = 'bottom', distance, frames = 18, fade = true, children, style,
}) => {
  const frame = useClock(); const {fps} = useVideoConfig(); const t = useTheme(); const product = t.preset === 'product';
  const dist = distance ?? (product ? 60 : 120);
  const s = spring({frame: frame - at, fps, config: product ? SPRING.calm : SPRING.snap, durationInFrames: frames});
  const d = (1 - s) * dist;
  const tr = from === 'bottom' ? `translateY(${d}px)` : from === 'top' ? `translateY(${-d}px)` : from === 'left' ? `translateX(${-d}px)` : `translateX(${d}px)`;
  return <div style={{transform: tr, opacity: fade ? progress(frame, at, Math.max(4, frames * 0.5)) : 1, ...style}}>{children}</div>;
};

/** Places the centre of children at (x, y). */
export const At: React.FC<{x: number; y: number; transform?: string; origin?: string; children: React.ReactNode; style?: CSS}> = ({x, y, transform = '', origin = 'center center', children, style}) => (
  <div style={{position: 'absolute', left: x, top: y, transform: `translate(-50%,-50%) ${transform}`, transformOrigin: origin, ...style}}>{children}</div>
);

/** A glowing rule that grows from zero (hard-cut line, divider before a turn). */
export const CutLine: React.FC<{at: number; width: number | string; color?: string; thickness?: number; frames?: number; style?: CSS}> = ({at, width, color, thickness = 2, frames = 10, style}) => {
  const {palette, preset} = useTheme(); const frame = useClock(); const col = color ?? palette.accent;
  const p = EASE(progress(frame, at, frames));
  return <div style={{width: typeof width === 'number' ? width * p : width, height: thickness, background: col, boxShadow: preset === 'impact' ? `0 0 22px ${col}` : undefined, opacity: p, ...style}} />;
};

/** Persistent corner credit (source line), 60% opacity by default. */
export const SourceCorner: React.FC<{lines: string[]; side?: 'right' | 'left'; bottom?: number; inset?: number; size?: number; opacity?: number; style?: CSS}> = ({lines, side = 'right', bottom = 26, inset = 30, size = 24, opacity = 0.6, style}) => {
  const {palette, fonts, weights} = useTheme();
  return (
    <div style={{position: 'absolute', bottom, right: side === 'right' ? inset : undefined, left: side === 'left' ? inset : undefined, textAlign: side, fontFamily: fonts.body, fontWeight: weights.bold, fontSize: size, lineHeight: 1.4, color: palette.white, opacity, letterSpacing: 0.5, pointerEvents: 'none', ...style}}>
      {lines.map((l, i) => <div key={i}>{l}</div>)}
    </div>
  );
};
