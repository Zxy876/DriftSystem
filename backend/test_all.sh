#!/bin/bash
echo "======================================="
echo "     DriftSystem 0-1 Testing Tool"
echo "======================================="

echo "--- v1.18 Comment Contract ---"
python3 tools/validate_v118_comments.py || exit 1

echo "--- Semantic Alias Coverage (P3-1) ---"
python3 tools/measure_semantic_alias_coverage.py || exit 1
python3 -m pytest test_semantic_alias_coverage_gate.py || exit 1

echo "--- Drift Resource Guardrails (P3-2) ---"
python3 -m pytest test_drift_resource_catalog_guardrails.py -q || exit 1

BASE="http://127.0.0.1:8000"

echo "--- Test: Add Node ---"
curl -s -X POST "$BASE/tree/add?content=测试节点"
echo; echo

echo "--- Test: Tree State ---"
curl -s "$BASE/tree/state"
echo; echo

echo "--- Test: Backtrack ---"
curl -s -X POST "$BASE/tree/backtrack"
echo; echo

echo "--- Test: Breakpoint ---"
curl -s -X POST "$BASE/tree/breakpoint"
echo; echo

echo "--- Test: DSL ---"
curl -s -X POST "$BASE/dsl/run" \
    -H "Content-Type: application/json" \
    -d '{"script": "ADD 你好"}'
echo; echo

echo "--- Test: Hint (AI Assist) ---"
curl -s -X POST "$BASE/hint/get" \
    -H "Content-Type: application/json" \
    -d '{"context": "测试一下AI"}'
echo; echo

echo "======================================="
echo "     DriftSystem 0-1 Test Complete"
echo "======================================="