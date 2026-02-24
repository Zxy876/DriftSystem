ps -ef | grep paper-1.20.1.jar | grep -v grep | awk '{print $2}' | xargs kill
cd backend/server && find world_staging_v121 world_staging_v121_nether world_staging_v121_the_end -name session.lock -delete
cd ../ && nohup ./start_mc.sh > /tmp/start_mc.out 2>&1 &# DriftSystem v1.21 文档索引

本目录用于归档拍摄系统跃迁（Level-as-Script）的所有文档：

- `example_level.json`（Issue 1.1）
- `crew_task_example.json`（Issue 3.1）
- `crew_runtime.md`（Issue 3.3）
- `demo_runbook.md`（Issue 7.1）
- 其他子文档：导演手册、演员指南、任务手册等

> 当前为占位文件，等待后续 Issue 逐项填充。
