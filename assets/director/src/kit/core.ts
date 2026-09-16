/**
 * kit/core.ts — theme, easing, progress helpers and layout readers shared by every kit component.
 * Colors and fonts come ONLY from useTheme() (film.style.palette / film.style.fontRoles); nothing here is hard-coded per film.
 */
import React from 'react';
import {Easing, interpolate} from 'remotion';

export type Palette = {
  bg: string; bg2: string; accent: string; accentBright: string; secondary: string; warm: string;
  white: string; muted: string; red: string; gold: string; paper: string; ink: string;
};
export type Fonts = {display: string; sans: string; body: string};
export type Preset = 'impact' | 'product';
export type Theme = {palette: Palette; fonts: Fonts; weights: {black: number; bold: number}; preset: Preset};

/** Default look (deep navy + electric blue). A film overrides any key through film.style.palette. */
export const DEFAULT_THEME: Theme = {
  palette: {
    bg: '#070b14', bg2: '#0d1526', accent: '#3b7bff', accentBright: '#8fb4ff', secondary: '#2fd6c8', warm: '#ff9a3c',
    white: '#f4f6fb', muted: '#8a94ad', red: '#ff3b5c', gold: '#f2c14e', paper: '#f3f4f6', ink: '#101a2e',
  },
  fonts: {
    display: '"NotoSansSC","Noto Sans CJK SC","PingFang SC",sans-serif',
    sans: '"NotoSansSC","Noto Sans CJK SC","PingFang SC","Microsoft YaHei",sans-serif',
    body: '"NotoSansSC","Noto Sans CJK SC","PingFang SC","Microsoft YaHei",sans-serif',
  },
  weights: {black: 900, bold: 700},
  preset: 'impact',
};

/** Product preset: light paper, single accent, restrained motion. */
export const PRODUCT_PALETTE: Partial<Palette> = {
  bg: '#f6f7f9', bg2: '#ffffff', accent: '#3a6ff2', accentBright: '#6b93ff', secondary: '#1fb6a8', warm: '#f28b3a',
  white: '#0f172a', muted: '#6b7280', red: '#e5484d', gold: '#d59f1a', paper: '#ffffff', ink: '#0f172a',
};

export function themeFromStyle(style: Record<string, unknown> | undefined): Theme {
  const s = style ?? {};
  const preset = (s.preset === 'product' ? 'product' : 'impact') as Preset;
  const base = preset === 'product' ? {...DEFAULT_THEME.palette, ...PRODUCT_PALETTE} : DEFAULT_THEME.palette;
  const palette = {...base, ...((s.palette as Partial<Palette>) ?? {})};
  const roles = (s.fontRoles as Partial<Fonts>) ?? {};
  const family = typeof s.fontFamily === 'string' ? s.fontFamily : undefined;
  const fonts: Fonts = {
    display: roles.display ?? DEFAULT_THEME.fonts.display,
    sans: roles.sans ?? family ?? DEFAULT_THEME.fonts.sans,
    body: roles.body ?? family ?? DEFAULT_THEME.fonts.body,
  };
  return {palette, fonts, weights: DEFAULT_THEME.weights, preset};
}

const ThemeCtx = React.createContext<Theme>(DEFAULT_THEME);
export const ThemeProvider: React.FC<{style: Record<string, unknown>; children: React.ReactNode}> = ({style, children}) => {
  const theme = React.useMemo(() => themeFromStyle(style), [style]);
  return React.createElement(ThemeCtx.Provider, {value: theme}, children);
};
export const useTheme = (): Theme => React.useContext(ThemeCtx);

/** hex (#rgb/#rrggbb) → rgba() string. */
export const rgba = (hex: string, a: number): string => {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  const n = parseInt(full.slice(0, 6), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

/** Translucent panel/line colors derived from the palette. */
export const tintOf = (t: Theme) => ({
  panel: rgba(t.palette.bg2, 0.82), panelSolid: rgba(t.palette.bg, 0.94), panelLight: rgba(t.palette.paper, 0.95),
  line: rgba(t.palette.accent, 0.55), lineSoft: rgba(t.palette.accentBright, 0.28), lineLight: rgba(t.palette.ink, 0.22),
  inner: `inset 0 1px 0 ${rgba(t.palette.accentBright, 0.12)}, inset 0 -18px 40px ${rgba(t.palette.bg, 0.55)}`,
  glow: `0 18px 60px ${rgba(t.palette.bg, 0.65)}`,
});

export const TABULAR = {fontVariantNumeric: 'tabular-nums' as const, fontFeatureSettings: '"tnum" 1'};

/* ---------------------------------------------------------------- easing */
export const EASE = Easing.bezier(0.16, 1, 0.3, 1);       // apple-ish ease-out
export const EASE_IO = Easing.bezier(0.65, 0, 0.35, 1);
export const EASE_SOFT = Easing.bezier(0.22, 1, 0.36, 1);
export const SPRING = {
  snap: {damping: 200, stiffness: 220, mass: 0.7},   // lands, no bounce: big type, hard cuts, cards
  soft: {damping: 200, stiffness: 100, mass: 1},     // gentle push: images, panels
  pop: {damping: 15, stiffness: 190, mass: 0.6},     // a little bounce: chips, stamps
  calm: {damping: 190, stiffness: 120, mass: 0.9},   // product preset default (no overshoot)
} as const;

/** frame in [a,b] → from..to, clamped, ease-out by default. */
export const ramp = (frame: number, a: number, b: number, from: number, to: number, easing = EASE): number =>
  interpolate(frame, [a, Math.max(a + 1, b)], [from, to], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing});
/** 0→1 progress over `frames` starting at `at`. */
export const progress = (frame: number, at: number, frames: number): number =>
  frames <= 0 ? (frame >= at ? 1 : 0) : Math.min(1, Math.max(0, (frame - at) / frames));
/** 1→0 inside [at, at+len), else 0 (flashes, shakes). */
export const pulse = (frame: number, at: number, len: number): number =>
  frame < at || frame >= at + len ? 0 : 1 - (frame - at) / len;
/** Deterministic jitter in [-1,1) — never Math.random. */
export const jitter = (frame: number, seed: number): number => {
  const x = Math.sin((frame + 1) * 12.9898 + seed * 78.233) * 43758.5453;
  return (x - Math.floor(x)) * 2 - 1;
};
export const group1000 = (n: number): string => {
  const s = Math.round(Math.abs(n)).toString();
  return (n < 0 ? '-' : '') + s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
};
/** style.opacity multiplies the component's own entrance fade instead of overriding it. */
export const mulOpacity = (style: React.CSSProperties | undefined, own: number): number =>
  typeof style?.opacity === 'number' ? style.opacity * own : own;

/* ------------------------------------------------------- layout readers */
export type Rect = {x: number; y: number; w: number; h: number};
export type Box = {w: number; h: number};
export const num = (l: Record<string, unknown>, key: string, fallback: number): number => (typeof l[key] === 'number' ? (l[key] as number) : fallback);
export const str = (l: Record<string, unknown>, key: string, fallback: string): string => (typeof l[key] === 'string' ? (l[key] as string) : fallback);
export const lines = (l: Record<string, unknown>, key: string): string[] => (Array.isArray(l[key]) ? (l[key] as string[]) : []);
export const box = <T extends Record<string, number>>(l: Record<string, unknown>, key: string, fallback: T): T => {
  const v = l[key];
  return v && typeof v === 'object' ? {...fallback, ...(v as Partial<T>)} : fallback;
};
export const rect = (l: Record<string, unknown>, key: string, fallback: Rect): Rect => {
  const v = l[key];
  if (Array.isArray(v) && v.length === 4 && v.every((x) => typeof x === 'number')) return {x: v[0] as number, y: v[1] as number, w: v[2] as number, h: v[3] as number};
  return box(l, key, fallback);
};
/** Per-format constant without repeating it in every layout object. */
export const pick = <T,>(format: string, three: T, nine: T, wide: T): T => (format === '9x16' ? nine : format === '16x9' ? wide : three);
