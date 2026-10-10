#!/usr/bin/env bash
# Open private local SceneGraph in real upstream Pascal Editor (Build/Paint/Items).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${1:?Usage: bash scripts/launch-private-pascal-residence.sh /private/scene.json}"
[[ -f "$SOURCE" ]] || { echo "Private native SceneGraph not found" >&2; exit 2; }
PORT="${PASCAL_EDITOR_PORT:-3002}"
BASE="http://127.0.0.1:$PORT"
command -v node >/dev/null && command -v curl >/dev/null || { echo "node/curl required" >&2; exit 2; }
# Reject bad graph without starting Docker, and compute deterministic private scene ID.
ID="$(node - "$ROOT" "$SOURCE" <<'NODE'
const fs=require('fs'),crypto=require('crypto');
const [root,p]=process.argv.slice(2),b=fs.readFileSync(p),g=JSON.parse(b);
const {checkGraph}=require(root+'/scripts/import-pascal-native-scene.cjs');
checkGraph(g);
if(!Object.values(g.nodes).some(n=>n.type==='zone'))throw Error('No native room zones');
console.log('private-residence-'+crypto.createHash('sha256').update(b).digest('hex').slice(0,16));
NODE
)"
if ! curl -fsS --max-time 3 "$BASE/api/scenes" >/dev/null 2>&1; then
  bash "$ROOT/scripts/start-full-editor.sh"
fi
READY=0
for i in $(seq 1 45); do
  if curl -fsS --max-time 3 "$BASE/api/scenes" >/dev/null 2>&1; then READY=1; break; fi
  sleep 2
done
[[ "$READY" == 1 ]] || { echo "Native Pascal API unavailable at $BASE" >&2; exit 3; }
if curl -fsS --max-time 10 "$BASE/api/scenes/$ID" >/dev/null 2>&1; then
  node - "$BASE" "$ID" "$SOURCE" <<'NODE'
const fs=require('fs');
(async()=>{
 const [base,id,file]=process.argv.slice(2);
 const response=await fetch(base+'/api/scenes/'+id);
 if(!response.ok)throw Error('Saved scene GET failed');
 const remote=(await response.json()).graph,local=JSON.parse(fs.readFileSync(file,'utf8'));
 if(!remote?.nodes||Object.keys(local.nodes).some(id=>JSON.stringify(remote.nodes[id])!==JSON.stringify(local.nodes[id])))
    throw Error('Existing scene differs from input; refusing reuse');
 console.log('Reopened previously persisted scene',id);
})().catch(e=>{console.error(e);process.exitCode=1});
NODE
else
  node "$ROOT/scripts/import-pascal-native-scene.cjs" "$SOURCE" --id "$ID" --name "Private Residential Studio" --url "$BASE"
fi
printf '\nFULL PASCAL EDITOR: %s/scene/%s\n' "$BASE" "$ID"
