# CityPhone API Contract Snapshot (Iteration 1 Narrative Baseline)

> 范围：Drift System · Science Line 分支后端。本文档按 "Iteration 1 · 叙事数据层" 要求，记录当前实际 API 契约，并在 Iteration 0 冻结的基础上新增叙事载荷说明。

---

## 1. Endpoints

| Method | Path | 描述 | 备注 |
| --- | --- | --- | --- |
| GET | `/ideal-city/cityphone/state/{player_id}` | 读取指定玩家的 CityPhone 状态 | 支持可选 Query `scenario_id`，默认 `default` |
| POST | `/ideal-city/cityphone/action` | 由 CityPhone 前端提交动作（pose、模板等） | Body 为 JSON，匹配 `CityPhoneAction` Pydantic 模型 |

---

## 2. GET `/ideal-city/cityphone/state/{player_id}`

### 2.1 Request

- Path 参数：`player_id`（字符串）。
- Query 参数：`scenario_id`（字符串，默认 `default`）。

### 2.2 Response（当前实现）

```json
{
  "status": "ok",
  "state": {
    "player_id": "demo_player",
    "scenario_id": "default",
    "phase": "vision",
    "ready_for_build": false,
    "build_capability": 0,
    "motivation_score": 0,
    "logic_score": 0,
    "blocking": [],
    "panels": {
      "vision": {
        "goals": [],
        "logic_outline": [],
        "open_questions": [],
        "notes": [
          "[计划 d8ac4a] GM4 Balloon Celebration · 建造完成，派发 1 条指令。 (日志: /Users/zxydediannao/DRIFT_SCIENCELINE/backend/data/ideal_city/build_queue/executed/18c05a80-8dc2-43b0-b3b8-0334b2d8ac4a.json)"
        ],
        "coverage": {}
      },
      "resources": {
        "items": [],
        "pending": true,
        "risk_register": [],
        "risk_pending": true
      },
      "location": {
        "location_hint": null,
        "player_pose": null,
        "pending": true,
        "location_quality": "缺少地标提示"
      },
      "plan": {
        "available": true,
        "summary": "GM4 Balloon Celebration",
        "steps": [
          "demo-1: 部署庆典入口"
        ],
        "mod_hooks": [
          "gm4:balloon_animals"
        ],
        "plan_id": "18c05a80-8dc2-43b0-b3b8-0334b2d8ac4a",
        "status": "已完成",
        "pending_reasons": [
          "建造指令已派发 1 条。",
          "日志文件：18c05a80-8dc2-43b0-b3b8-0334b2d8ac4a.json"
        ]
      }
    },
    "technology_status": {
      "stage": {
        "label": "Crystal Growth",
        "level": 1,
        "progress": 0.35
      },
      "energy": {
        "generation": 120.0,
        "consumption": 85.0,
        "capacity": 200.0,
        "storage": 64.0
      },
      "risk_alerts": [
        {
          "risk_id": "energy_spike",
          "level": "low",
          "summary": "Monitor generator load variance"
        }
      ],
      "recent_events": [
        {
          "event_id": "stage_advance_notice",
          "category": "stage_update",
          "description": "Forge advanced crystal technology to stage 1",
          "occurred_at": "2026-01-10T10:56:30Z",
          "impact": "positive"
        }
      ],
      "updated_at": "2026-01-10T10:57:00Z"
    },
    "narrative": {
      "mode": "archive",
      "title": "熄灯区公共工坊 · 展馆总览",
      "timeframe": "熄灯区纪元 · 第17周",
      "last_event": "2026-01-10 10:56 · Forge advanced crystal technology to stage 1",
      "sections": [
        {
          "slot": "archive_overview",
          "title": "展馆档案",
          "body": [
            "熄灯区临时工坊的外立面修复完成，社区志愿者已接管夜间守护。",
            "城市档案馆收录首批居民修缮记录，等待后续口述材料。",
            "展馆注记：档案仍在整理，城市等待补齐关键字段。"
          ],
          "accent": "collecting"
        },
        {
          "slot": "risk_watch",
          "title": "风险观察",
          "body": [
            "夜间能源调度仍在试运行，备用线路尚未正式备案。",
            "社区轮值制度尚未形成书面档案，存在执行空档。",
            "技术告警[low]：Monitor generator load variance"
          ]
        },
        {
          "slot": "history_log",
          "title": "历史注记",
          "body": [
            "2056-06-12：熄灯区居民委员会提交“公共工坊”企划草案。",
            "2056-06-18：城市工坊联盟捐赠首批工具包，记录入档。",
            "2026-01-10 10:56 · Forge advanced crystal technology to stage 1"
          ]
        },
        {
          "slot": "city_interpretation",
          "title": "城市解读",
          "body": [
            "城市守护者将该企划视为“记忆修复”，期待居民自述如何使用工坊。",
            "城市评分：动机 0 · 逻辑 0 · 建造成熟度 0。",
            "城市解读：叙述仍在扩展，鼓励补充风险与执行步骤。"
          ]
        }
      ]
    }
  }
}
```

### 2.3 字段说明

- `phase`：字符串，枚举之一 `vision|resources|location|plan`（参见 `determine_phase`）。
- `ready_for_build`：布尔，表示是否满足建造条件。
- `build_capability`、`motivation_score`、`logic_score`：整数。
- `blocking`：字符串数组，描述阻塞原因。
- `panels`：四个面板（vision/resources/location/plan），字段结构见上例。
- `technology_status`：可选对象，来自 `technology_status.json`。
- `exhibit_mode`：对象，含 `mode|label|description[]|updated_at`，用于标识展馆处于看展或布展模式及其判定依据。
- `narrative`：新增叙事载荷，包含展馆模式、标题、时间框架以及 `sections[]`（每段含 `slot|title|body|accent`），客户端可直接渲染为“说明牌”文本。

---

## 3. POST `/ideal-city/cityphone/action`

### 3.1 Request

Body JSON 映射 `CityPhoneAction`：

```json
{
  "player_id": "demo_player",
  "action": "pose_sync",
  "payload": {
    "x": 10,
    "y": 64,
    "z": 10,
    "world": "world"
  },
  "scenario_id": "default"
}
```

### 3.2 Response（当前实现）

```json
{
  "status": "error",
  "state": {
    "player_id": "demo_player",
    "scenario_id": "default",
    "phase": "vision",
    "ready_for_build": false,
    "build_capability": 0,
    "motivation_score": 0,
    "logic_score": 0,
    "blocking": [],
    "panels": { ... },
    "technology_status": { ... }
  },
  "notice": null,
  "build_plan": null,
  "guidance": null,
  "manifestation_intent": null,
  "error": "unknown_action",
  "message": "暂不支持该动作。"
}
```

### 3.3 字段说明

- `status`：字符串，`ok|error`。
- `state`：始终返回最新 `CityPhoneStatePayload`。
- `notice` / `build_plan` / `guidance` / `manifestation_intent`：存在时为对象，否则 `null`。
- `error`：错误代码（如 `unknown_action`）。
- `message`：人类可读文本。
- `exhibit_mode`：与 `GET /state` 返回结构一致，方便客户端无需重新推导模式切换。

---

## 4. 迭代保护措施

- 本文档对应 Iteration 1 叙事数据层版本。后续重构需更新此契约快照或生成差异。
- 所有改动必须保持兼容或拉齐客户端同步窗口期。
- 迭代忆述：目标是将 `blocking`、`coverage` 等字段降级为附录，但在改造完成前依旧对外暴露。
- 自 Iteration 1 起，`narrative` 字段为首选渲染来源；`panels` 仍保留至少两个版本以兼容旧客户端。
