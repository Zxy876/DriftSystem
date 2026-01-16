from app.core.ai.intent_engine import parse_intent
from app.core.story.story_engine import story_engine


def test_spawn_entity_rewrites_to_create_block():
    result = parse_intent(
        player_id="tester",
        text="在坐标 10 64 15 放置 minecraft:amethyst_block",
        world_state={},
        story_engine=story_engine,
    )
    intents = result["intents"]
    assert intents, "expected at least one intent"
    assert intents[0]["type"] == "CREATE_BLOCK"
