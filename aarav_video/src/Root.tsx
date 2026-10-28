import React from 'react';
import {Composition, Series} from 'remotion';
import {Episode} from './Episode';
import {timelines} from './timelines';

export const W = 1280;
export const H = 720;
export const FPS = 30;

const Full: React.FC = () => (
	<Series>
		{timelines.map((t) => (
			<Series.Sequence key={t.id} durationInFrames={t.durationInFrames}>
				<Episode timeline={t} />
			</Series.Sequence>
		))}
	</Series>
);

export const RemotionRoot: React.FC = () => (
	<>
		{timelines.map((t) => (
			<Composition
				key={t.id}
				id={t.id}
				component={Episode}
				durationInFrames={t.durationInFrames}
				fps={FPS}
				width={W}
				height={H}
				defaultProps={{timeline: t}}
			/>
		))}
		<Composition
			id="Full"
			component={Full}
			durationInFrames={timelines.reduce((s, t) => s + t.durationInFrames, 0)}
			fps={FPS}
			width={W}
			height={H}
		/>
	</>
);
