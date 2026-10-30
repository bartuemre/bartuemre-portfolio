// Run explicitly to refresh the locally hosted, SIL Open Font License assets.
// These pinned Google Fonts files support English and Turkish (Latin + Latin Extended).
import { mkdir, writeFile } from 'node:fs/promises';
const fontSources = [
  ['dm-mono-v16-400-latin-ext', 'dmmono/v16/aFTU7PB1QTsUX8KYthSQBLyM', 'DM Mono', '400', 'latin-ext'],
  ['dm-mono-v16-400-latin', 'dmmono/v16/aFTU7PB1QTsUX8KYthqQBA', 'DM Mono', '400', 'latin'],
  ['dm-mono-v16-500-latin-ext', 'dmmono/v16/aFTR7PB1QTsUX8KYvumzEY2tbZX9', 'DM Mono', '500', 'latin-ext'],
  ['dm-mono-v16-500-latin', 'dmmono/v16/aFTR7PB1QTsUX8KYvumzEYOtbQ', 'DM Mono', '500', 'latin'],
  ['manrope-v23-latin-ext', 'manrope/v23/xn7gYHE41ni1AdIRggmxSuXd', 'Manrope', '400 700', 'latin-ext'],
  ['manrope-v23-latin', 'manrope/v23/xn7gYHE41ni1AdIRggexSg', 'Manrope', '400 700', 'latin'],
  ['space-grotesk-v22-latin-ext', 'spacegrotesk/v22/V8mDoQDjQSkFtoMM3T6r8E7mPb94C-s0', 'Space Grotesk', '500 700', 'latin-ext'],
  ['space-grotesk-v22-latin', 'spacegrotesk/v22/V8mDoQDjQSkFtoMM3T6r8E7mPbF4Cw', 'Space Grotesk', '500 700', 'latin'],
];
const ranges = {
  'latin-ext': 'U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, U+2113, U+2C60-2C7F, U+A720-A7FF',
  latin: 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD',
};
await mkdir('public/fonts', { recursive: true });
async function download(url, destination, font = false) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (font && bytes.subarray(0, 4).toString() !== 'wOF2') throw new Error(`${url}: not WOFF2`);
  await writeFile(destination, bytes);
  console.log(`${destination}: ${bytes.length} bytes`);
}
await Promise.all(fontSources.map(([name, url]) => download(`https://fonts.gstatic.com/s/${url}.woff2`, `public/fonts/${name}.woff2`, true)));
await Promise.all(['dmmono', 'manrope', 'spacegrotesk'].map(name => download(`https://raw.githubusercontent.com/google/fonts/main/ofl/${name}/OFL.txt`, `public/fonts/${name}-OFL.txt`)));
await writeFile('src/styles/fonts.css', '/* Locally hosted Google Fonts. Sources: scripts/vendor-fonts.mjs; licenses: public/fonts. */\n' + fontSources.map(([name, , family, weight, subset]) => `@font-face {
  font-family: '${family}';
  font-style: normal;
  font-weight: ${weight};
  font-display: swap;
  src: url('/fonts/${name}.woff2') format('woff2');
  unicode-range: ${ranges[subset]};
}`).join('\n'));
