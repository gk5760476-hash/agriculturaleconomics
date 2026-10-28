export type Cam = [number, number, number];

export type Word = {text: string; start: number; end: number};

export type Line = {
	who: string;
	name: string;
	color: string;
	audio: string;
	from: number;
	duration: number;
	// Spoken live by the presenter: the line keeps its time but has no audio or caption.
	silent?: boolean;
	// Lip-synced takes; `from` is relative to the line start.
	lips?: {src: string; from: number; duration: number; aspect: number}[];
	pages: Word[][];
};

export type Shot = {
	img?: string;
	card?: string;
	cam?: {from: Cam; to: Cam};
	fit?: 'cover' | 'contain';
	sfx?: string;
	// Ambience bed (public/sfx/amb_<name>.wav), looped under the shot.
	amb?: string;
	aspect?: number;
	clip?: string;
	clipLast?: string;
	clipFreeze?: string;
	clipDuration?: number;
	clipAspect?: number;
	clipRate?: number;
	clipStart?: number;
	from: number;
	duration: number;
	lines: Line[];
};

export type Timeline = {
	id: string;
	title: string;
	subtitle: string;
	fps: number;
	durationInFrames: number;
	shots: Shot[];
};
