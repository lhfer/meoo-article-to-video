/**
 * kit/cursor.tsx — a real macOS cursor (@remotion/mac-cursors) following a path of shot-local frames; the hand pointer shows around each click,
 * with the same ripple as CursorTrail. Product preset default for screen recordings and prompt → result shots; impact may use it in evidence shots.
 */
import React from 'react';
import {MacOSCursor} from '@remotion/mac-cursors';
import {EASE_IO, progress, ramp, rgba, useTheme} from './core';
import {useClock} from './clock';

export const MacCursorTrail: React.FC<{path: Array<{x: number; y: number; at: number}>; clicks?: number[]; cursor?: string; scale?: number; color?: string}> = ({path, clicks = [], cursor = 'default', scale = 1.6, color}) => {
  const {palette} = useTheme(); const frame = useClock(); const col = color ?? palette.accent;
  if (!path.length || frame < path[0].at) return null;
  let x = path[path.length - 1].x; let y = path[path.length - 1].y;
  for (let i = 0; i < path.length - 1; i++) {
    const a = path[i]; const b = path[i + 1];
    if (frame >= a.at && frame < b.at) { x = ramp(frame, a.at, b.at, a.x, b.x, EASE_IO); y = ramp(frame, a.at, b.at, a.y, b.y, EASE_IO); break; }
  }
  const near = clicks.find((c) => frame >= c - 8 && frame <= c + 16);
  const press = near === undefined ? 0 : progress(frame, near, 4) * (1 - progress(frame, near + 4, 6));
  return (
    <>
      {clicks.map((c, i) => { const p = progress(frame, c, 14); return p > 0 && p < 1 ? <div key={i} style={{position: 'absolute', left: x - 30 * p, top: y - 30 * p, width: 60 * p, height: 60 * p, borderRadius: '50%', border: `2px solid ${rgba(col, 1 - p)}`, pointerEvents: 'none'}} /> : null; })}
      <MacOSCursor cursor={near === undefined ? cursor : 'pointer'} style={{left: x, top: y, scale: (scale * (1 - 0.12 * press)).toFixed(3), pointerEvents: 'none'}} />
    </>
  );
};
