export type Format = '3x4'|'9x16'|'16x9';
export type Shot = {id:string;component:string;from:number;end:number;durationFrames:number;transitionIn:{type:string;frames:number};props?:Record<string,unknown>;layouts:Record<Format,Record<string,unknown>>;assets?:string[];viewerGain?:string;anchor?:string;hold?:string;bespoke?:string};
export type ShotProps = {shot:Shot;format:Format;layout:Record<string,unknown>;events:Record<string,number>;style:Record<string,unknown>;cue:(name:string)=>number;asset:(id:string)=>string;};
export type Word = {text:string;startMs:number;endMs:number};
export type CaptionWord = {text:string;from:number;end:number};
export type Caption = {text:string;from:number;end:number;voice?:string;words?:CaptionWord[]};
export type Voice = {id:string;src:string;from:number;durationFrames:number;gain:number;real:boolean;words?:Word[];gapIntent?:{reason:string}};
export type Timeline = {draft:boolean;fps:number;durationFrames:number;formats:Partial<Record<Format,{width:number;height:number}>>;primaryFormat?:Format;events:Record<string,number>;style:Record<string,unknown>;assets:Record<string,{src:string}>;globalAssets:string[];shots:Shot[];captionStyle:Record<string,unknown>;captions:Caption[];voices:Voice[];audio:Array<{src:string;from:number;end:number;durationFrames:number;trimStart:number;gain:number;fadeIn:number;fadeOut:number;duck?:number}>;voiceGaps?:Array<{after:string;before:string;frames:number;seconds:number;intentional:string|null}>;leadSilenceSeconds?:number;trailingSilenceSeconds?:number};
