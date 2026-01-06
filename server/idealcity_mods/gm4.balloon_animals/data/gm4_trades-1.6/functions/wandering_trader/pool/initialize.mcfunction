tag @s add gm4_pooled_trade_option
tag @s add gm4_processed_trade_option
data modify storage gm4_trades:temp/wandering_trader/current_tradepool pool set from entity @s equipment.body.components."minecraft:custom_data".gm4_trades.pool
execute as @e[type=trader_llama, tag=gm4_trade_option, tag=!gm4_pooled_trade_option, limit=1, sort=arbitrary] run function gm4_trades-1.6:wandering_trader/pool/collect_trades
tag @e[type=trader_llama, tag=gm4_trade_option] remove gm4_processed_trade_option
data remove storage gm4_trades:temp/wandering_trader/current_tradepool pool
