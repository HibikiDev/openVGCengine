'use strict';


function splitmix32(a) {
	return function next() {
		a |= 0;
		a = (a + 0x9e3779b9) | 0;
		let t = a ^ (a >>> 16);
		t = Math.imul(t, 0x21f0aaad);
		t ^= t >>> 15;
		t = Math.imul(t, 0x735a2d97);
		t ^= t >>> 15;
		return t >>> 0;
	};
}

function hashString(s) {
	let h = 0;
	for (const ch of String(s)) h = (h * 31 + ch.charCodeAt(0)) | 0;
	return h;
}






function deriveSeed(seed, salt) {
	const rng = splitmix32((seed | 0) ^ hashString(salt));
	const parts = [rng() % 65536, rng() % 65536, rng() % 65536, rng() % 65536];
	return `gen5,${parts.join(',')}`;
}

module.exports = { deriveSeed, splitmix32 };
