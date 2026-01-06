data modify storage gm4_balloon_animals:temp temp_source[-1].uses set value 2
data modify storage gm4_balloon_animals:temp temp_source append from storage gm4_balloon_animals:temp trades[]
data modify entity @s Offers.Recipes set from storage gm4_balloon_animals:temp temp_source
