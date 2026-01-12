import os

os.environ.setdefault('IDEAL_CITY_AI_DISABLE', '1')

from app.core.ideal_city.pipeline import IdealCityPipeline, DeviceSpecSubmission

pipeline = IdealCityPipeline()
submission = DeviceSpecSubmission(player_id='tester', narrative='我要搭建一个工坊', scenario_id='default')
pipeline.submit(submission)
state = pipeline.cityphone_state('tester', 'default')

print('INTERPRETATION')
for line in state.city_interpretation:
    print(line)

print('UNKNOWN')
for line in state.unknowns:
    print(line)

print('HISTORY')
for line in state.history_entries:
    print(line)

print('GALLERY')
for section in state.narrative.sections:
    if section.slot == 'gallery_status':
        for line in section.body:
            print(line)
    if section.slot == 'open_questions':
        print('OPEN')
        for line in section.body:
            print(line)

print('LAST', state.narrative.last_event)

print('APPENDIX')
for section in state.narrative.sections:
    if section.slot == 'archive_appendix':
        for line in section.body:
            print(line)

print('MODE')
print(state.exhibit_mode.description)
