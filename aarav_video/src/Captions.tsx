import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import type {Line, Word} from './types';

// Pick the caption page on screen: from its first word until the next page starts.
const activePage = (line: Line, frame: number): Word[] => {
	let page = line.pages[0];
	for (const p of line.pages) {
		if (p.length && frame >= p[0].start) page = p;
	}
	return page;
};

export const Captions: React.FC<{lines: Line[]; fontFamily: string}> = ({lines, fontFamily}) => {
	const frame = useCurrentFrame();
	const line = lines.find((l) => frame >= l.from && frame < l.from + l.duration + 6);
	if (!line || !line.pages.length) return null;

	const page = activePage(line, frame);
	const narrator = line.who === 'narrator';
	const fade = interpolate(frame, [line.from, line.from + 5], [0, 1], {extrapolateRight: 'clamp'});
	// each new page of words eases up into place
	const pageStart = page.length ? page[0].start : line.from;
	const rise = interpolate(frame, [pageStart - 2, pageStart + 5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

	return (
		<div
			style={{
				position: 'absolute',
				left: 0,
				right: 0,
				bottom: 38,
				display: 'flex',
				justifyContent: 'center',
				opacity: fade,
			}}
		>
			<div
				style={{
					maxWidth: 1060,
					padding: '12px 26px 14px',
					borderRadius: 12,
					background: 'rgba(10, 8, 6, 0.64)',
					backdropFilter: 'blur(6px)',
					border: '1px solid rgba(226, 180, 90, 0.18)',
					boxShadow: '0 10px 30px rgba(0, 0, 0, 0.45)',
					textAlign: 'center',
					fontFamily,
				}}
			>
				<div
					style={{
						fontSize: 15,
						fontWeight: 600,
						letterSpacing: 2.5,
						textTransform: 'uppercase',
						color: line.color,
						marginBottom: 4,
					}}
				>
					{line.name}
				</div>
				<div
					style={{
						fontSize: 33,
						lineHeight: 1.3,
						fontWeight: narrator ? 400 : 600,
						fontStyle: narrator ? 'italic' : 'normal',
						color: '#fff',
						opacity: 0.4 + 0.6 * rise,
						transform: `translateY(${(1 - rise) * 6}px)`,
					}}
				>
					{page.map((w, i) => {
						const spoken = frame >= w.start;
						const current = spoken && frame < w.end;
						return (
							<span
								key={i}
								style={{
									opacity: spoken ? 1 : 0.5,
									color: current ? line.color : '#fff',
									textShadow: current ? `0 0 14px ${line.color}66` : '0 1px 2px rgba(0,0,0,0.6)',
								}}
							>
								{w.text}
								{i < page.length - 1 ? ' ' : ''}
							</span>
						);
					})}
				</div>
			</div>
		</div>
	);
};
