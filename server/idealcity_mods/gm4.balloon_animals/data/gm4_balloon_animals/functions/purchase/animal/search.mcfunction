execute store result score $id gm4_balloon_animals_data run data get storage gm4_balloon_animals:temp temp_source[-1].sell.components."minecraft:custom_data".gm4_balloon_animals.id
execute as @e[type=#gm4_balloon_animals:balloon_animal, tag=gm4_balloon_animal, tag=!gm4_balloon_animal_purchased] if score @s gm4_balloon_animals_id = $id gm4_balloon_animals_data run function gm4_balloon_animals:purchase/animal/update
execute unless score $trade_success gm4_balloon_animals_data matches 1 run playsound entity.villager.no neutral @a[distance=..8] ~ ~ ~
