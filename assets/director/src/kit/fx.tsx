/**
 * kit/fx.tsx — GPU effects (@remotion/effects) on a transparent <Solid>, plus a motion trail (@remotion/motion-blur). Impact preset only:
 * the product preset renders nothing (Trail passes its children through).
 * WebGL2 is required for LightLeak / Starburst: render.py adds --gl=angle when a shot uses them (or brief.render.gl is set);
 * Studio previews in a normal Chrome need nothing. House limits live here (leak opacity ≤ 0.45 and ≤ 24 frames, starburst opacity ≤ 0.35
 * behind a radial fade, trail ≤ 6 layers) and qa.py re-checks the rendered file (flash length / frequency / luminance jumps).
 * Determinism (measured, docs/effects-radar.md): mix-blend-mode on the WebGL canvas — or a blend / isolation wrapper around it — renders
 * differently between identical renders under angle and breaks review.py carry-opening (12–18 of 150 frames). Normal blending with a CSS mask
 * is stable (0 differing frames over 5 renders), so both light parts blend normally and never use mix-blend-mode. The GPU backend itself still
 * dithers gradients by ±1–2 levels on a few frames, which render.py absorbs with PNG intermediates and carry-opening with a ±4 tolerance.
 */
import React from 'react';
import {Solid, useCurrentFrame, usePixelDensity, useVideoConfig} from 'remotion';
import {lightLeak} from '@remotion/effects/light-leak';
import {starburst} from '@remotion/effects/starburst';
import {Trail as MotionTrail} from '@remotion/motion-blur';
import {EASE_IO, ramp, useTheme} from './core';
import {ShotClock, useClock, useShotClockValue} from './clock';

type CSS = React.CSSProperties;
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
/** Hue (0–360) of a hex color. The light leak's base is yellow-orange (~35°); hueShift = accent hue − 35 keeps it on palette. */
export const hueOf = (hex: string): number => {
  const h = hex.replace('#', ''); const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h; const n = parseInt(full.slice(0, 6), 16);
  const r = ((n >> 16) & 255) / 255; const g = ((n >> 8) & 255) / 255; const b = (n & 255) / 255;
  const max = Math.max(r, g, b); const min = Math.min(r, g, b); const d = max - min;
  if (d === 0) return 0;
  const hue = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (hue * 60 + 360) % 360;
};
const LEAK_BASE_HUE = 35;

/** Light leak bloom: reveals over the first half of `len`, retracts over the second. `side` keeps it to the outer ~60% from one edge (a leak, not a wash); normal blending, opacity caps at 0.45. ≤ 3 per film; not inside the first 3 s. */
export const LightLeak: React.FC<{at: number; len?: number; seed?: number; hue?: number; opacity?: number; side?: 'left' | 'right' | 'top' | 'bottom' | 'none'; style?: CSS}> = ({at, len = 16, seed = 3, hue, opacity = 0.36, side = 'right', style}) => {
  const {palette, preset} = useTheme(); const frame = useClock(); const {width, height} = useVideoConfig(); const density = usePixelDensity();
  const n = Math.min(len, 24);
  if (preset === 'product' || frame < at || frame > at + n) return null;
  const progress = clamp01((frame - at) / n);
  const shift = ((((hue ?? hueOf(palette.accent)) - LEAK_BASE_HUE) % 360) + 360) % 360;
  const mask = side === 'none' ? undefined : `linear-gradient(to ${side}, rgba(0,0,0,0) 0%, rgba(0,0,0,0) 38%, rgba(0,0,0,0.55) 68%, rgba(0,0,0,1) 100%)`;
  return <Solid width={width} height={height} pixelDensity={density} style={{position: 'absolute', left: 0, top: 0, opacity: Math.min(opacity, 0.45), pointerEvents: 'none', maskImage: mask, WebkitMaskImage: mask, ...style}} effects={[lightLeak({seed, hueShift: shift, progress})]} />;
};

/** Retro ray field behind a hit (stamp, counter, slam): origin at (x, y) in stage px, fades out within `radius` px (radial mask), slow spin, scales in over `fade` frames. Normal blending. ≤ 1 per beat, ≤ 4 per film. */
export const Starburst: React.FC<{at: number; len?: number; x: number; y: number; radius?: number; rays?: number; colors?: [string, string]; opacity?: number; spin?: number; fade?: number; style?: CSS}> = ({at, len = 60, x, y, radius = 480, rays = 18, colors, opacity = 0.3, spin = 0.5, fade = 8, style}) => {
  const {palette, preset} = useTheme(); const frame = useClock(); const {width, height} = useVideoConfig(); const density = usePixelDensity();
  if (preset === 'product' || frame < at || frame > at + len) return null;
  const o = Math.min(opacity, 0.35) * ramp(frame, at, at + fade, 0, 1, EASE_IO) * ramp(frame, at + len - fade, at + len, 1, 0, EASE_IO);
  const k = ramp(frame, at, at + fade, 0.6, 1, EASE_IO);
  const mask = `radial-gradient(circle at ${x}px ${y}px, rgba(0,0,0,1) 0px, rgba(0,0,0,0.5) ${Math.round(radius * 0.45)}px, rgba(0,0,0,0) ${radius}px)`;
  return <Solid width={width} height={height} pixelDensity={density} style={{position: 'absolute', left: 0, top: 0, opacity: o, pointerEvents: 'none', maskImage: mask, WebkitMaskImage: mask, transform: `scale(${k.toFixed(4)})`, transformOrigin: `${x}px ${y}px`, ...style}} effects={[starburst({rays: Math.max(2, Math.min(rays, 100)), colors: colors ?? [palette.accent, palette.bg], rotation: (frame - at) * spin, smoothness: 0.12, origin: [x / width, y / height]})]} />;
};

/** Motion trail (impact only): the children are drawn `layers` extra times, each lagging `lag` frames at falling opacity. Children must be absolutely positioned.
 * Kit parts inside keep their ShotClock — each layer re-derives the shot frame from its lag. Product preset: children pass through untouched. */
export const Trail: React.FC<{layers?: number; lag?: number; opacity?: number; children: React.ReactNode}> = ({layers = 5, lag = 0.7, opacity = 0.45, children}) => {
  const {preset} = useTheme(); const real = useCurrentFrame(); const ctx = useShotClockValue();
  if (preset === 'product') return <>{children}</>;
  return <MotionTrail layers={Math.max(0, Math.min(Math.round(layers), 6))} lagInFrames={lag} trailOpacity={Math.min(opacity, 0.6)}><ClockShift base={real} ctx={ctx}>{children}</ClockShift></MotionTrail>;
};
const ClockShift: React.FC<{base: number; ctx: number | null; children: React.ReactNode}> = ({base, ctx, children}) => {
  const shifted = useCurrentFrame();
  if (ctx === null) return <>{children}</>;
  return <ShotClock frame={ctx + (shifted - base)}>{children}</ShotClock>;
};
