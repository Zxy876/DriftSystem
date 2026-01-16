# 聊天创造意图识别说明

> 版本：2026-01-14 · 维护者：Drift System 工程团队

---

## 1. 模块概览
- 模块位置：`backend/app/core/intent_creation.py`
- API 入口：`POST /intent/recognize`
- 判定策略：基于规则的保守分类器，提供 **创造 / 非创造** 二分类结果，并回传命中的动词与资源槽位。
- 使用场景：
  - 聊天转裁决主链路（`IdealCityPipeline.ingest_narrative_event`）的前置过滤。
  - 调试/标注工具调用，辅助构建 Phase 1 标注集。

---

## 2. 数据结构
### 2.1 API 请求
```json
POST /intent/recognize
{
  "message": "我想用紫水晶搭建一盏幽冥莲花灯"
}
```

### 2.2 API 响应
```json
{
  "is_creation": true,
  "confidence": 0.78,
  "reasons": ["action:搭建", "material:紫水晶", "boost:我想"],
  "creation_slots": {
    "actions": ["搭建"],
    "materials": ["紫水晶"]
  },
  "raw_slots": {
    "actions": ["搭建"],
    "materials": ["紫水晶"],
    "boost": ["我想"]
  }
}
```
- `creation_slots`：下游用于构建 `creation_plan` 的核心槽位（Phase 2 输入要求）。
- `raw_slots`：调试用，包含所有命中的关键词桶。

---

## 3. 关键词维护
- 默认词表文件：`backend/data/intent/creation_keywords.json`
- 字段说明：
  - `action_keywords`：创造动词/短语。
  - `material_keywords`：常见方块/资源/结构名词。
  - `non_creation_keywords`：判定非创造时的负面词。
  - `boost_phrases`：提高置信度的意图短语。
- 支持在实例化 `CreationIntentClassifier` 时注入额外词表，便于场景差异化。

---

## 4. 标注数据集
- 路径：`backend/data/intent/creation_intent_dataset.jsonl`
- 规模：120 条（creation 80 / non_creation 40）。
- 每行结构：
```json
{"message": "...", "label": "creation", "notes": "补充说明"}
```
- 用途：
  - Phase 1 交付产出（手工审阅可用）。
  - Phase 2/Phase 3 可作为 Transformer 校验/基线测试案例。

---

## 5. 集成点
- `IdealCityPipeline.ingest_narrative_event`
  - 在 Narrative 抽取后调用 `default_creation_classifier()`。
  - 若 `is_creation=False` 且未命中系统指令 → 返回 `status="ignored"`，避免误触发裁决。
  - 回传 `intent_analysis`（同上响应结构，使用 `CreationIntentDecision.model_dump()`）。
- `test_narrative_ingestion.py`
  - 覆盖正/负示例，确保响应包含 `intent_analysis`。

---

## 6. 后续工作
1. 继续扩充数据集（目标 ≥200 条，覆盖多模态输入）。
2. 结合 Phase 2 Transformer 产出 `creation_plan` Schema（动词 → 模板映射、材料 → Mod ID）。
3. 引入日志聚合（统计 `ignored/accepted/needs_review` 比例，落地到 `backend/logs/creation_pipeline/`）。

---

*如需调整词表或扩展槽位，请同步更新此文档并新增单元测试覆盖。*
