import React from 'react';
import {
	AbsoluteFill,
	Audio,
	Easing,
	Img,
	OffthreadVideo,
	Sequence,
	interpolate,
	staticFile,
	useCurrentFrame,
} from 'remotion';
import {loadFont as loadBebas} from '@remotion/google-fonts/BebasNeue';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {Captions} from './Captions';
import type {Cam, Shot, Timeline} from './types';

const {fontFamily: bebas} = loadBebas();
const {fontFamily: inter} = loadInter('normal', {weights: ['400', '600'], subsets: ['latin']});

const W = 1280;
const H = 720;
const FPS = 30;
const XFADE = 12; // frames each shot overlaps the previous one

const ease = Easing.inOut(Easing.cubic);

// Place the image so image point (cx, cy) sits at frame centre at the given zoom, never showing an edge.
const coverRect = (aspect: number, [cx, cy, zoom]: Cam) => {
	const baseW = aspect > W / H ? H * aspect : W;
	const baseH = aspect > W / H ? H : W / aspect;
	const w = baseW * zoom;
	const h = baseH * zoom;
	const left = Math.min(0, Math.max(W - w, W / 2 - cx * w));
	const top = Math.min(0, Math.max(H - h, H / 2 - cy * h));
	return {left, top, width: w, height: h};
};

// A lip-synced take plays at 1x for exactly its part of the line, dissolving in and out of the base clip.
const LipTake: React.FC<{src: string; duration: number; rect: React.CSSProperties}> = ({src, duration, rect}) => {
	const frame = useCurrentFrame();
	const opacity = interpolate(frame, [0, 4, duration - 4, duration], [0, 1, 1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	return <OffthreadVideo src={staticFile(src)} muted style={{...rect, opacity}} />;
};

const ImageShot: React.FC<{shot: Shot}> = ({shot}) => {
	const frame = useCurrentFrame();
	const t = ease(Math.min(1, frame / (shot.duration + XFADE)));
	const from = shot.cam?.from ?? [0.5, 0.5, 1];
	const to = shot.cam?.to ?? from;
	const cam = from.map((v, i) => v + (to[i] - v) * t) as Cam;
	const src = staticFile(`img/${shot.img}.jpg`);
	const aspect = shot.aspect ?? 16 / 9;

	if (shot.clip && shot.clipLast && shot.clipDuration) {
		const rate = shot.clipRate ?? 1;
		const start = shot.clipStart ?? 0;
		const rect = {position: 'absolute' as const, ...coverRect(shot.clipAspect ?? aspect, cam)};
		// Frames of this shot the remaining clip can fill at this playback rate.
		const playable = Math.max(0, Math.floor(((shot.clipDuration - start - 0.05) / rate) * FPS));
		return (
			<AbsoluteFill>
				<Img src={staticFile(shot.clipLast)} style={rect} />
				{playable > 0 ? (
					<Sequence durationInFrames={playable}>
						<OffthreadVideo
							src={staticFile(shot.clip)}
							muted
							playbackRate={rate}
							startFrom={Math.round(start * FPS)}
							style={rect}
						/>
					</Sequence>
				) : null}
				{shot.lines.flatMap((l) =>
					(l.lips ?? []).map((p) => (
						<Sequence key={p.src} from={l.from - shot.from + p.from} durationInFrames={p.duration}>
							<LipTake src={p.src} duration={p.duration} rect={{position: 'absolute', ...coverRect(p.aspect, cam)}} />
						</Sequence>
					)),
				)}
				{shot.clipFreeze ? <Img src={staticFile(shot.clipFreeze)} style={rect} /> : null}
			</AbsoluteFill>
		);
	}

	if (shot.fit === 'contain') {
		const h = Math.min(H, W / aspect) * cam[2];
		return (
			<AbsoluteFill>
				<Img src={src} style={{...coverRect(aspect, [0.5, 0.5, 1.1]), position: 'absolute', filter: 'blur(28px) brightness(0.5)'}} />
				<Img src={src} style={{position: 'absolute', height: h, width: h * aspect, left: (W - h * aspect) / 2, top: (H - h) / 2}} />
			</AbsoluteFill>
		);
	}
	return <Img src={src} style={{position: 'absolute', ...coverRect(aspect, cam)}} />;
};

const Card: React.FC<{text: string; duration: number}> = ({text, duration}) => {
	const frame = useCurrentFrame();
	const scale = interpolate(frame, [0, duration], [1.04, 1], {extrapolateRight: 'clamp'});
	const long = text.length > 40;
	return (
		<AbsoluteFill
			style={{
				background: 'radial-gradient(ellipse at center, #1a1612 0%, #050403 75%)',
				justifyContent: 'center',
				alignItems: 'center',
				padding: '0 60px 90px',
			}}
		>
			<div
				style={{
					fontFamily: long ? inter : bebas,
					fontWeight: long ? 600 : 400,
					fontSize: long ? (text === text.toUpperCase() ? 36 : 42) : 150,
					maxWidth: 1120,
					lineHeight: long ? 1.35 : 0.95,
					letterSpacing: long ? 0.5 : 4,
					textAlign: 'center',
					whiteSpace: 'pre-line',
					transform: `scale(${scale})`,
					background: 'linear-gradient(180deg, #fbe7a6 0%, #e2b45a 55%, #a8772c 100%)',
					WebkitBackgroundClip: 'text',
					color: 'transparent',
					filter: 'drop-shadow(0 4px 18px rgba(0,0,0,0.8))',
				}}
			>
				{text}
			</div>
		</AbsoluteFill>
	);
};

// Dissolving between two framings of the same picture ghosts it, so those shots cut instead.
const ShotLayer: React.FC<{shot: Shot; first: boolean; cut: boolean}> = ({shot, first, cut}) => {
	const frame = useCurrentFrame();
	const opacity = first || cut ? 1 : interpolate(frame, [0, XFADE], [0, 1], {extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{opacity, backgroundColor: '#000'}}>
			{shot.card ? <Card text={shot.card} duration={shot.duration} /> : <ImageShot shot={shot} />}
		</AbsoluteFill>
	);
};

const EpisodeChip: React.FC<{timeline: Timeline}> = ({timeline}) => {
	const frame = useCurrentFrame();
	const opacity = interpolate(frame, [10, 30, 130, 160], [0, 1, 1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	return (
		<div
			style={{
				position: 'absolute',
				top: 28,
				left: 34,
				opacity,
				fontFamily: inter,
				color: '#f3e6c4',
				textShadow: '0 2px 8px rgba(0,0,0,0.9)',
			}}
		>
			<div style={{fontSize: 15, letterSpacing: 3, textTransform: 'uppercase', opacity: 0.8}}>
				Episode {Number(timeline.id.slice(2))} · {timeline.subtitle}
			</div>
			<div style={{fontSize: 26, fontWeight: 600}}>{timeline.title}</div>
		</div>
	);
};

const AMB_FADE = 20;

// Consecutive shots with the same ambience share one looping bed that fades at its edges.
const ambienceRuns = (shots: Shot[]) => {
	const runs: {amb: string; from: number; to: number}[] = [];
	for (const s of shots) {
		const prev = runs[runs.length - 1];
		if (s.amb && prev && prev.amb === s.amb && prev.to === s.from) prev.to = s.from + s.duration;
		else if (s.amb) runs.push({amb: s.amb, from: s.from, to: s.from + s.duration});
	}
	return runs;
};

// Each episode rises from and falls to black, so the joined film dips to black between episodes.
const EDGE_FADE = 15;

const EdgeFade: React.FC<{duration: number}> = ({duration}) => {
	const frame = useCurrentFrame();
	const opacity = interpolate(frame, [0, EDGE_FADE, duration - EDGE_FADE, duration], [1, 0, 0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	return <AbsoluteFill style={{backgroundColor: '#000', opacity}} />;
};

export const Episode: React.FC<{timeline: Timeline}> = ({timeline}) => {
	const last = timeline.shots.length - 1;
	return (
		<AbsoluteFill style={{backgroundColor: '#000'}}>
			{timeline.shots.map((shot, i) => (
				<Sequence key={i} from={shot.from} durationInFrames={shot.duration + (i < last ? XFADE : 0)}>
					<ShotLayer shot={shot} first={i === 0} cut={!!shot.img && shot.img === timeline.shots[i - 1]?.img} />
				</Sequence>
			))}
			{/* Vignette over every shot */}
			<AbsoluteFill
				style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)'}}
			/>
			{ambienceRuns(timeline.shots).map((r) => {
				const len = r.to - r.from + XFADE;
				return (
					<Sequence key={`amb${r.from}`} from={r.from} durationInFrames={len}>
						<Audio
							src={staticFile(`sfx/amb_${r.amb}.wav`)}
							loop
							volume={(f) =>
								interpolate(f, [0, AMB_FADE, len - AMB_FADE, len], [0, 1, 1, 0], {
									extrapolateLeft: 'clamp',
									extrapolateRight: 'clamp',
								})
							}
						/>
					</Sequence>
				);
			})}
			{timeline.shots.flatMap((shot, i) => [
				...(shot.sfx
					? [
							<Sequence key={`sfx${i}`} from={shot.from}>
								<Audio src={staticFile(`sfx/${shot.sfx}.wav`)} volume={0.6} />
							</Sequence>,
						]
					: []),
				...shot.lines.filter((line) => !line.silent).map((line, j) => (
					<Sequence key={`a${i}-${j}`} from={line.from} durationInFrames={line.duration}>
						<Audio src={staticFile(line.audio)} />
					</Sequence>
				)),
			])}
			<Captions lines={timeline.shots.flatMap((s) => s.lines).filter((l) => !l.silent)} fontFamily={inter} />
			<EpisodeChip timeline={timeline} />
			<EdgeFade duration={timeline.durationInFrames} />
		</AbsoluteFill>
	);
};
