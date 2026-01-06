from pathlib import Path
from typing import Iterable, List

from beet import Context
from beet.library.data_pack import EntityTypeTag, Function, LootTable

from gm4.utils import CSV


def beet_default(ctx: Context):

    # read csv file
    animals_csv = CSV.from_file(Path('gm4_balloon_animals', 'animals.csv'))
    animals: List = list(animals_csv)
    
    # sort animals into a common and a rare group
    rare_animals: List[str] = []
    common_animals: List[str] = []
    for animal in animals:
        if animal['rare'] == "TRUE":
            rare_animals.append(str(animal['id']))
            continue
        common_animals.append(str(animal['id']))

    # sort each group alphabetically to ensure .csv-independent id assignments
    rare_animals.sort()
    common_animals.sort()

    # set variants
    wolf_variants = ["minecraft:pale", "minecraft:ashen", "minecraft:black", "minecraft:chestnut", "minecraft:rusty", "minecraft:snowy", "minecraft:spotted", "minecraft:striped", "minecraft:woods"]
    farm_variants = ["minecraft:warm", "minecraft:temperate","minecraft:cold"]
    chicken_eggs = ["egg", "blue_egg", "brown_egg"]

    # store to meta
    ctx.meta['animals'] = animals
    ctx.meta['enumeration'] = [*common_animals, *rare_animals]
    ctx.meta['rare_start'] = len(common_animals)
    ctx.meta['wolf_variants'] = wolf_variants
    ctx.meta['farm_variants'] = farm_variants
    ctx.meta['chicken_eggs'] = chicken_eggs

    _populate_entity_type_tag(ctx, animals)
    _populate_loot_tables(ctx, animals, ctx.meta['enumeration'], ctx.meta['rare_start'])
    _populate_functions(
        ctx,
        animals,
        ctx.meta['enumeration'],
        wolf_variants,
        farm_variants,
        chicken_eggs,
    )


def _populate_entity_type_tag(ctx: Context, animals: Iterable) -> None:
    values = sorted({str(row['id']) for row in animals})
    ctx.data['gm4_balloon_animals'].entity_type_tags['balloon_animal'] = EntityTypeTag(
        {
            'values': values,
        }
    )


def _populate_loot_tables(
    ctx: Context,
    animals: Iterable,
    enumeration: List[str],
    rare_start: int,
) -> None:
    ctx.data['gm4_balloon_animals'].loot_tables['technical/random/pick_common'] = LootTable(
        {
            'pools': [
                {
                    'rolls': {
                        'type': 'minecraft:uniform',
                        'min': 0,
                        'max': max(rare_start - 1, 0),
                    },
                    'entries': [
                        {
                            'type': 'minecraft:item',
                            'name': 'minecraft:stone',
                        }
                    ],
                }
            ]
        }
    )

    ctx.data['gm4_balloon_animals'].loot_tables['technical/random/pick_rare'] = LootTable(
        {
            'pools': [
                {
                    'rolls': {
                        'type': 'minecraft:uniform',
                        'min': rare_start,
                        'max': max(len(enumeration) - 1, rare_start),
                    },
                    'entries': [
                        {
                            'type': 'minecraft:item',
                            'name': 'minecraft:stone',
                        }
                    ],
                }
            ]
        }
    )

    entries = []
    for row in animals:
        function = str(row['function'])
        if function not in {"init_animal", "init_wolf", "init_farm"}:
            continue

        animal_id = str(row['id'])
        try:
            index = enumeration.index(animal_id)
        except ValueError:
            continue

        for name in map(str.strip, str(row['names']).split(',')):
            if not name:
                continue
            entries.append(
                {
                    'type': 'minecraft:item',
                    'name': 'minecraft:lead',
                    'functions': [
                        {
                            'function': 'minecraft:copy_custom_data',
                            'source': {
                                'type': 'minecraft:storage',
                                'source': 'gm4_balloon_animals:temp',
                            },
                            'ops': [
                                {
                                    'source': 'gm4_balloon_animals',
                                    'target': 'gm4_balloon_animals',
                                    'op': 'merge',
                                }
                            ],
                        },
                        {
                            'function': 'minecraft:set_name',
                            'entity': 'this',
                            'target': 'item_name',
                            'name': str(row['type']),
                        },
                        {
                            'function': 'minecraft:set_lore',
                            'entity': 'this',
                            'lore': [
                                {
                                    'text': name,
                                    'color': 'gray',
                                }
                            ],
                            'mode': 'replace_all',
                        },
                    ],
                    'conditions': [
                        {
                            'condition': 'minecraft:value_check',
                            'value': {
                                'type': 'minecraft:score',
                                'target': {
                                    'type': 'minecraft:fixed',
                                    'name': '$animal_id',
                                },
                                'score': 'gm4_balloon_animals_data',
                            },
                            'range': {
                                'min': index,
                                'max': index,
                            },
                        }
                    ],
                }
            )

    ctx.data['gm4_balloon_animals'].loot_tables['lead'] = LootTable(
        {
            'pools': [
                {
                    'rolls': 1,
                    'entries': entries,
                }
            ]
        }
    )
    ctx.log.debug('Generated %d lead entries.', len(entries))

    ctx.data['gm4_balloon_animals'].loot_tables['bee_nest'] = LootTable(
        {
            'pools': [
                {
                    'rolls': 1,
                    'entries': [
                        {
                            'type': 'minecraft:item',
                            'name': 'minecraft:bee_nest',
                            'functions': [
                                {
                                    'function': 'minecraft:set_nbt',
                                    'tag': '{BlockEntityTag:{Occupants:[{EntityData:{id:"minecraft:bee"},TicksInHive:0,MinTicksInHive:0}]}}',
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )

    for color, display in (
        ('brown', {'text': 'Brown Egg', 'color': 'gold'}),
        ('blue', {'text': 'Blue Egg', 'color': 'aqua'}),
    ):
        ctx.data['gm4_balloon_animals'].loot_tables[f'chicken_egg/{color}_egg'] = LootTable(
            {
                'pools': [
                    {
                        'rolls': 1,
                        'entries': [
                            {
                                'type': 'minecraft:item',
                                'name': 'minecraft:egg',
                                'functions': [
                                    {
                                        'function': 'minecraft:set_count',
                                        'count': 8,
                                    },
                                    {
                                        'function': 'minecraft:set_name',
                                        'entity': 'this',
                                        'target': 'item_name',
                                        'name': display,
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        )
    ctx.log.debug('Generated chicken egg variants: %%s', chicken_eggs)


def _populate_functions(
    ctx: Context,
    animals: Iterable,
    enumeration: List[str],
    wolf_variants: List[str],
    farm_variants: List[str],
    chicken_eggs: List[str],
) -> None:
    ctx.data['gm4_balloon_animals'].functions['wandering_trader/trade/pick_animal'] = Function(
        _build_pick_animal_commands(animals, enumeration)
    )

    ctx.data['gm4_balloon_animals'].functions['wandering_trader/trade/init_wolf'] = Function(
        _build_variant_commands('wolf', wolf_variants)
    )

    ctx.data['gm4_balloon_animals'].functions['wandering_trader/trade/init_farm'] = Function(
        _build_variant_commands('farm', farm_variants)
    )

    ctx.data['gm4_balloon_animals'].functions['wandering_trader/trade/add_chicken_egg'] = Function(
        _build_add_chicken_egg_commands(chicken_eggs)
    )

    ctx.data['gm4_balloon_animals'].functions['init'] = Function(
        _build_init_commands(len(farm_variants), len(wolf_variants), len(chicken_eggs))
    )


def _build_pick_animal_commands(animals: Iterable, enumeration: List[str]) -> str:
    commands = [
        '# @s = wandering trader and no trader llamas, tag=gm4_balloon_animal_trader,tag=gm4_balloon_animal_trader_new',
        '# at @s',
        '# run from wandering_trader/pick_two_animals',
        '',
        'execute store result score $animal_id gm4_balloon_animals_data run loot spawn ~ ~-4096 ~ loot gm4_balloon_animals:technical/random/enumeration_value',
    ]

    for row in animals:
        function = str(row['function'])
        animal_id = str(row['id'])
        try:
            index = enumeration.index(animal_id)
        except ValueError:
            continue

        if function not in {"init_animal", "init_wolf", "init_farm"}:
            summon_target = 'minecraft:trader_llama'
        else:
            summon_target = animal_id

        commands.append(
            'execute if score $animal_id gm4_balloon_animals_data matches {index} '
            'summon {summon} run function gm4_balloon_animals:wandering_trader/trade/{fn}'.format(
                index=index,
                summon=summon_target,
                fn=function,
            )
        )

    return '\n'.join(commands) + '\n'


def _build_variant_commands(kind: str, variants: List[str]) -> str:
    header = [
        f'# @s = {"wolf" if kind == "wolf" else "farm animal"} to be attached to trader, type=#gm4_balloon_animals:balloon_animal',
        '# at wandering trader with no llamas, tag=gm4_balloon_animal_trader,tag=gm4_balloon_animal_trader_new',
        '# run from wandering_trader/trade/pick_animal',
        '',
        'tag @s add gm4_balloon_animal',
        '',
        'effect give @s levitation infinite 0 true',
        'effect give @s slow_falling infinite 0 true',
        'effect give @s resistance infinite 4 true',
        '',
        'data modify entity @s Age set value -2147483648',
        'data modify entity @s leash.UUID set from storage gm4_balloon_animals:temp trader.uuid',
        '',
        'scoreboard players add $variant_seed gm4_balloon_animals_data 1',
        'scoreboard players set $variant_id gm4_balloon_animals_data 0',
        'scoreboard players operation $variant_id gm4_balloon_animals_data = $variant_seed gm4_balloon_animals_data',
        f'scoreboard players operation $variant_id gm4_balloon_animals_data %= ${kind}_variant_count gm4_balloon_animals_data',
    ]

    variant_commands = [
        'execute if score $variant_id gm4_balloon_animals_data matches {idx} '
        'run data modify entity @s variant set value "{variant}"'.format(idx=index, variant=variant)
        for index, variant in enumerate(variants)
    ]

    footer = [
        '',
        'scoreboard players add $id gm4_balloon_animals_id 1',
        'scoreboard players operation @s gm4_balloon_animals_id = $id gm4_balloon_animals_id',
        'execute store result storage gm4_balloon_animals:temp gm4_balloon_animals.id int 1 run scoreboard players get $id gm4_balloon_animals_id',
        '',
        'execute summon trader_llama run function gm4_balloon_animals:wandering_trader/trade/spawn_trade_llama',
        '',
        'data modify entity @s CustomName set from storage gm4_balloon_animals:temp CustomName',
        '',
    ]

    return '\n'.join(header + variant_commands + footer)


def _build_add_chicken_egg_commands(chicken_eggs: List[str]) -> str:
    commands = [
        '# @s = trader llama',
        '# at wandering trader with no llamas, tag=gm4_balloon_animal_trader,tag=gm4_balloon_animal_trader_new',
        '# run from wandering_trader/trade/pick_animal',
        '',
        'tp @s ~ 0 ~',
        '',
        'data merge entity @s {Silent:1b,NoGravity:1b,Invulnerable:1b,ChestedHorse:1b,Variant:0,Strength:1,DespawnDelay:1,Tags:["gm4_trade_option"],Items:[{id:"minecraft:emerald",Count:2b,Slot:1b,tag:{gm4_trades:{options:{maxUses:4,rewardXp:1b,xp:1,priceMultiplier:0.05f}}}}],DecorItem:{id:"minecraft:light_blue_carpet",Count:1b,tag:{gm4_trades:{options:{maxUses:4,rewardXp:1b,xp:1,priceMultiplier:0.05f}}}}}',
        '',
        'scoreboard players add $variant_seed gm4_balloon_animals_data 1',
        'scoreboard players set $variant_id gm4_balloon_animals_data 0',
        'scoreboard players operation $variant_id gm4_balloon_animals_data = $variant_seed gm4_balloon_animals_data',
        'scoreboard players operation $variant_id gm4_balloon_animals_data %= $egg_variant_count gm4_balloon_animals_data',
    ]

    commands.extend(
        'execute if score $variant_id gm4_balloon_animals_data matches {idx} run loot replace entity @s horse.0 loot gm4_balloon_animals:chicken_egg/{variant}'.format(
            idx=index,
            variant=variant,
        )
        for index, variant in enumerate(chicken_eggs)
    )

    commands.append('')
    return '\n'.join(commands)


def _build_init_commands(farm_count: int, wolf_count: int, egg_count: int) -> str:
    return '\n'.join(
        [
            '',
            'scoreboard objectives add gm4_balloon_animals_data dummy',
            'scoreboard objectives add gm4_balloon_animals_id dummy',
            '',
            '# legacy-compatible counters used to emulate randomness on 1.20.1',
            'scoreboard players set $variant_seed gm4_balloon_animals_data 0',
            f'scoreboard players set $farm_variant_count gm4_balloon_animals_data {farm_count}',
            f'scoreboard players set $wolf_variant_count gm4_balloon_animals_data {wolf_count}',
            f'scoreboard players set $egg_variant_count gm4_balloon_animals_data {egg_count}',
            '',
            'execute unless score balloon_animals gm4_modules matches 1 run data modify storage gm4:log queue append value {type:"install",module:"Balloon Animals"}',
            'execute unless score balloon_animals gm4_earliest_version < balloon_animals gm4_modules run scoreboard players operation balloon_animals gm4_earliest_version = balloon_animals gm4_modules',
            'scoreboard players set balloon_animals gm4_modules 1',
            '',
            'schedule function gm4_balloon_animals:main 1t',
            '',
        ]
    )
