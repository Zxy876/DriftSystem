execute as @e[type=wandering_trader, tag=!gm4_trader, tag=!smithed.entity] if data entity @s Offers.Recipes at @s run function gm4_trades-1.6:wandering_trader/modify
schedule function gm4_trades-1.6:main 10s
