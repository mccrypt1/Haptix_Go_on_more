/** Load shared/patterns.json in the browser (fetch) and in Node (fs). */

let cached = null;

export async function loadSharedPatterns() {
    if (cached) return cached;
    const url = new URL('../shared/patterns.json', import.meta.url);
    try {
        const response = await fetch(url);
        if (response.ok) {
            cached = await response.json();
            return cached;
        }
    } catch { /* file URLs are not fetchable in every Node version */ }
    try {
        const { readFileSync } = await import('node:fs');
        cached = JSON.parse(readFileSync(url, 'utf8'));
    } catch {
        cached = [];
    }
    return cached;
}
