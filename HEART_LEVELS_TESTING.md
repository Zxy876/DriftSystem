# 心悦文集30关卡增强 - 测试文档

## 📋 实现概览

### ✅ 已完成功能

#### 1. **30个关卡独特场景配置**
每个关卡都有：
- 🏗️ **独特建筑/装置** (world_patch.build)
- 👤 **专属NPC角色** (world_patch.spawn)
- 🎵 **主题音乐** (world_patch.music)
- ✨ **环境粒子效果** (world_patch.particle)
- 💬 **欢迎语** (world_patch.tell)

#### 2. **关卡主题列表**

| 关卡 | 主题 | NPC | 音乐 | 生物群系 |
|------|------|-----|------|---------|
| level_01 | 赛道 | 赛车手桃子 | pigstep | PLAINS |
| level_02 | 图书馆 | 图书管理员 | cat | FOREST |
| level_03 | 山顶 | 隐士 | ward | MOUNTAINS |
| level_04 | 海边 | 渔夫 | stal | BEACH |
| level_05 | 森林 | 护林员 | chirp | FOREST |
| level_06 | 沙漠 | 商人 | mall | DESERT |
| level_07 | 雪山 | 雪人 | wait | ICE_SPIKES |
| level_08 | 洞穴 | 矿工 | 11 | CAVES |
| level_09 | 花园 | 园丁 | blocks | FLOWER_FOREST |
| level_10 | 湖泊 | 诗人 | far | RIVER |
| level_11 | 村庄 | 村长 | mellohi | PLAINS |
| level_12 | 瀑布 | 瀑布守护者 | strad | JUNGLE |
| level_13 | 竹林 | 熊猫饲养员 | 13 | BAMBOO_JUNGLE |
| level_14 | 沼泽 | 沼泽学者 | otherside | SWAMP |
| level_15 | 悬崖 | 攀岩者 | 5 | WINDSWEPT_HILLS |
| level_16 | 神殿 | 祭司 | stal | JUNGLE |
| level_17 | 灯塔 | 灯塔看守 | pigstep | OCEAN |
| level_18 | 冰湖 | 滑冰者 | cat | FROZEN_OCEAN |
| level_19 | 蘑菇岛 | 蘑菇研究员 | ward | MUSHROOM_FIELDS |
| level_20 | 平原 | 牧羊人 | chirp | PLAINS |
| level_21 | 峡谷 | 探险家 | mall | BADLANDS |
| level_22 | 樱花林 | 赏花者 | wait | CHERRY_GROVE |
| level_23 | 废墟 | 考古学家 | 11 | DESERT |
| level_24 | 天空岛 | 飞行员 | blocks | END_HIGHLANDS |
| level_25 | 地下城 | 守卫 | far | DEEP_DARK |
| level_26 | 温泉 | 温泉管理员 | mellohi | SAVANNA |
| level_27 | 星空台 | 占星师 | strad | PLAINS |
| level_28 | 极光 | 极光观察者 | 13 | ICE_SPIKES |
| level_29 | 火山 | 火山学家 | otherside | BASALT_DELTAS |
| level_30 | 心悦殿堂 | 心悦守护者 | 5 | END_HIGHLANDS |

#### 3. **小地图解锁可视化**

**视觉效果：**
- 🔒 **未解锁关卡**：暗蓝色小圆点 (5像素) + 暗色文字
- 🔓 **已解锁关卡**：亮青绿色圆点 (7像素) + 光晕效果 + 亮色文字
- 💛 **当前关卡**：金色大圆点 (10像素) + 强光晕
- 🔴 **玩家位置**：红色小点 + 白色边框

**自动解锁触发：**
- 创建剧情时自动解锁关卡 (`inject_story`)
- 剧情对话时持续解锁 (`say_next`)

---

## 🧪 测试步骤

### 前置条件
```bash
# 1. 确认后端运行
ps aux | grep "python app/main.py"  # 应显示 PID 97727

# 2. 确认MC服务器运行
ps aux | grep "java.*paper"

# 3. 进入游戏
# Minecraft 1.20.1 客户端连接 localhost:25565
```

### Test Case 1: 创建剧情并验证场景加载

**步骤：**
1. 进入游戏，在聊天框输入：
   ```
   写一个剧情
   ```

2. **预期结果：**
   - ✅ 看到AI生成的剧情文本
   - ✅ 自动传送到关卡场景
   - ✅ 看到NPC生成（如：赛车手桃子）
   - ✅ 听到主题音乐（如：pigstep）
   - ✅ 看到粒子效果（villager_happy）
   - ✅ 收到欢迎消息："欢迎来到赛道！"

### Test Case 2: 跳关并验证独特场景

**步骤：**
1. 输入：
   ```
   跳到第三关
   ```

2. **预期结果：**
   - ✅ 传送到山顶场景 (level_03)
   - ✅ 看到NPC："隐士"
   - ✅ 听到音乐：ward
   - ✅ 生物群系：MOUNTAINS
   - ✅ 建筑：瞭望塔

3. 继续测试其他关卡：
   ```
   跳到第十关   # → 湖泊 + 诗人 + far音乐
   跳到第二十关 # → 平原 + 牧羊人 + chirp音乐
   跳到第三十关 # → 心悦殿堂 + 心悦守护者
   ```

### Test Case 3: 小地图解锁可视化

**步骤：**
1. 输入：
   ```
   给我小地图
   ```

2. **预期结果：**
   - ✅ 收到filled_map物品
   - ✅ 已解锁关卡显示为**亮青绿色**大圆点+光晕
   - ✅ 未解锁关卡显示为**暗蓝色**小圆点
   - ✅ 当前关卡显示为**金色**超大圆点
   - ✅ 玩家位置显示为**红色**小点

3. 继续创建更多剧情，观察小地图变化：
   ```
   写一个剧情  # → 解锁level_01
   继续        # → 可能解锁level_02
   继续        # → 继续解锁...
   ```

4. **再次获取小地图验证变化：**
   ```
   给我小地图
   ```
   - ✅ 新解锁的关卡应变为**亮青绿色**

### Test Case 4: 多关卡连续测试

**步骤：**
```
写一个沙漠冒险的剧情  # → level_06 沙漠+商人
继续
继续
跳到雪山关卡           # → level_07 雪山+雪人
给我小地图             # → 验证level_06和level_07都已解锁
```

---

## 🐛 已知问题排查

### Issue 1: NPC未生成
**检查：**
```bash
# 查看后端日志
tail -f /Users/zxydediannao/DriftSystem/backend/backend.log

# 检查world_patch是否包含spawn命令
curl http://127.0.0.1:8000/story/load/<level_id>?player_id=<uuid>
```

### Issue 2: 音乐未播放
**检查：**
- MC客户端音量设置
- 唱片机是否生成（`/minecraft:record_<music_name>`）
- world_patch的music字段

### Issue 3: 小地图颜色错误
**检查：**
```bash
# 获取玩家小地图数据
curl http://127.0.0.1:8000/minimap/player/<player_id>

# 检查unlocked列表是否包含已完成关卡
```

---

## 📊 配置文件位置

- **关卡配置**: `/Users/zxydediannao/DriftSystem/backend/data/heart_levels/level_*.json`
- **增强脚本**: `/Users/zxydediannao/DriftSystem/backend/enhance_heart_levels.py`
- **小地图渲染**: `/Users/zxydediannao/DriftSystem/backend/app/core/world/minimap_renderer.py`
- **关卡API**: `/Users/zxydediannao/DriftSystem/backend/app/api/level_api.py`
- **小地图API**: `/Users/zxydediannao/DriftSystem/backend/app/api/minimap_api.py`

---

## 🎉 成功标准

所有30个关卡应满足：
- [x] 独特NPC名称和角色
- [x] 独特建筑/装置描述
- [x] 独特主题音乐（MC唱片）
- [x] 独特生物群系
- [x] 独特欢迎消息
- [x] 粒子效果配置
- [x] 小地图解锁后颜色变化

---

## 📝 后续优化建议

1. **动态音乐系统**：根据剧情情绪切换音乐
2. **渐进式解锁动画**：小地图节点解锁时播放动画
3. **成就系统**：完成关卡后给予成就奖励
4. **回溯功能**：允许玩家重玩已完成关卡
5. **自定义NPC对话**：每个NPC有独特的对话树

---

*生成时间: 2025-01-20*  
*后端版本: v2.stage*  
*插件版本: DriftSystem-DEBUG.jar v2.0*
