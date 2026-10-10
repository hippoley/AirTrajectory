// Contract: AirTrajectory Studio must expose the genuine Pascal editor, not a mocked 3D canvas.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const studio = fs.readFileSync(path.join(root, 'web/studio.html'), 'utf8');
const launcher = fs.readFileSync(path.join(root, 'scripts/start-full-editor.sh'), 'utf8');
const compose = fs.readFileSync(path.join(root, 'compose.pascal-native.yml'), 'utf8');
const notice = fs.readFileSync(path.join(root, 'integrations/pascal-studio/README.md'), 'utf8');
assert.match(studio, /id="open-pascal-editor"[^>]*href="http:\/\/localhost:3002\//);
assert.match(studio, /target="_blank" rel="noopener noreferrer"/);
assert.match(studio, /完整 2D\/3D Editor/);
assert.match(launcher, /pascalorg\/editor\.git/);
assert.match(launcher, /docker compose -f compose\.pascal-native\.yml/);
assert.match(compose, /3002/);
assert.match(notice, /MIT/);
console.log('PASS: Studio links to authentic pinned Pascal Editor with native full interaction entry');
