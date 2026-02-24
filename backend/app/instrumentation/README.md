# backend/app/instrumentation/

- 现有 `cityphone_metrics.py` 继续服务 v1.18 语义层监控
- v1.21 将在此新增审计模块，例如 `level_audit.py`、`director_audit.py`
- 所有文件必须仅记录/审计，不直接修改业务状态

> 本 README 由 Copilot Issue 0.1 创建，用于标记 v1.21 新增审计职责。
