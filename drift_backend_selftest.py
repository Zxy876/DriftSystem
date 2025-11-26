import requests
import json
from pprint import pprint

BASE = "http://127.0.0.1:8000"   # 根据你实际情况改
PLAYER = "test_player"
TEST_LEVEL_ID = "1"              # 你现有的某个关卡 id，比如 "1" / "01" 等
TIMEOUT = 15


def pretty(title, data):
    print("\n" + "=" * 60)
    print(">>> " + title)
    print("-" * 60)
    if isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def test_story_levels():
    print("\n[1] 测试 /story/levels")
    r = requests.get(f"{BASE}/story/levels", timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    pretty("关卡列表", data)
    return data


def test_story_load():
    print("\n[2] 测试 /story/load/{player}/{level}")
    url = f"{BASE}/story/load/{PLAYER}/{TEST_LEVEL_ID}"
    r = requests.post(url, json={}, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    pretty("加载关卡返回", data)
    return data


def test_story_advance_say(content: str):
    """
    这里的 body 结构要和你后端实际的 Pydantic 模型对应。
    我先按最通用的：{"world_state": {}, "action": {...}} 来写。
    如果你的实现是 {"input": "..."}，也可以把 payload 改成那样。
    """
    print(f"\n[3] 测试 /story/advance/{PLAYER}  自然语言: {content!r}")
    payload = {
        "world_state": {},
        "action": {
            "type": "say",
            "content": content
        }
    }
    url = f"{BASE}/story/advance/{PLAYER}"
    r = requests.post(url, json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    pretty("推进剧情返回", data)
    return data


def test_tree_add_and_state():
    print("\n[4] 测试 Tree: /add + /state + /backtrack")
    # 1) 玩家写一段自己的剧情
    payload = {"content": "我拒绝这个安排，我要走向湖对面的塔楼。"}
    r = requests.post(f"{BASE}/add", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    pretty("Tree /add 返回", r.json())

    # 2) 查看当前 tree 状态
    r2 = requests.get(f"{BASE}/state", timeout=TIMEOUT)
    r2.raise_for_status()
    pretty("Tree /state 返回", r2.json())

    # 3) 回退一步
    r3 = requests.post(f"{BASE}/backtrack", json={}, timeout=TIMEOUT)
    r3.raise_for_status()
    pretty("Tree /backtrack 返回", r3.json())


def test_dsl_run_and_levels():
    print("\n[5] 测试 DSL /run 注入新关卡")

    # 你可以在这里写一个极简 dsl，后端解析后生成 level_dsl_test。
    script = """
    {
      "level_id": "dsl_test",
      "title": "来自 DSL 的测试关卡",
      "summary": "这是通过 /run 注入的新剧情。",
      "entry_node": {
        "title": "DSL 入口",
        "text": "你走进由脚本书写的世界。"
      }
    }
    """

    r = requests.post(f"{BASE}/run", json={"script": script}, timeout=TIMEOUT)
    r.raise_for_status()
    pretty("DSL /run 返回", r.json())

    # 再次查看 story levels，看是否出现 "dsl_test"
    r2 = requests.get(f"{BASE}/story/levels", timeout=TIMEOUT)
    r2.raise_for_status()
    levels = r2.json()
    pretty("DSL 注入后 /story/levels 返回", levels)

    has_dsl = any(
        isinstance(x, dict) and x.get("id") == "dsl_test"
        for x in (levels if isinstance(levels, list) else [])
    )
    print("\n[检查] 关卡列表中是否包含 dsl_test:", has_dsl)
    return has_dsl


if __name__ == "__main__":
    print("=== DriftSystem 后端能力自检 ===")

    # 1. 关卡
    levels = test_story_levels()

    # 2. 加载一个关卡
    load_ret = test_story_load()

    # 3. 自然语言推进几次（包括造物）
    adv1 = test_story_advance_say("我环顾四周。")
    adv2 = test_story_advance_say("在我旁边造一张桌子和一把椅子。")
    adv3 = test_story_advance_say("召唤一个叫 小玉兔 的兔子 npc 和我说话。")

    # 4. Tree：拒绝剧情，写自己的分支
    test_tree_add_and_state()

    # 5. DSL：注入一个新关卡
    has_dsl = test_dsl_run_and_levels()

    print("\n=== 总结 ===")
    print("1) Story levels/加载/推进 是否正常返回 JSON？")
    print("2) advance 的 JSON 里是否有你设计的 node / world_patch 结构？")
    print("3) Tree add/state/backtrack 是否正常？")
    print("4) DSL /run 是否真的把 dsl_test 注入到 levels 中？")
    print("如果以上都 OK，则后端已经达到可以对接 MC 前端的水准。")
