# backend/app/levels/

本目录用于承载 v1.21 的 Level Session 状态机与配套工具：

- `level_session.py`（待实现）：四阶段状态机（IMPORT → SET_DRESS → REHEARSE → TAKE）
- 其他辅助模块应保持只读 / 可审计特性，不得引入世界写入逻辑

> 尚未实现任何业务代码，按照 Copilot 执行清单 Issue 2 系列逐步补齐。
