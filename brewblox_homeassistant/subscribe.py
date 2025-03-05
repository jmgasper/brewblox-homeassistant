from aiohttp import web
import time
import json
from hassapi import Hass
from brewblox_service import brewblox_logger, features, mqtt

from brewblox_homeassistant.models import ServiceConfig

LOGGER = brewblox_logger(__name__)

class SubscribingFeature(features.ServiceFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)
        
        self.config: ServiceConfig = app['config']
        self.topic = f'{self.config.history_topic}/#'
        try:
            self.hass = Hass(hassurl=self.config.hass_url, token=self.config.hass_token)
        except Exception as e:
            LOGGER.error("Couldn't connect to Home Assistant " + e)

    async def startup(self, app: web.Application):
        """Add event handling

        To get messages, you need to call `mqtt.subscribe(topic)` and `mqtt.listen(topic, callback)`.

        You can set multiple listeners for each call to subscribe, and use wildcards to filter messages.
        """
        LOGGER.info("Starting up brewblox_homeassistant plugin")
        failed = True
        while(failed):
            try:
                time.sleep(10)
                await mqtt.listen(app, self.topic, self.on_message)
                await mqtt.subscribe(app, self.topic)
                #self.current_state =
                LOGGER.info("Current switch state: " + self.hass.get_state(self.config.hass_id).state)
                failed = False
            except Exception as e:
                LOGGER.error("Error during startup: " + e)
                LOGGER.error("Retrying...")
                time.sleep(3)
                failed = True
        LOGGER.info("Startup successful")

    async def shutdown(self, app: web.Application):
        """Shutdown and remove event handlers

        unsubscribe() and unlisten() must be called
        with the same arguments as subscribe() and listen()
        """
        await mqtt.unsubscribe(app, self.topic)
        await mqtt.unlisten(app, self.topic, self.on_message)

    async def on_message(self, topic: str, payload: str):
        data = json.loads(payload)
        if(data['key']==self.config.service and self.config.block_name in data['data'].keys()):
            block = data['data'][self.config.block_name]
            # Turn on or off, depending on desired state
            changed = False
            if(block['desiredState'] == 1 and (block['state']==None or block['state']==0 or self.hass.get_state(self.config.hass_id).state == 'off')):
                while(self.hass.get_state(self.config.hass_id).state == 'off'):
                    LOGGER.info("Waiting for switch....")
                    self.hass.turn_on(self.config.hass_id)
                    time.sleep(2)
                LOGGER.info("Switch turned on successfully")
                block['state']=1
                changed = True
            elif(block['desiredState'] == 0 and (block['state']==None or block['state']==1 or self.hass.get_state(self.config.hass_id).state == 'on')):
                while(self.hass.get_state(self.config.hass_id).state == 'off'):
                    LOGGER.info("Waiting for switch....")
                    self.hass.turn_off(self.config.hass_id)
                    time.sleep(2)
                LOGGER.info("Switch turned off successfully")
                block['state']=0
                changed = True

            # Publish the updated state, but only if we changed the value
            if(changed == True):
                data['data'][self.config.block_name]=block
                LOGGER.info("Updated block " + self.config.block_name + json.dumps(data))
                await mqtt.publish(self.app,
                        topic,
                        json.dumps({
                            'key': self.config.service,
                            'data': data['data']
                        }))

def setup(app: web.Application):
    # We register our feature here
    # It will now be automatically started when the service starts
    LOGGER.info("Staring brewblox-assistant setup")
    features.add(app, SubscribingFeature(app))
    LOGGER.info("Setup successful")


def fget(app: web.Application) -> SubscribingFeature:
    # Retrieve the registered instance of SubscribingFeature
    return features.get(app, SubscribingFeature)
