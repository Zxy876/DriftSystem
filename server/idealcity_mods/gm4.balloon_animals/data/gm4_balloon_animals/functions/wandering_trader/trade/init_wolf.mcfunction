tag @s add gm4_balloon_animal
effect give @s levitation infinite 0 true
effect give @s slow_falling infinite 0 true
effect give @s resistance infinite 4 true
data modify entity @s Age set value -2147483648
data modify entity @s leash.UUID set from storage gm4_balloon_animals:temp trader.uuid
execute store result score $variant_id gm4_balloon_animals_data run random value 0..8
execute if score $variant_id gm4_balloon_animals_data matches 0 run data modify entity @s variant set value "minecraft:pale"
execute if score $variant_id gm4_balloon_animals_data matches 1 run data modify entity @s variant set value "minecraft:ashen"
execute if score $variant_id gm4_balloon_animals_data matches 2 run data modify entity @s variant set value "minecraft:black"
execute if score $variant_id gm4_balloon_animals_data matches 3 run data modify entity @s variant set value "minecraft:chestnut"
execute if score $variant_id gm4_balloon_animals_data matches 4 run data modify entity @s variant set value "minecraft:rusty"
execute if score $variant_id gm4_balloon_animals_data matches 5 run data modify entity @s variant set value "minecraft:snowy"
execute if score $variant_id gm4_balloon_animals_data matches 6 run data modify entity @s variant set value "minecraft:spotted"
execute if score $variant_id gm4_balloon_animals_data matches 7 run data modify entity @s variant set value "minecraft:striped"
execute if score $variant_id gm4_balloon_animals_data matches 8 run data modify entity @s variant set value "minecraft:woods"
scoreboard players add $id gm4_balloon_animals_id 1
scoreboard players operation @s gm4_balloon_animals_id = $id gm4_balloon_animals_id
execute store result storage gm4_balloon_animals:temp gm4_balloon_animals.id int 1 run scoreboard players get $id gm4_balloon_animals_id
execute summon trader_llama run function gm4_balloon_animals:wandering_trader/trade/spawn_trade_llama
data modify entity @s CustomName set from storage gm4_balloon_animals:temp CustomName
