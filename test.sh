#!/bin/bash

BASE="http://127.0.0.1:8000"
PLAYER="test_player"

echo "== WORLD =="
curl "$BASE/world/state"
curl -X POST "$BASE/world/apply" \
    -H "Content-Type: application/json" \
    -d '{"action":{"type":"create","target":"purple_whale","location":"sky"}}'

echo "== TREE =="
curl -X POST "$BASE/add" -H "Content-Type: application/json" \
    -d '{"content":"测试树节点"}'

curl "$BASE/state"
curl -X POST "$BASE/backtrack"
curl -X POST "$BASE/breakpoint"

echo "== DSL =="
curl -X POST "$BASE/run" -H "Content-Type: application/json" \
    -d '{"script":"print(\"hello\")"}'

echo "== ROOT =="
curl -X POST "$BASE" -H "Content-Type: application/json" \
    -d '{"content":"你好"}'

echo "== STORY =="
curl "$BASE/story/levels"
curl "$BASE/story/level/level_1"
curl -X POST "$BASE/story/load/$PLAYER/level_1"
curl "$BASE/story/state/$PLAYER"

curl -X POST "$BASE/story/advance/$PLAYER" \
    -H "Content-Type: application/json" \
    -d '{"action":{"type":"continue"}}'
