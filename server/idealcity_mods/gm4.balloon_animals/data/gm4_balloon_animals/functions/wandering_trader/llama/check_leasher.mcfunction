execute store result score $trader_llama_check gm4_balloon_animals_data on leasher if entity @s[tag=gm4_balloon_animal_trader_new]
execute if score $trader_llama_check gm4_balloon_animals_data matches 1 run function gm4_balloon_animals:wandering_trader/llama/kill
