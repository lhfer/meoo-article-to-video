import React from 'react';
import {Composition} from 'remotion';
import timeline from '../content/timeline.json';
import {Film} from './Film';
import type {Format} from './types';
export const Root:React.FC=()=> <>{(Object.keys(timeline.formats) as Format[]).map(format=><Composition key={format} id={`Film-${format}`} component={Film} fps={timeline.fps} durationInFrames={timeline.durationFrames} width={timeline.formats[format].width} height={timeline.formats[format].height} defaultProps={{format}}/>)}</>;
