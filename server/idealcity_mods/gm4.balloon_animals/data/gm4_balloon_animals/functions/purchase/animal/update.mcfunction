tag @s add gm4_balloon_animal_purchased
scoreboard players set $trade_success gm4_balloon_animals_data 1
data modify entity @s leash.UUID set from storage gm4_balloon_animals:temp player.uuid
tag @s add gm4_balloon_animal_newly_purchased
schedule function gm4_balloon_animals:purchase/animal/locate_cleanse 10
