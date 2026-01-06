tag @s add gm4_balloon_animal_trader
tag @s add gm4_balloon_animal_trader_new
scoreboard players set $llamas_replaced gm4_balloon_animals_data 0
execute as @e[type=trader_llama, tag=!smithed.entity, distance=..6] run function gm4_balloon_animals:wandering_trader/llama/check_leasher
function gm4_balloon_animals:wandering_trader/pick_two_animals
scoreboard players reset $trader_llama_check gm4_balloon_animals_data
tag @s remove gm4_balloon_animal_trader_new
