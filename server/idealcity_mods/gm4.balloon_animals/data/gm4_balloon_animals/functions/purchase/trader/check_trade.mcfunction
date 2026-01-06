execute store result score $uses gm4_balloon_animals_data run data get storage gm4_balloon_animals:temp temp_source[-1].uses
execute if score $uses gm4_balloon_animals_data matches 1 at @s as @e[type=#gm4_balloon_animals:balloon_animal, tag=gm4_balloon_animal, tag=!gm4_balloon_animal_purchased, limit=1] run function gm4_balloon_animals:purchase/animal/search
execute if score $uses gm4_balloon_animals_data matches 1 run function gm4_balloon_animals:purchase/trader/update_trade
