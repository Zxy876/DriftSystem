#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
PLAYER="p2rt_$(date +%s)_$RANDOM"
LEVEL="rt_p2_$(date +%s)_$RANDOM"
BUILD_ID="rt_accept_$(date +%s)_$RANDOM"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "PLAYER $PLAYER"
echo "LEVEL $LEVEL"

echo "== START STORY =="
curl -sS -X POST "$BASE/world/story/start" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$PLAYER\"}" > "$TMP_DIR/start.json"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("START_STATUS", d.get("status"), d.get("level_id"))' "$TMP_DIR/start.json"

echo "== COLLECT EVENTS =="
for ITEM in oak_log raw_porkchop torch; do
  curl -sS -X POST "$BASE/world/story/rule-event" \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$PLAYER\",\"event_type\":\"collect\",\"payload\":{\"item_type\":\"$ITEM\",\"amount\":1,\"location\":{\"x\":12,\"y\":65,\"z\":-3,\"world\":\"world\"}}}" > "$TMP_DIR/collect_${ITEM}.json"
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("COLLECT", sys.argv[2], d.get("status"))' "$TMP_DIR/collect_${ITEM}.json" "$ITEM"
done

echo "== DEBUG AFTER COLLECT =="
curl -sS "$BASE/world/story/$PLAYER/debug/tasks" > "$TMP_DIR/debug_collect.json"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); inv=d.get("inventory_resources") or {}; print("DEBUG_STATUS", d.get("status")); print("INVENTORY", json.dumps(inv, ensure_ascii=False, sort_keys=True)); ok=(inv.get("wood",0)>=1 and inv.get("pork",0)>=1 and inv.get("torch",0)>=1 and "oak_log" not in inv and "raw_porkchop" not in inv); print("CANONICAL_INVENTORY_OK", ok)' "$TMP_DIR/debug_collect.json"

echo "== SCENE INJECT =="
INJECT_DATA="{\"level_id\":\"$LEVEL\",\"title\":\"P2 Runtime Acceptance\",\"text\":\"创建剧情 森林营地，验证资源语义\",\"player_id\":\"$PLAYER\",\"player_position\":{\"world\":\"world\",\"x\":12,\"y\":65,\"z\":-3},\"scene_theme\":\"大风吹\",\"scene_hint\":\"森林\"}"
INJECT_CODE=$(curl --max-time 45 -sS -o "$TMP_DIR/inject.json" -w "%{http_code}" \
  -X POST "$BASE/story/inject" \
  -H "Content-Type: application/json" \
  -d "$INJECT_DATA" || true)
echo "INJECT_HTTP_CODE $INJECT_CODE"
if [[ "$INJECT_CODE" == "200" ]]; then
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); scene=d.get("scene") or {}; plan=scene.get("scene_plan") or {}; inv=(scene.get("inventory_state") or {}).get("resources") or {}; frags=plan.get("fragments") or []; print("INJECT_STATUS", d.get("status")); print("SCENE_INVENTORY", json.dumps(inv, ensure_ascii=False, sort_keys=True)); print("SCENE_FRAGMENTS", json.dumps(frags, ensure_ascii=False)); print("SCENE_FRAGMENTS_OK", {"camp","fire","cooking_area"}.issubset(set(frags)))' "$TMP_DIR/inject.json"
else
  python3 -c 'import json,sys; p=sys.argv[1];
try:
 d=json.load(open(p));
 print("INJECT_ERROR", json.dumps(d, ensure_ascii=False))
except Exception:
 print("INJECT_ERROR", "non-json-or-timeout")' "$TMP_DIR/inject.json"
fi

echo "== APPLY REPORT =="
curl -sS -X POST "$BASE/world/apply/report" \
  -H "Content-Type: application/json" \
  -d "{\"build_id\":\"$BUILD_ID\",\"player_id\":\"$PLAYER\",\"status\":\"EXECUTED\",\"failure_code\":\"OK\",\"executed\":4,\"failed\":0,\"duration_ms\":120,\"payload_hash\":\"hash_$RANDOM\"}" > "$TMP_DIR/apply_report.json"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("APPLY_REPORT_STATUS", d.get("status"), d.get("last_status"), d.get("report_count"))' "$TMP_DIR/apply_report.json"

echo "== DEBUG FINAL =="
curl -sS "$BASE/world/story/$PLAYER/debug/tasks" > "$TMP_DIR/debug_final.json"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); last=d.get("last_apply_report") or {}; scene=d.get("scene_generation") or {}; print("DEBUG_FINAL_STATUS", d.get("status")); print("DEBUG_FINAL_INVENTORY", json.dumps(d.get("inventory_resources") or {}, ensure_ascii=False, sort_keys=True)); print("DEBUG_FINAL_LAST_APPLY", json.dumps(last, ensure_ascii=False, sort_keys=True)); print("DEBUG_FINAL_SCENE_FRAGMENTS", json.dumps(scene.get("fragments") or [], ensure_ascii=False))' "$TMP_DIR/debug_final.json"

echo "== SUMMARY =="
python3 -c 'import json,sys; dc=json.load(open(sys.argv[1])); df=json.load(open(sys.argv[2])); inv=dc.get("inventory_resources") or {}; print(json.dumps({"player_id":sys.argv[3], "level_id":sys.argv[4], "inventory":inv, "canonical_inventory_ok": (inv.get("wood",0)>=1 and inv.get("pork",0)>=1 and inv.get("torch",0)>=1 and "oak_log" not in inv and "raw_porkchop" not in inv), "last_apply_status": (df.get("last_apply_report") or {}).get("last_status")}, ensure_ascii=False, sort_keys=True))' "$TMP_DIR/debug_collect.json" "$TMP_DIR/debug_final.json" "$PLAYER" "$LEVEL"
