/** kit/media.tsx — stills, clip playback with cuts/holds, Ken Burns, circle wipe, RGB split. */
import React from 'react';
import {Freeze, Img, OffthreadVideo, Sequence, staticFile, useVideoConfig} from 'remotion';
import {Video} from '@remotion/media';
import {EASE_IO, EASE_SOFT, ramp} from './core';
import {useClock} from './clock';

type CSS = React.CSSProperties;
export const fill: CSS = {width: '100%', height: '100%', display: 'block', objectFit: 'fill'};

/** A registered image at its natural fit. */
export const Still: React.FC<{src: string; style?: CSS}> = ({src, style}) => <Img src={staticFile(src)} style={{...fill, ...style}} />;

export type Seg = {from: number; to: number; at: number; rate?: number; hold?: boolean};
/** Cuts and speed changes on one source clip; `hold` freezes a single source frame. Frames are shot-local. */
export const Clip: React.FC<{src: string; segs: Seg[]; muted?: boolean; style?: CSS}> = ({src, segs, muted = true, style}) => {
  const {fps} = useVideoConfig(); const file = staticFile(src);
  return (
    <>
      {segs.map((s, i) => {
        const d = Math.round(s.to - s.from); if (d <= 0) return null;
        const trimBefore = Math.max(0, Math.round(s.at * fps));
        return (
          <Sequence key={i} from={Math.round(s.from)} durationInFrames={d} layout="none">
            {s.hold ? <Freeze frame={0}><OffthreadVideo src={file} trimBefore={trimBefore} muted style={{...fill, ...style}} /></Freeze>
              : <Video src={file} trimBefore={trimBefore} playbackRate={s.rate ?? 1} muted={muted} style={{...fill, ...style}} />}
          </Sequence>
        );
      })}
    </>
  );
};

/** Slow push/pan on a still: zoom from→to and focus drift over `frames` (product default), inside an overflow-hidden box. */
export const KenBurns: React.FC<{src: string; at?: number; frames?: number; zoom?: [number, number]; from?: {x: number; y: number}; to?: {x: number; y: number}; style?: CSS}> = ({src, at = 0, frames = 150, zoom = [1.04, 1.12], from = {x: 50, y: 50}, to = {x: 50, y: 50}, style}) => {
  const frame = useClock(); const k = ramp(frame, at, at + frames, zoom[0], zoom[1], EASE_SOFT);
  const x = ramp(frame, at, at + frames, from.x, to.x, EASE_SOFT); const y = ramp(frame, at, at + frames, from.y, to.y, EASE_SOFT);
  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden', ...style}}><Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: `${x}% ${y}%`, transform: `scale(${k.toFixed(4)})`}} /></div>;
};

/** Circular reveal of children from (x, y); use at most once per film. */
export const CircleWipe: React.FC<{at: number; len: number; x: number; y: number; radius: number; children: React.ReactNode}> = ({at, len, x, y, radius, children}) => {
  const frame = useClock(); const p = ramp(frame, at, at + len, 0, 1, EASE_IO);
  if (p <= 0) return null;
  return <div style={{position: 'absolute', inset: 0, clipPath: `circle(${radius * p}px at ${x}px ${y}px)`}}>{children}</div>;
};

/** Children rendered three times as R/G/B channels screened together with a horizontal offset (≤ 14 px, decay within 7 frames). */
export const RgbSplit: React.FC<{amount: number; children: React.ReactNode}> = ({amount, children}) => {
  if (amount <= 0.3) return <>{children}</>;
  const a = Math.min(amount, 14);
  const channels = [['kitR', -1, '1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0'], ['kitG', 0, '0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0'], ['kitB', 1, '0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0']] as const;
  return (
    <div style={{position: 'absolute', inset: 0, background: '#000', isolation: 'isolate'}}>
      <svg width="0" height="0" style={{position: 'absolute'}}><defs>{channels.map(([id, , values]) => <filter key={id} id={id} colorInterpolationFilters="sRGB"><feColorMatrix type="matrix" values={values} /></filter>)}</defs></svg>
      {channels.map(([id, dir]) => <div key={id} style={{position: 'absolute', inset: 0, mixBlendMode: 'screen', transform: `translateX(${dir * a}px)`, filter: `url(#${id})`}}>{children}</div>)}
    </div>
  );
};
