import asyncio
import json
from types import SimpleNamespace

from brewblox_homeassistant.subscribe import SubscribingFeature


class FakeHass:
    def __init__(self, state='off'):
        self.state = state
        self.turn_on_calls = []
        self.turn_off_calls = []

    def get_state(self, entity_id):
        return SimpleNamespace(state=self.state)

    def turn_on(self, entity_id):
        self.turn_on_calls.append(entity_id)

    def turn_off(self, entity_id):
        self.turn_off_calls.append(entity_id)


def make_feature():
    app = {
        'config': SimpleNamespace(
            state_topic='brewcast/state',
            service='brew-room',
            block_name='Boil Heating Element',
            hass_url='http://homeassistant.local:8123',
            hass_token='token',
            hass_id='switch.boil_element',
            poll_interval=5,
        ),
    }
    feature = SubscribingFeature(app)
    feature.hass = FakeHass()
    return feature


def test_extracts_desired_state_from_state_event():
    feature = make_feature()

    payload = {
        'key': 'brew-room',
        'type': 'Spark.state',
        'data': {
            'blocks': [
                {
                    'id': 'Boil Heating Element',
                    'data': {
                        'desiredState': 'STATE_ACTIVE',
                    },
                }
            ]
        },
    }

    assert feature._extract_desired_state(payload) == 1


def test_extracts_desired_state_from_patch_event():
    feature = make_feature()

    payload = {
        'key': 'brew-room',
        'type': 'Spark.patch',
        'data': {
            'changed': [
                {
                    'id': 'Boil Heating Element',
                    'data': {
                        'desiredState': 'STATE_INACTIVE',
                    },
                }
            ]
        },
    }

    assert feature._extract_desired_state(payload) == 0


def test_on_message_ignores_non_state_events():
    feature = make_feature()

    payload = json.dumps({
        'key': 'brew-room',
        'data': {
            'Boil Heating Element': {
                'desiredState': 1,
            }
        },
    })

    asyncio.run(feature.on_message('brewcast/history/brew-room', payload))

    assert feature.hass.turn_on_calls == []
    assert feature.hass.turn_off_calls == []


def test_on_message_deduplicates_repeated_on_commands():
    feature = make_feature()
    payload = json.dumps({
        'key': 'brew-room',
        'type': 'Spark.patch',
        'data': {
            'changed': [
                {
                    'id': 'Boil Heating Element',
                    'data': {
                        'desiredState': 'STATE_ACTIVE',
                    },
                }
            ]
        },
    })

    asyncio.run(feature.on_message('brewcast/state/brew-room/patch', payload))
    asyncio.run(feature.on_message('brewcast/state/brew-room/patch', payload))

    assert feature.hass.turn_on_calls == ['switch.boil_element']
    assert feature.hass.turn_off_calls == []


def test_on_message_retries_after_throttle_window():
    feature = make_feature()
    payload = json.dumps({
        'key': 'brew-room',
        'type': 'Spark.patch',
        'data': {
            'changed': [
                {
                    'id': 'Boil Heating Element',
                    'data': {
                        'desiredState': 'STATE_ACTIVE',
                    },
                }
            ]
        },
    })

    asyncio.run(feature.on_message('brewcast/state/brew-room/patch', payload))
    feature.last_command_at -= feature.command_retry_interval
    asyncio.run(feature.on_message('brewcast/state/brew-room/patch', payload))

    assert feature.hass.turn_on_calls == ['switch.boil_element', 'switch.boil_element']
