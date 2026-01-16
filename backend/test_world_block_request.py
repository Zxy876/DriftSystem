from app.api.world_api import _looks_like_block_request
from app.core.intent_creation import CreationIntentDecision


def _decision(materials):
    return CreationIntentDecision(
        is_creation=True,
        confidence=0.9,
        reasons=[],
        slots={"materials": materials},
    )


def test_block_keyword_in_message():
    decision = _decision(["amethyst"])
    assert _looks_like_block_request("放一个紫水晶方块", decision)


def test_minecraft_resource_in_materials():
    decision = _decision(["minecraft:amethyst_block"])
    assert _looks_like_block_request("帮我放这个", decision)


def test_non_block_spawn_request():
    decision = _decision(["minecraft:armor_stand"])
    assert not _looks_like_block_request("召唤一下盔甲架", decision)
