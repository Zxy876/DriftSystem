data modify storage gm4_balloon_animals:temp temp_source append from storage gm4_balloon_animals:temp trades[0]
data remove storage gm4_balloon_animals:temp trades[0]
execute store success score $trade_applicable gm4_balloon_animals_data if data storage gm4_balloon_animals:temp temp_source[-1].sell.components."minecraft:custom_data".gm4_balloon_animals.trade
execute if score $trade_applicable gm4_balloon_animals_data matches 1 run function gm4_balloon_animals:purchase/trader/check_trade
execute store result score $trade_count gm4_balloon_animals_data run data get storage gm4_balloon_animals:temp trades
execute if score $trade_found gm4_balloon_animals_data matches 0 if score $trade_count gm4_balloon_animals_data matches 1.. run function gm4_balloon_animals:purchase/trader/parse_trades
