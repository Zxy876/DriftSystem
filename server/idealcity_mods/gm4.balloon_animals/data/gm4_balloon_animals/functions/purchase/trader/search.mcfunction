scoreboard players set $trade_found gm4_balloon_animals_data 0
data remove storage gm4_balloon_animals:temp temp_source
data modify storage gm4_balloon_animals:temp trades set from entity @s Offers.Recipes
function gm4_balloon_animals:purchase/trader/parse_trades
tag @s add gm4_balloon_animal_trader_processed
execute if score $trade_found gm4_balloon_animals_data matches 0 as @e[type=wandering_trader, tag=!smithed.entity, tag=gm4_balloon_animal_trader, tag=!gm4_balloon_animal_trader_processed, limit=1] run function gm4_balloon_animals:purchase/trader/search
