import asyncio
import json
from time import monotonic
from typing import Any

from aiohttp import web
from hassapi import Hass
from brewblox_service import brewblox_logger, features, mqtt

from brewblox_homeassistant.models import ServiceConfig

LOGGER = brewblox_logger(__name__)

class SubscribingFeature(features.ServiceFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)

        self.config: ServiceConfig = app['config']
        self.topic = f'{self.config.state_topic}/{self.config.service}/#'
        self.command_lock = asyncio.Lock()
        self.last_desired_state: int | None = None
        self.last_command_at = 0.0
        self.command_retry_interval = max(float(self.config.poll_interval), 5.0)
        try:
            self.hass = Hass(hassurl=self.config.hass_url, token=self.config.hass_token)
        except Exception:
            LOGGER.exception('Could not connect to Home Assistant')
            raise

    async def startup(self, app: web.Application):
        """Add event handling

        To get messages, you need to call `mqtt.subscribe(topic)` and `mqtt.listen(topic, callback)`.

        You can set multiple listeners for each call to subscribe, and use wildcards to filter messages.
        """
        LOGGER.info('Starting up brewblox_homeassistant plugin')
        while True:
            try:
                await mqtt.listen(app, self.topic, self.on_message)
                await mqtt.subscribe(app, self.topic)
                LOGGER.info('Current switch state: %s', self._get_switch_state())
                LOGGER.info('Startup successful')
                return
            except Exception:
                LOGGER.exception('Error during startup')
                await self._cleanup_subscription(app)
                await asyncio.sleep(3)

    async def shutdown(self, app: web.Application):
        """Shutdown and remove event handlers

        unsubscribe() and unlisten() must be called
        with the same arguments as subscribe() and listen()
        """
        await self._cleanup_subscription(app)

    async def _cleanup_subscription(self, app: web.Application):
        try:
            await mqtt.unsubscribe(app, self.topic)
        except Exception:
            LOGGER.debug('Ignoring MQTT unsubscribe failure for %s', self.topic, exc_info=True)
        try:
            await mqtt.unlisten(app, self.topic, self.on_message)
        except Exception:
            LOGGER.debug('Ignoring MQTT unlisten failure for %s', self.topic, exc_info=True)

    def _get_switch_state(self) -> str | None:
        try:
            entity_state = self.hass.get_state(self.config.hass_id)
        except Exception:
            LOGGER.warning('Failed to read Home Assistant state for %s', self.config.hass_id, exc_info=True)
            return None
        return getattr(entity_state, 'state', None)

    @staticmethod
    def _normalize_desired_state(value: Any) -> int | None:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int) and value in (0, 1):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {'1', 'state_active', 'active', 'on'}:
                return 1
            if normalized in {'0', 'state_inactive', 'inactive', 'off'}:
                return 0
        return None

    def _extract_desired_state(self, payload: dict[str, Any]) -> int | None:
        if payload.get('key') != self.config.service:
            return None

        event_type = payload.get('type')
        data = payload.get('data') or {}

        if event_type == 'Spark.state':
            blocks = data.get('blocks') or []
        elif event_type == 'Spark.patch':
            blocks = data.get('changed') or []
        else:
            return None

        for block in blocks:
            if block.get('id') != self.config.block_name:
                continue
            return self._normalize_desired_state((block.get('data') or {}).get('desiredState'))
        return None

    async def on_message(self, topic: str, payload: str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            LOGGER.warning('Ignoring invalid JSON on topic %s', topic)
            return

        desired_state = self._extract_desired_state(data)
        if desired_state is None:
            return

        async with self.command_lock:
            desired_changed = desired_state != self.last_desired_state
            switch_state = self._get_switch_state()
            target_state = 'on' if desired_state else 'off'

            if switch_state == target_state:
                self.last_desired_state = desired_state
                return

            now = monotonic()
            if not desired_changed and now - self.last_command_at < self.command_retry_interval:
                LOGGER.debug(
                    'Skipping duplicate command for %s while waiting for Home Assistant state to settle',
                    self.config.hass_id,
                )
                return

            LOGGER.info('Setting %s to %s', self.config.hass_id, target_state)
            try:
                if desired_state:
                    self.hass.turn_on(self.config.hass_id)
                else:
                    self.hass.turn_off(self.config.hass_id)
            except Exception:
                LOGGER.warning('Failed to set %s to %s', self.config.hass_id, target_state, exc_info=True)
                return

            self.last_desired_state = desired_state
            self.last_command_at = now

def setup(app: web.Application):
    # We register our feature here
    # It will now be automatically started when the service starts
    LOGGER.info("Starting brewblox-assistant setup")
    features.add(app, SubscribingFeature(app))
    LOGGER.info("Setup successful")


def fget(app: web.Application) -> SubscribingFeature:
    # Retrieve the registered instance of SubscribingFeature
    return features.get(app, SubscribingFeature)
