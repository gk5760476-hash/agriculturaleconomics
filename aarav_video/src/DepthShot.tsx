import React, {useEffect, useLayoutEffect, useRef, useState} from 'react';
import {continueRender, delayRender, staticFile} from 'remotion';
import type {Cam} from './types';

type Pixels = {w: number; h: number; data: Uint8ClampedArray};

// Decoded pixels are shared by every shot in this render tab that uses the same picture.
const cache = new Map<string, Promise<Pixels>>();

const loadPixels = (src: string): Promise<Pixels> => {
	let p = cache.get(src);
	if (!p) {
		p = new Promise((resolve, reject) => {
			const img = new Image();
			img.onload = () => {
				const c = document.createElement('canvas');
				c.width = img.naturalWidth;
				c.height = img.naturalHeight;
				const ctx = c.getContext('2d', {willReadFrequently: true})!;
				ctx.drawImage(img, 0, 0);
				resolve({w: c.width, h: c.height, data: ctx.getImageData(0, 0, c.width, c.height).data});
			};
			img.onerror = () => reject(new Error(`could not load ${src}`));
			img.src = src;
		});
		cache.set(src, p);
	}
	return p;
};

type Props = {
	img: string;
	depth: string;
	cam: Cam; // camera now
	start: Cam; // camera at the shot's first frame
	t: number; // eased shot progress 0..1
	width: number;
	height: number;
	cover: (aspect: number, cam: Cam) => {left: number; top: number; width: number; height: number};
};

// 2.5D parallax: every output pixel samples the picture shifted by its depth, so near things (Aarav, the
// table) grow and slide a little more than the room behind them as the camera moves. Zero shift at t = 0.
export const DepthShot: React.FC<Props> = ({img, depth, cam, start, t, width, height, cover}) => {
	const canvas = useRef<HTMLCanvasElement>(null);
	const [handle] = useState(() => delayRender(`depth ${img}`));
	const [pix, setPix] = useState<[Pixels, Pixels] | null>(null);
	const out = useRef<ImageData | null>(null);
	const released = useRef(false);

	useEffect(() => {
		Promise.all([loadPixels(staticFile(img)), loadPixels(staticFile(depth))])
			.then(setPix)
			.catch((e) => {
				console.error(e);
				continueRender(handle);
			});
	}, [img, depth, handle]);

	useLayoutEffect(() => {
		const c = canvas.current;
		if (!c || !pix) return;
		const [src, dep] = pix;
		const dpr = window.devicePixelRatio || 1;
		const cw = Math.round(width * dpr);
		const ch = Math.round(height * dpr);
		if (c.width !== cw || c.height !== ch) {
			c.width = cw;
			c.height = ch;
		}
		const ctx = c.getContext('2d')!;
		if (!out.current || out.current.width !== cw || out.current.height !== ch) out.current = ctx.createImageData(cw, ch);
		const o = out.current.data;

		const aspect = src.w / src.h;
		const r = cover(aspect, cam);
		const r0 = cover(aspect, start);
		// image point at frame centre, now and at the start
		const uc = (width / 2 - r.left) / r.width;
		const vc = (height / 2 - r.top) / r.height;
		const uc0 = (width / 2 - r0.left) / r0.width;
		const vc0 = (height / 2 - r0.top) / r0.height;
		// dolly: near pixels magnify by (1 + n * dolly); grows with the camera's zoom change plus a gentle drift
		const zoomDir = cam[2] >= start[2] ? 1 : -1;
		const dolly = Math.max(-0.08, Math.min(0.08, 0.4 * (cam[2] / start[2] - 1))) + 0.025 * t * zoomDir;
		// pan: near pixels travel further than far ones
		const panU = 0.3 * (uc - uc0);
		const panV = 0.3 * (vc - vc0);

		const sd = src.data;
		const sw = src.w;
		const sh = src.h;
		const dd = dep.data;
		const dw = dep.w;
		const dh = dep.h;
		const inv = 1 / dpr;
		let k = 0;
		for (let y = 0; y < ch; y++) {
			const v0 = ((y + 0.5) * inv - r.top) / r.height;
			const dy = Math.min(dh - 1, Math.max(0, (v0 * dh) | 0));
			for (let x = 0; x < cw; x++) {
				const u0 = ((x + 0.5) * inv - r.left) / r.width;
				const dx = Math.min(dw - 1, Math.max(0, (u0 * dw) | 0));
				const n = dd[(dy * dw + dx) * 4] / 255;
				const s = 1 + n * dolly;
				let u = uc + (u0 - uc) / s + n * panU;
				let v = vc + (v0 - vc) / s + n * panV;
				// bilinear sample, clamped to the picture
				let sx = u * sw - 0.5;
				let sy = v * sh - 0.5;
				if (sx < 0) sx = 0;
				else if (sx > sw - 1.001) sx = sw - 1.001;
				if (sy < 0) sy = 0;
				else if (sy > sh - 1.001) sy = sh - 1.001;
				const ix = sx | 0;
				const iy = sy | 0;
				const fx = sx - ix;
				const fy = sy - iy;
				const i00 = (iy * sw + ix) * 4;
				const i10 = i00 + 4;
				const i01 = i00 + sw * 4;
				const i11 = i01 + 4;
				const w00 = (1 - fx) * (1 - fy);
				const w10 = fx * (1 - fy);
				const w01 = (1 - fx) * fy;
				const w11 = fx * fy;
				o[k] = sd[i00] * w00 + sd[i10] * w10 + sd[i01] * w01 + sd[i11] * w11;
				o[k + 1] = sd[i00 + 1] * w00 + sd[i10 + 1] * w10 + sd[i01 + 1] * w01 + sd[i11 + 1] * w11;
				o[k + 2] = sd[i00 + 2] * w00 + sd[i10 + 2] * w10 + sd[i01 + 2] * w01 + sd[i11 + 2] * w11;
				o[k + 3] = 255;
				k += 4;
			}
		}
		ctx.putImageData(out.current, 0, 0);
		if (!released.current) {
			released.current = true;
			continueRender(handle);
		}
	});

	return <canvas ref={canvas} style={{position: 'absolute', left: 0, top: 0, width, height}} />;
};
