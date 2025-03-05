# Home Assistant Service

This package contains a simple [Home Assistant](https://www.home-assistant.io/) service implementation that can control Home Assistant switches.  In my personal setup, this is used in place of SSRs to control pumps and heating elements.  [Zigbee switches](https://www.ikuu.com.au/product/double-power-point-ip54/) have been installed and integrated with Home Assistant via [Zigbee2MQTT](https://www.zigbee2mqtt.io)

### Config

To set this up, create a Digital Actuator in your service, without assigning it a channel.  Our code will act as the channel, taking signals and sending them to Home Assistant to turn a switch on or off.

You need to provide:

* `mqtt-host` - the host of the MQTT server.  In my case, this is just the IP addres of my Brewblox server
* `block-name` - the block name of the digital actuator you created above
* `hass_url` - the IP or FQDN of the Home Assistant server, including port, like `http://192.168.1.1:8123`
* `hass_token` - [A long lived access token token](https://developers.home-assistant.io/docs/auth_api/#long-lived-access-token)
* `hass_id` - The Home Assistant ID of the device to tie to the Brewblox block (like `switch.hlt_element`)
* `service` - the name of the Brewblox service that contains the block-name

### Sample docker-compose entry

To add the setup to your docker-compose, a sample entry looks like this:

```
  boil-heating-element:
    image: ghcr.io/jmgasper/brewblox-homeassistant:develop
    privileged: true
    restart: unless-stopped
    command: --port 5002 --mqtt-host=192.168.1.36 --block-name="Boil Heating Element" --hass_url="http://192.168.1.219:8123" --hass_token="longtoken" --hass_id="switch.hlt_element" --service="brew-room"
    volumes:
    - type: bind
      source: /etc/localtime
      target: /etc/localtime
      read_only: true
```
