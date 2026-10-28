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
					borderRadius: 10,
					background: 'rgba(8, 7, 6, 0.72)',
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
