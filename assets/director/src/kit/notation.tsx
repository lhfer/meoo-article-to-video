/**
 * kit/notation.tsx — hand-drawn annotations (@remotion/rough-notation): underline / circle / highlight / box / bracket / strike on the wrapped text.
 * Draws from `at` over `len` frames on the shot clock. Wrap settled text (a Display, a claim line, a metric): wrapping a Slam mid-transform makes the
 * stroke chase the scale/skew. Both presets: impact = thick rough double strokes in accentBright, product = thin single strokes in accent. One per screen at a time.
 */
import React from 'react';
import {Box, Bracket, Circle, Highlight, StrikeThrough, Underline} from '@remotion/rough-notation';
import {EASE_IO, ramp, rgba, useTheme} from './core';
import {useClock} from './clock';

export type NoteKind = 'underline' | 'circle' | 'highlight' | 'box' | 'bracket' | 'strike';
type Pad = {left?: number; right?: number; top?: number; bottom?: number};
export const Note: React.FC<{kind?: NoteKind; at: number; len?: number; color?: string; width?: number; seed?: number; padding?: Pad; style?: React.CSSProperties; children: React.ReactNode}> = ({kind = 'underline', at, len, color, width, seed = 7, padding, style, children}) => {
  const {palette, preset} = useTheme(); const frame = useClock(); const impact = preset === 'impact';
  const p = ramp(frame, at, at + (len ?? (impact ? 10 : 14)), 0, 1, EASE_IO);
  const col = color ?? (kind === 'highlight' ? rgba(palette.gold, impact ? 0.5 : 0.35) : impact ? palette.accentBright : palette.accent);
  const stroke = width ?? (impact ? 10 : 4);
  const common = {progress: p, disabled: frame < at, seed, color: col, roughness: impact ? 1.6 : 0.8, bowing: impact ? 1 : 0.4, disableMultiStroke: !impact, style};
  const iterations = impact ? 2 : 1;
  switch (kind) {
    case 'circle': return <Circle {...common} iterations={iterations} strokeWidth={stroke} padding={{left: 14, right: 14, top: 8, bottom: 8, ...padding}}>{children}</Circle>;
    case 'highlight': return <Highlight {...common} iterations={iterations} padding={{left: 6, right: 6, ...padding}}>{children}</Highlight>;
    case 'box': return <Box {...common} iterations={iterations} strokeWidth={stroke} padding={{left: 10, right: 10, top: 6, bottom: 6, ...padding}}>{children}</Box>;
    case 'bracket': return <Bracket {...common} strokeWidth={stroke} bracketLeft bracketRight padding={{left: 8, right: 8, ...padding}}>{children}</Bracket>;
    case 'strike': return <StrikeThrough {...common} iterations={iterations} strokeWidth={stroke}>{children}</StrikeThrough>;
    default: return <Underline {...common} iterations={iterations} strokeWidth={stroke} padding={{top: padding?.top ?? 4}}>{children}</Underline>;
  }
};
