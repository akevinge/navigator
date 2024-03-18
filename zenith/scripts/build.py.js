/* eslint-disable */
import { execa } from 'execa';
import fs from 'fs';

const OUT_BINARY_NAME = 'zenith-cli';
const PY_BUILD_DIR = 'build-py';
const OUT_DIR = 'src-tauri/bin/';

// Append exe if on Windows.
let extension = '';
if (process.platform === 'win32') {
	extension = '.exe';
}

// Build the Python binary using PyInstaller.
async function build() {
	return execa('. shim/venv/bin/activate && python3 shim/setup.py build', { shell: true });
}

// Append the target triple to the binary name.
async function appendTargetTriple() {
	// Use rustc to determine the target triple.
	const rustInfo = (await execa('rustc', ['-vV'])).stdout;
	const targetTriple = /host: (\S+)/g.exec(rustInfo)[1];
	if (!targetTriple) {
		throw new Error('failed to determine platform target triple');
	}

	// Rename the binary to include the target triple.
	const pathWithExtension = `${PY_BUILD_DIR}/${OUT_BINARY_NAME}${extension}`;
	const pathWithTargetTriple = `${OUT_DIR}/${OUT_BINARY_NAME}-${targetTriple}${extension}`;
	fs.rmSync(OUT_DIR, { recursive: true, force: true });
	fs.mkdirSync(OUT_DIR, { recursive: true });
	try {
		fs.renameSync(pathWithExtension, pathWithTargetTriple);
		fs.renameSync(`${PY_BUILD_DIR}/lib`, `${OUT_DIR}/lib`);
	} catch (e) {
		throw new Error(`failed to rename ${pathWithExtension} -> ${pathWithTargetTriple}`);
	}

	return pathWithTargetTriple;
}

async function main() {
	await build()
		.then(() => {
			console.log(`✅ Successfully built ${OUT_DIR}/${OUT_BINARY_NAME}`);
		})
		.catch((e) => {
			throw new Error(`error while building: ${e.message}`);
		});

	await appendTargetTriple()
		.then((path) => {
			console.log(`✅ Successfully appended target triple to ${path}`);
		})
		.catch((e) => {
			throw new Error(`error while appending target triple: ${e.message}`);
		});
}

main().catch((e) => {
	console.error(`❌ Error during Python build: ${e.message}`);
});