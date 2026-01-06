tag @s add gm4_processed_trade_option
scoreboard players set $pools_differ gm4_trades_data 1
data modify storage gm4_trades:temp/wandering_trader/comparison pool set from storage gm4_trades:temp/wandering_trader/current_tradepool pool
execute if data entity @s equipment.body.components."minecraft:custom_data".gm4_trades.pool store success score $pools_differ gm4_trades_data run data modify storage gm4_trades:temp/wandering_trader/comparison pool set from entity @s equipment.body.components."minecraft:custom_data".gm4_trades.pool
data remove storage gm4_trades:temp/wandering_trader/comparison pool
execute if score $pools_differ gm4_trades_data matches 0 run tag @s add gm4_pooled_trade_option
execute as @e[type=trader_llama, tag=gm4_trade_option, tag=!gm4_processed_trade_option, limit=1, sort=arbitrary] run function gm4_trades-1.6:wandering_trader/pool/collect_trades
