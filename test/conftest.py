import logging
import sys
import types


def _install_brewblox_service_stub():
    if 'brewblox_service' in sys.modules:
        return

    brewblox_service = types.ModuleType('brewblox_service')

    def brewblox_logger(name: str):
        return logging.getLogger(name)

    class ServiceFeature:
        def __init__(self, app):
            self.app = app

    _features_key = '_features'

    def add(app, feature):
        app.setdefault(_features_key, {})[type(feature)] = feature

    def get(app, cls):
        return app[_features_key][cls]

    async def _noop(*args, **kwargs):
        return None

    brewblox_service.brewblox_logger = brewblox_logger
    brewblox_service.features = types.SimpleNamespace(
        ServiceFeature=ServiceFeature,
        add=add,
        get=get,
    )
    brewblox_service.mqtt = types.SimpleNamespace(
        listen=_noop,
        subscribe=_noop,
        unsubscribe=_noop,
        unlisten=_noop,
    )

    models = types.ModuleType('brewblox_service.models')

    class BaseServiceConfig:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    models.BaseServiceConfig = BaseServiceConfig

    sys.modules['brewblox_service'] = brewblox_service
    sys.modules['brewblox_service.models'] = models


def _install_hass_stub():
    if 'hassapi' in sys.modules:
        return

    hassapi = types.ModuleType('hassapi')

    class Hass:
        def __init__(self, *args, **kwargs):
            pass

    hassapi.Hass = Hass
    sys.modules['hassapi'] = hassapi


_install_brewblox_service_stub()
_install_hass_stub()
