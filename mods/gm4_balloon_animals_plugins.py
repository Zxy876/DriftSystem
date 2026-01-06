from beet import Context
from bolt.runtime import Runtime


ENTRYPOINTS = ["**"]

def beet_default(ctx: Context) -> None:
    """Ensure bolt runs and evaluates all templated modules."""
    ctx.require("bolt")
    runtime = ctx.inject(Runtime)
    runtime.evaluate.add_entrypoint(ENTRYPOINTS)
    if 'gm4_balloon_animals' in ctx.data:
        print(
            "[gm4_balloon_animals_plugins] Loot tables present:",
            sorted(ctx.data['gm4_balloon_animals'].loot_tables.keys()),
        )
