// Contract: AirTrajectory Studio is a truthful gateway to the complete, self-hosted Pascal editor.
// The public GitHub Pages entry must not pretend to host the native Next.js application.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const studio = fs.readFileSync(path.join(root, 'web/studio.html'), 'utf8');
const launcher = fs.readFileSync(path.join(root, 'scripts/start-full-editor.sh'), 'utf8');
const compose = fs.readFileSync(path.join(root, 'compose.pascal-native.yml'), 'utf8');
const notice = fs.readFileSync(path.join(root, 'integrations/pascal-studio/README.md'), 'utf8');
assert.match(studio, /Pascal 原生 2D\/3D Editor/);
assert.match(studio, /href="http:\/\/localhost:3002\/?"/);
assert.match(studio, /bash scripts\/start-full-editor\.sh/);
assert.match(studio, /SELF-HOSTED/);
assert.match(studio, /legacy-studio\.html/);
assert.doesNotMatch(studio, /<svg\b|<canvas\b|legacy-studio\.js/);
assert.match(launcher, /pascalorg\/editor\.git/);
assert.match(launcher, /docker compose -f compose\.pascal-native\.yml/);
assert.match(compose, /3002/);
assert.match(notice, /MIT/);
console.log('PASS: public Studio is Pascal native self-hosted gateway and never resurrects legacy canvas');
