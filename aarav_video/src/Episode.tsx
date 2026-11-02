import React from 'react';
import {
	AbsoluteFill,
	Audio,
	Easing,
	Img,
	OffthreadVideo,
	Sequence,
	interpolate,
	random,
	staticFile,
	useCurrentFrame,
} from 'remotion';
import {Captions} from './Captions';
import {DepthShot} from './DepthShot';
import {bebas, inter} from './fonts';
import type {Cam, Shot, Timeline} from './types';

const W = 1280;
const H = 720;
const FPS = 30;
const XFADE = 12; // frames each shot overlaps the previous one

const ease = Easing.inOut(Easing.cubic);
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// One warm, slightly richer grade over every picture so comic panels and photo plates sit together.
const GRADE = 'contrast(1.05) saturate(1.07) sepia(0.05) brightness(1.01)';

// Gentle handheld drift (CSS px, degrees) from a few slow incommensurate sines: alive, never shaky.
const handheld = (f: number) => ({
	x: 2.2 * Math.sin(f / 70) + 1.1 * Math.sin(f / 29 + 1.3),
	y: 1.6 * Math.sin(f / 83 + 0.7) + 0.9 * Math.sin(f / 37 + 2.1),
	r: 0.09 * Math.sin(f / 101 + 0.4),
});

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

	if (shot.depth) {
		return (
			<DepthShot
				img={`img/${shot.img}.jpg`}
				depth={shot.depth}
				cam={cam}
				start={from}
				t={t}
				width={W}
				height={H}
				cover={coverRect}
			/>
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

const GOLD = 'linear-gradient(180deg, #fbe7a6 0%, #e2b45a 55%, #a8772c 100%)';

// Title card: letters (or words, for long cards) rise in one after another, then a light sheen sweeps
// across the gold; thin rules draw out from the centre.
const Card: React.FC<{text: string; duration: number}> = ({text, duration}) => {
	const frame = useCurrentFrame();
	const long = text.length > 40;
	const scale = interpolate(frame, [0, duration], [1.035, 1], clamp);
	const font: React.CSSProperties = {
		fontFamily: long ? inter : bebas,
		fontWeight: long ? 600 : 400,
		fontSize: long ? (text === text.toUpperCase() ? 36 : 42) : 150,
		lineHeight: long ? 1.35 : 0.95,
		letterSpacing: long ? 0.5 : 4,
		textAlign: 'center',
		whiteSpace: 'pre-line',
	};
	const units = long ? text.split(/(\s+)/) : Array.from(text);
	const step = long ? 1.6 : 2.2;
	let n = 0;
	const pieces = units.map((u, i) => {
		if (!u || /^\s+$/.test(u)) return u;
		const at = 4 + n++ * step;
		const p = interpolate(frame, [at, at + 10], [0, 1], clamp);
		return (
			<span
				key={i}
				style={{
					display: 'inline-block',
					opacity: p,
					transform: `translateY(${(1 - p) * 16}px)`,
					filter: p < 1 ? `blur(${(1 - p) * 4}px)` : undefined,
					background: GOLD,
					WebkitBackgroundClip: 'text',
					color: 'transparent',
				}}
			>
				{u}
			</span>
		);
	});
	const revealed = 4 + n * step + 10;
	const sheen = interpolate(frame, [revealed, revealed + 28], [130, -30], clamp);
	const rule = interpolate(frame, [2, 26], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
	const glowX = 50 + 6 * Math.sin(frame / 40);
	const line: React.CSSProperties = {
		height: 1,
		width: 420 * rule,
		background: 'linear-gradient(90deg, transparent, #e2b45a, transparent)',
		opacity: 0.8,
	};
	return (
		<AbsoluteFill
			style={{
				background: `radial-gradient(ellipse at ${glowX}% 46%, #221b13 0%, #0b0907 45%, #040302 78%)`,
				justifyContent: 'center',
				alignItems: 'center',
				padding: '0 60px 90px',
			}}
		>
			<div style={{transform: `scale(${scale})`, display: 'flex', flexDirection: 'column', alignItems: 'center', maxWidth: 1120}}>
				<div style={{...line, marginBottom: long ? 26 : 30}} />
				<div style={{display: 'grid', filter: 'drop-shadow(0 4px 18px rgba(0,0,0,0.8))'}}>
					<div style={{...font, gridArea: '1 / 1'}}>{pieces}</div>
					{frame >= revealed ? (
						<div
							aria-hidden
							style={{
								...font,
								gridArea: '1 / 1',
								background: 'linear-gradient(105deg, transparent 42%, rgba(255,248,225,0.85) 50%, transparent 58%)',
								backgroundSize: '250% 100%',
								backgroundPosition: `${sheen}% 0`,
								WebkitBackgroundClip: 'text',
								color: 'transparent',
							}}
						>
							{text}
						</div>
					) : null}
				</div>
				<div style={{...line, marginTop: long ? 26 : 22}} />
			</div>
		</AbsoluteFill>
	);
};

// Warm motes drifting through the light in indoor shots.
const Dust: React.FC<{seed: number; frame: number}> = ({seed, frame}) => (
	<AbsoluteFill style={{mixBlendMode: 'screen', pointerEvents: 'none'}}>
		{Array.from({length: 26}, (_, i) => {
			const r = (k: string) => random(`${k}${seed}-${i}`);
			const size = 1.5 + 3.5 * r('s');
			const span = H + 40;
			const y = ((((r('y') * span - frame * (0.12 + 0.3 * r('v'))) % span) + span) % span) - 20;
			const x = r('x') * W + 16 * Math.sin(frame / (60 + 50 * r('p')) + 6.28 * r('q'));
			const glow = 0.12 + 0.28 * (0.5 + 0.5 * Math.sin(frame / (18 + 20 * r('t')) + 6.28 * r('u')));
			return (
				<div
					key={i}
					style={{
						position: 'absolute',
						left: x,
						top: y,
						width: size * 3,
						height: size * 3,
						borderRadius: '50%',
						opacity: glow,
						background: 'radial-gradient(circle, rgba(255,236,200,0.95) 0%, rgba(255,236,200,0) 70%)',
					}}
				/>
			);
		})}
	</AbsoluteFill>
);

// Fine film grain over everything; six full-frame tiles cycled and shifted every frame.
const Grain: React.FC = () => {
	const frame = useCurrentFrame();
	const ox = Math.floor(random(`gx${frame}`) * 128);
	const oy = Math.floor(random(`gy${frame}`) * 128);
	return (
		<AbsoluteFill style={{overflow: 'hidden', mixBlendMode: 'overlay', opacity: 0.09, pointerEvents: 'none'}}>
			<Img src={staticFile(`fx/grain_${frame % 6}.png`)} style={{position: 'absolute', left: -ox, top: -oy, width: 1408, height: 848}} />
		</AbsoluteFill>
	);
};

// Dissolving between two framings of the same picture ghosts it, so those shots cut instead.
// Other shots dissolve through a soft blur, like a lens racking between pictures.
const ShotLayer: React.FC<{shot: Shot; first: boolean; cut: boolean}> = ({shot, first, cut}) => {
	const frame = useCurrentFrame();
	const p = first || cut ? 1 : interpolate(frame, [0, XFADE], [0, 1], clamp);
	const hh = handheld(shot.from + frame);
	return (
		<AbsoluteFill style={{opacity: p, backgroundColor: '#000', filter: p < 1 ? `blur(${(1 - p) * 6}px)` : undefined}}>
			{shot.card ? (
				<Card text={shot.card} duration={shot.duration} />
			) : (
				<AbsoluteFill style={{transform: `translate(${hh.x}px, ${hh.y}px) rotate(${hh.r}deg) scale(1.015)`, filter: GRADE, overflow: 'hidden'}}>
					<ImageShot shot={shot} />
				</AbsoluteFill>
			)}
			{shot.amb === 'room' && !shot.card ? <Dust seed={shot.from} frame={shot.from + frame} /> : null}
		</AbsoluteFill>
	);
};

// Lower-third episode strip: bottom-left, clear of the baked-in titles at the top of many panels.
const EpisodeChip: React.FC<{timeline: Timeline}> = ({timeline}) => {
	const frame = useCurrentFrame();
	const opacity = interpolate(frame, [10, 30, 130, 160], [0, 1, 1, 0], clamp);
	const slide = interpolate(frame, [10, 34], [-26, 0], {...clamp, easing: Easing.out(Easing.cubic)});
	const rule = interpolate(frame, [18, 44], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
	return (
		<div
			style={{
				position: 'absolute',
				bottom: 150,
				left: 0,
				padding: '10px 70px 12px 36px',
				background: 'linear-gradient(90deg, rgba(0,0,0,0.62) 0%, rgba(0,0,0,0.35) 65%, rgba(0,0,0,0) 100%)',
				borderLeft: '3px solid #e2b45a',
				opacity,
				transform: `translateX(${slide}px)`,
				fontFamily: inter,
				color: '#f3e6c4',
				textShadow: '0 2px 8px rgba(0,0,0,0.9)',
			}}
		>
			<div style={{fontSize: 15, letterSpacing: 3, textTransform: 'uppercase', opacity: 0.8}}>
				Episode {Number(timeline.id.slice(2))} · {timeline.subtitle}
			</div>
			<div style={{fontSize: 26, fontWeight: 600}}>{timeline.title}</div>
			<div style={{marginTop: 8, height: 2, width: 220 * rule, background: 'linear-gradient(90deg, #e2b45a, transparent)'}} />
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
			<Grain />
			<EdgeFade duration={timeline.durationInFrames} />
		</AbsoluteFill>
	);
};
