# DriftSystem 文档索引

## 关卡统一规范

所有 Heart Levels 必须遵循同一个 JSON 结构，核心字段如下：

```json
{
  "id": "level_01",
  "title": "心悦文集 第 1 章",
  "narrative": {
    "text": ["第一段剧情文本"],
    "beats": []
  },
  "scene": {},
  "tasks": [],
  "meta": {},
  "tags": []
}
```

### 规则总结
- **文件名与 `id` 一致**：`level_01.json` 对应 `"id": "level_01"`。
- **`narrative` 必须是对象**：至少包含 `text`（数组），`beats` 可选。
- **`scene` 必须是对象**：允许为空对象，后续可以逐步扩充细节。
- **`tasks` 必须是数组**：没有任务时使用 `[]`，禁止 `null` 或缺省。
- 允许继续保留旧版 `text` 字段，验证脚本会自动同步到 `narrative.text`。

### 验证命令
在仓库根目录执行：

```bash
# 自动修复（若发现格式问题会直接写回文件）
python backend/tools/validate_levels.py

# 只验证不修改，若检查失败将返回非零退出码
python backend/tools/validate_levels.py --strict
```

验证通过后，再执行：

```bash
python backend/drift_backend_selftest.py
```

即可确认关卡数据与后端加载流程保持一致。
