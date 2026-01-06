from beet import Context


def ensure_manifest(ctx: Context) -> None:
    """Populate gm4 manifest cache with minimal entries for local builds."""
    ctx.cache["gm4_manifest"].json = {
        "last_commit": "local",
        "modules": {
            "gm4_balloon_animals": {
                "id": "gm4_balloon_animals",
                "name": "Balloon Animals",
                "version": "1.3.0",
                "hash": "",
                "video_link": "",
                "wiki_link": "https://wiki.gm4.co/wiki/Balloon_Animals",
                "credits": {
                    "Creator": ["TheEpyonProject"],
                    "Icon Design": ["Hozz"],
                },
                "requires": ["lib_trades"],
                "description": "Looking for exotic animals? This module makes some Wandering Traders sell cute baby animals!",
                "recommends": [],
                "minecraft": ["1.20.1"],
                "hidden": False,
                "important_note": None,
                "search_keywords": [],
                "publish_date": None,
                "modrinth_id": "zKRZZHQ3",
                "smithed_link": None,
                "pmc_link": None,
            }
        },
        "libraries": {
            "lib_trades": {
                "id": "gm4_trades",
                "name": "Gamemode 4 Trades",
                "version": "1.6.0",
                "hash": "",
                "video_link": "",
                "wiki_link": "",
                "credits": {
                    "Creator": ["Bloo"],
                },
                "requires": [],
                "description": "Allows datapacks to add trades to wandering traders or villager-like entities.",
                "recommends": [],
                "minecraft": ["1.20.1"],
                "hidden": False,
                "important_note": None,
                "search_keywords": [],
                "publish_date": None,
                "modrinth_id": None,
                "smithed_link": "gm4_lib_trades",
                "pmc_link": None,
            }
        },
        "base": {
            "version": "1.8.0",
        },
        "contributors": [],
    }

    ctx.cache["previous_manifest"].json = {
        "last_commit": "",
        "modules": [],
        "libraries": {},
        "contributors": [],
    }
