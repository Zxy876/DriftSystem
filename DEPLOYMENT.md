# DriftSystem 完整启动指南

## 系统架构

DriftSystem由两部分组成:
1. **后端服务** (Python FastAPI) - AI引擎、剧情管理、意图识别
2. **MC插件** (Java/Paper) - 游戏交互、世界渲染

## 快速启动

### 1. 启动后端服务

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端会在 `http://127.0.0.1:8000` 启动

验证:
```bash
curl http://127.0.0.1:8000/
```

应该看到:
```json
{
  "status": "running",
  "routes": ["/levels", "/story/*", "/world/*", "/ai/*", "/minimap/*"]
}
```

### 2. 构建MC插件

```bash
cd system/mc_plugin
./build.sh
```

这会:
- 编译插件
- 生成 `target/mc_plugin-1.0-SNAPSHOT.jar`
- 自动复制到服务器plugins目录

### 3. 配置插件

编辑 `plugins/DriftSystem/config.yml`:
```yaml
backend_url: "http://127.0.0.1:8000"

system:
  debug: true  # 首次运行建议开启调试

story:
  start_level: "level_01"

world:
  allow_world_modification: true
  allow_story_creation: true
```

### 4. 启动Minecraft服务器

```bash
cd backend/server  # 或 server/
java -Xmx4G -Xms2G -jar paper-1.20.1.jar nogui
```

### 5. 进入游戏测试

连接到服务器后:

```
/drift status
```

应该看到系统状态信息。

然后尝试自然语言:
```
你好，我想开始冒险
```

系统会:
1. 识别意图
2. 加载第一关剧情
3. 渲染世界环境
4. 开始互动

## 功能测试

### 测试1: 剧情推进
```
玩家: 继续
玩家: 下一步
```

### 测试2: 跳转关卡
```
玩家: 去第3关
玩家: 跳到level_05
```

### 测试3: 世界控制
```
玩家: 把天气改成下雨
玩家: 现在改成白天
玩家: 传送我到前方
```

### 测试4: 创建剧情
```
玩家: 写一个关于星空的故事
```

系统会:
1. 调用AI生成剧情
2. 创建JSON文件
3. 注入到关卡系统
4. 自动渲染世界

### 测试5: 小地图
```
玩家: 显示地图
玩家: 我在哪里
```

## 故障排查

### 问题1: 插件无法连接后端

检查:
```bash
# 后端是否运行
curl http://127.0.0.1:8000/

# 检查防火墙
# 检查config.yml中的backend_url
```

### 问题2: 意图识别失败

检查后端日志:
```bash
# 后端应该显示
[intent_engine] AI multi-intent failed: ...
```

可能原因:
- API_KEY未设置
- DeepSeek API限流
- 网络问题

解决:
```bash
# 在backend/.env中设置
DEEPSEEK_API_KEY=your_key_here
```

### 问题3: 世界patch不执行

启用调试:
```yaml
system:
  debug: true
```

查看日志:
```
[WorldPatchExecutor] execute patch = {...}
```

### 问题4: 剧情无法加载

检查:
```bash
# 确认关卡文件存在
ls backend/data/heart_levels/

# 测试后端API
curl http://127.0.0.1:8000/levels
```

## 开发模式

### 热重载后端
```bash
cd backend
uvicorn app.main:app --reload
```

代码改动会自动重启后端。

### 重新构建插件
```bash
cd system/mc_plugin
./build.sh
```

然后在MC中:
```
/reload confirm
```

**注意**: 不推荐频繁reload，可能导致状态丢失。

### 查看实时日志

后端:
```bash
tail -f backend/logs/*.log
```

MC服务器:
```bash
tail -f server/logs/latest.log
```

## 环境变量

### 后端 (.env)
```env
DEEPSEEK_API_KEY=sk-xxxxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

### 系统要求
- Python 3.10+
- Java 17+
- Paper/Spigot 1.20.1
- 4GB+ RAM
- 稳定网络连接（用于AI API）

## 高级配置

### 自定义AI提示词

编辑 `backend/app/core/ai/intent_engine.py`:
```python
INTENT_PROMPT = """
你是心悦宇宙的AI...
[自定义你的提示词]
"""
```

### 添加新关卡

在 `backend/data/heart_levels/` 创建 `level_31.json`:
```json
{
  "id": "level_31",
  "title": "新篇章",
  "text": ["剧情内容..."],
  "bootstrap_patch": {
    "mc": {
      "tell": "欢迎来到新篇章"
    }
  }
}
```

### 修改世界渲染逻辑

编辑 `system/mc_plugin/src/main/java/com/driftmc/world/WorldPatchExecutor.java`

添加新的patch类型处理。

## 性能优化

### 后端优化
```bash
# 使用gunicorn多worker
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### MC服务器优化
```
# server.properties
view-distance=8
simulation-distance=6
```

### 缓存配置
```python
# 在后端添加Redis缓存
# 缓存AI响应、剧情状态等
```

## 生产部署

### 后端部署
```bash
# 使用systemd
sudo cp drift-backend.service /etc/systemd/system/
sudo systemctl enable drift-backend
sudo systemctl start drift-backend
```

### MC服务器
```bash
# 使用screen或tmux
screen -S minecraft
./start.sh
# Ctrl+A+D 分离
```

### 反向代理
```nginx
server {
    listen 80;
    server_name drift.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

## 监控

### 后端健康检查
```bash
curl http://127.0.0.1:8000/
```

### MC插件状态
```
/drift status
```

### 查看玩家数据
```bash
cat backend/data/player_states/*.json
```

---

**享受你的AI驱动冒险之旅！** 🚀
