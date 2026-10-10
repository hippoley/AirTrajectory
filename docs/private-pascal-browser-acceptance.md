# Private homeowner Pascal native browser acceptance

Do not check in residential CAD, exact room coordinate data, screenshots, or local browser receipts. This runner imports a private native SceneGraph directly into the unmodified full Pascal Editor, opens it using real Chromium, checks the native renderer's canvas and scene persistence, and writes a private screenshot.

Start the pinned Pascal editor with `bash scripts/start-full-editor.sh`.

Then, on a trusted computer which has the original private CAD conversion outputs, run:

```bash
python scripts/convert_reviewed_rooms_to_pascal.py /private/hongyu_multilayer_rooms_candidate.json --output /private/hongyu_pascal_native_six_rooms.json
node scripts/accept-private-pascal-scene.cjs /private/hongyu_pascal_native_six_rooms.json private-hongyu-001
```

It refuses replacing an existing scene ID. For repeat runs, change the ID. The output `artifacts/private-pascal/native-private-residence.png` and `acceptance.json` must be kept private, not attached to a public Actions job.

Acceptance requires real `/scene/{id}` HTTP success, native canvas, zero JavaScript page errors, the same persisted zone count, and polygon equality after save. It explicitly does **not** prove visually accurate CAD walls, reviewed opening hosts, genuine physically signed sidecars, Paint/Items interaction or a ContamX run. Work on these separate gates only after the owner verifies the architectural geometry.
