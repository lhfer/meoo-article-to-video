/**
 * kit/clock.tsx — the shot clock and hit-stop (impact preset).
 * A hit-stop freezes the SHOT's own time for `hold` frames at each hit and shifts later events by the same amount,
 * so word-anchored actions still land on the audio. Background layers and captions live outside the shot and keep moving.
 * Rules: use hitClock() for every hit-stop shot; pass c('event') (shifted) to component `at`s; pass back(v) + the REAL
 * frame to Flash/useShake so full-screen effects do not freeze white across the hold.
 */
import React from 'react';
import {useCurrentFrame} from 'remotion';

const ClockCtx = React.createContext<number | null>(null);
/** Wrap the shot JSX so kit components read the remapped frame instead of useCurrentFrame(). */
export const ShotClock: React.FC<{frame: number; children: React.ReactNode}> = ({frame, children}) => (
  <ClockCtx.Provider value={frame}>{children}</ClockCtx.Provider>
);
/** The frame kit components animate on: the ShotClock frame when provided, else the live frame. */
export const useClock = (): number => {
  const live = useCurrentFrame();
  const ctx = React.useContext(ClockCtx);
  return ctx ?? live;
};

/** Hold time for `hold` frames at each of `ats`, then continue. Events inside (hit, hit+hold) snap to the hit. */
export const hitStop = (frame: number, ats: number | number[], hold = 3): number => {
  const list = (Array.isArray(ats) ? ats : [ats]).slice().sort((a, b) => a - b);
  let f = frame;
  for (const at of list) {
    if (frame >= at + hold) f -= hold;
    else if (frame > at) f = at;
  }
  return f;
};

/**
 * One consistent clock for a hit-stop shot.
 * ```tsx
 * const real = useCurrentFrame();
 * const {f, c, back} = hitClock(real, cue, [['hook.王炸', 4]], 3);   // +4: let the big type land before the hold
 * return <ShotClock frame={f}><Slam at={c('hook.王炸')} …/><Flash at={back(c('hook.王炸'))} frame={real}/></ShotClock>;
 * ```
 */
export const hitClock = (
  frame: number,
  cue: (name: string) => number,
  hits: Array<string | [string, number]>,
  hold = 3,
): {f: number; c: (name: string) => number; shift: (v: number) => number; back: (v: number) => number; hold: number} => {
  const hitFrames = hits.map((h) => (typeof h === 'string' ? cue(h) : cue(h[0]) + h[1])).sort((a, b) => a - b);
  const f = hitStop(frame, hitFrames, hold);
  const shift = (v: number) => hitStop(v, hitFrames, hold);
  const back = (v: number) => v + hold * hitFrames.filter((h) => shift(h) < v).length;
  return {f, c: (name: string) => shift(cue(name)), shift, back, hold};
};

/** The raw ShotClock value (null outside a ShotClock): fx.tsx re-derives a lagged shot frame per Trail layer. */
export const useShotClockValue = (): number | null => React.useContext(ClockCtx);
