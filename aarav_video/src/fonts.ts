import {continueRender, delayRender, staticFile} from 'remotion';

// Fonts are bundled in public/fonts so a render never depends on reaching Google Fonts mid-render.
const load = (family: string, file: string, weight: string) => {
	const handle = delayRender(`font ${family} ${weight}`);
	const face = new FontFace(family, `url(${staticFile(`fonts/${file}`)}) format('woff2')`, {weight});
	face
		.load()
		.then(() => {
			document.fonts.add(face);
			continueRender(handle);
		})
		.catch((err) => {
			console.error(err);
			continueRender(handle);
		});
	return family;
};

export const bebas = load('Bebas Neue', 'BebasNeue-latin.woff2', '400');
export const inter = load('Inter', 'Inter-latin-var.woff2', '100 900');
