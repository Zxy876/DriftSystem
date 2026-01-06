# CityPhone 交互设想与落地路线

> 目标：让玩家通过 "CityPhone" 道具触发剧情引导与建造协同，避免默认聊天框的 GPT 既视感。

## 体验蓝图

- **触发媒介**：
  - 玩家领取或合成一台 `CityPhone`（可用资源包模型 + 自定义名称）。
  - 只要热键栏持有该道具并右击，才会唤起剧情界面；离手或关闭背包时界面自动收起。

- **双栏界面布局**：
  - **上栏**：档案员头像 + 氛围化叙事文本，弱化聊天泡泡。
  - **下栏 tab**：
    1. `愿景` – 展示/整理玩家愿景与故事代理追问；提供“继续描述”按钮。
    2. `资源` – 结构化勾选表（来自 `StoryState.resources`），支持逐条确认或添加。
    3. `定位` – 实时显示 player pose；提供 `/taskdebug pose` 抄写按钮。
    4. `计划` – 当 `ready_for_build` 为 true，展示建造计划摘要与执行按钮。

- **阶段感**：
  - `StoryStateManager` 的阶段信息映射到手机界面的 tab 高亮或引导箭头。
  - 完成一阶段后自动播放短音效或震动提示。

- **口吻调整**：
  - 每个阶段的提示词写入 `story_state_agent` 阶段配置。
  - UI 内文本统一采用“档案馆后勤官”语气。

## 技术落地

### Minecraft 插件

1. **CityPhone 道具**
   - 注册自定义物品（使用资源包模型 ID `cityphone:item`）。
   - `onPlayerInteract` 拦截右键事件，调用服务器指令 `/cityphone open`。

2. **命令 & UI**
   - 新增 Paper 插件命令 `/cityphone open|close|status`：
     - `open`：向客户端发送 `OpenCityPhonePacket`（自定义网络/插件频道）。
     - `close`：关闭 UI。
     - `status`：调试用，打印当前 `StoryState` 概要。
   - 若已有自定义界面系统，复用；否则可用 Adventure/Spigot Inventory GUI + 客户端资源包渲染。

3. **动作同步**
   - UI 内按钮调用 `/cityphone action <player> <payload_json>`，由服务器转发到后端 API。
   - 例如 `payload_json = {"action": "submit_narrative", "text": "..."}`。

### 后端 API 扩展

- 新增 `POST /ideal-city/cityphone/action`：
  - 请求体：`{ "player_id": str, "action": str, "payload": dict }`。
  - 将动作转换为 `DeviceSpecSubmission` 或 StoryState 更新。

- 新增 `GET /ideal-city/cityphone/state/{player_id}`：
  - 组合返回：
    ```json
    {
      "phase": "vision|resources|location|wrap",
      "panels": {
        "vision": {...},
        "resources": [...],
        "location": {...},
        "plan": {...}
      }
    }
    ```

- 调整 `story_state_agent` 阶段提示词与 UI 标签文案对应。

### 客户端（可选模组层）

- 如果使用 `resourcepack + plugin` 方案不够，可通过 Fabric/Forge 客户端模组：
  - 监听插件频道 `cityphone:open`。
  - 渲染自定义屏幕，按阶段显示不同面板。
  - 通过 `cityphone:action` 频道发送 JSON 指令。

## 开发拆解

1. **道具 & 指令骨架**（插件）
   - 注册 CityPhone 物品、命令、监听器。
   - 骨架打通：右键 → 日志打印。

2. **后端接口**
   - 定义 `CityPhoneStateDTO`，封装 `StoryState` + 计划信息。
   - 实现 action handler：
     - `submit_narrative`
     - `confirm_resource`
     - `push_pose`
     - `request_plan`

3. **UI 原型**
   - 先用纯文本 GUI（Inventory 菜单）实现阶段切换和按钮；确认流程通。

4. **资源包 & 音效**
   - 增加手机 2D/3D 模型、交互音效。

5. **体验抛光**
   - 加入提示动画、TAB 高亮、阶段成功提示等。

## 里程碑

| Milestone | 目标 | 产出 |
|-----------|------|------|
| M1 | 打通手机交互链（原型） | 道具触发 → UI → 后端 → StoryState 更新 |
| M2 | 阶段 UI 完整化 | 视觉稿、资源/定位/计划面板联调 |
| M3 | 正式上线 | QA、玩家引导文案、文档更新 |

## 验收指标

- 玩家必须持有 CityPhone 才能打开剧情界面。
- `StoryState.ready_for_build` 为真时，Plan 面板显示“提交建造”按钮。
- 当玩家掉线/离手后，UI 自动关闭且状态同步。
- 全流程无需打开原生聊天，即可完成建造准备。

---

> 后续可延伸：
> - CityPhone 记录所有阶段历史，供玩家回顾。
> - 推送即时广播（如建造完成通知）。
> - 单机模式下提供离线缓存，待上线后自动同步。
