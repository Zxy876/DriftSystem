# initializes the newly created pool with a pool name
# @s = the first trade option in the pool (arbitrary sorting)
# at position of wandering trader
# run from gm4_trades:wandering_trader/create_pool

# mark trade option as pooled and processed, to prevent self comparison
tag @s add gm4_pooled_trade_option
tag @s add gm4_processed_trade_option

# read current trade pool name space (supports both 1.20.1 tag NBT and 1.20.5 components)
scoreboard players set $use_components gm4_trades_data 0
execute if data entity @s equipment.body.components."minecraft:custom_data".gm4_trades.pool run scoreboard players set $use_components gm4_trades_data 1
execute if score $use_components gm4_trades_data matches 1 run data modify storage gm4_trades:temp/wandering_trader/current_tradepool pool set from entity @s equipment.body.components."minecraft:custom_data".gm4_trades.pool
execute unless score $use_components gm4_trades_data matches 1 if data entity @s DecorItem.tag.gm4_trades.pool run data modify storage gm4_trades:temp/wandering_trader/current_tradepool pool set from entity @s DecorItem.tag.gm4_trades.pool

# compare to next trade option's pool
execute as @e[type=trader_llama,tag=gm4_trade_option,tag=!gm4_pooled_trade_option,limit=1,sort=arbitrary] run function gm4_trades:wandering_trader/pool/collect_trades

# clean up tag and storage (tag cleanup is very important here!)
tag @e[type=trader_llama,tag=gm4_trade_option] remove gm4_processed_trade_option
data remove storage gm4_trades:temp/wandering_trader/current_tradepool pool
