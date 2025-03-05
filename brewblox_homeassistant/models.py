"""
Pydantic models are declared here, and then imported wherever needed
"""

from brewblox_service.models import BaseServiceConfig


class ServiceConfig(BaseServiceConfig):
    """
    This model extends the default configuration from brewblox-service,
    and adds the arguments that were added to the parser in __main__.py
    """
    poll_interval: float
    block_name: str
    hass_url: str
    hass_token: str
    hass_id: str
    service: str

