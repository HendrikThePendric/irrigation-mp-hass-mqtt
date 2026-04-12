# MQTT Topics

The station connects to the MQTT broker over TLS (port 8883) with client certificates. All topics use the station's hardware-derived `station_id` (last 8 hex digits of the Pico's unique ID).

## Topic patterns

| Pattern | Direction | Description |
|---------|-----------|-------------|
| `irrigation/{station_id}/availability` | Publish | Device online/offline status |
| `irrigation/{station_id}/{point_id}/sensor` | Publish | Soil moisture reading |
| `irrigation/{station_id}/{point_id}/valve/state` | Publish | Current valve state |
| `irrigation/{station_id}/{point_id}/valve/set` | Subscribe | Valve open/close commands |
| `irrigation/{station_id}/broker_connectivity` | Publish | Connectivity test messages |
| `homeassistant/sensor/{station_id}-{point_id}/config` | Publish | HA sensor discovery |
| `homeassistant/valve/{station_id}-{point_id}/config` | Publish | HA valve discovery |
| `homeassistant/status` | Subscribe | HA restart detection |

## Published messages

### Availability

**Topic:** `irrigation/{station_id}/availability`

Published on connect with payload `"online"` (retained). The MQTT last will testament (LWT) automatically publishes `"offline"` if the device disconnects unexpectedly.

### Sensor state

**Topic:** `irrigation/{station_id}/{point_id}/sensor`

JSON payload with moisture percentage (0-100):

```json
{"moisture": 42.5}
```

Published at the interval configured by `publish_interval_minutes`. The value is the smoothed average of multiple readings taken during the publish cycle. Retained.

### Valve state

**Topic:** `irrigation/{station_id}/{point_id}/valve/state`

Plain text payload: `"open"` or `"closed"`. Published whenever the valve state changes. Retained.

### Broker connectivity test

**Topic:** `irrigation/{station_id}/broker_connectivity`

Plain text payload: `"broker_connectivity_test_{ticks_ms}"`. Used internally to verify the MQTT connection is alive.

### Discovery messages

Discovery messages register the device and its entities with Home Assistant using the [MQTT discovery protocol](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery). They are published on startup and again if Home Assistant restarts.

#### Sensor discovery

**Topic:** `homeassistant/sensor/{station_id}-{point_id}/config`

```json
{
  "name": "Location A Moisture",
  "unique_id": "locationa_sensor",
  "device_class": "moisture",
  "state_class": "measurement",
  "unit_of_measurement": "%",
  "state_topic": "irrigation/{station_id}/{point_id}/sensor",
  "value_template": "{{ value_json.moisture }}",
  "availability_topic": "irrigation/{station_id}/availability",
  "device": {
    "identifiers": ["{station_id}"],
    "name": "Backyard irrigation station",
    "manufacturer": "HenkNet IoT",
    "model": "Raspberry Pi Pico 2 W",
    "sw_version": "0.1"
  }
}
```

#### Valve discovery

**Topic:** `homeassistant/valve/{station_id}-{point_id}/config`

```json
{
  "name": "Location A Valve",
  "unique_id": "locationa_valve",
  "state_topic": "irrigation/{station_id}/{point_id}/valve/state",
  "command_topic": "irrigation/{station_id}/{point_id}/valve/set",
  "payload_open": "open",
  "payload_close": "closed",
  "state_open": "open",
  "state_closed": "closed",
  "optimistic": true,
  "availability_topic": "irrigation/{station_id}/availability",
  "device_class": "water",
  "device": { ... }
}
```

All discovery messages are published with `retain=True`.

## Subscriptions

### Valve commands

**Topic:** `irrigation/{station_id}/{point_id}/valve/set`

Payload: `"open"` or `"closed"`.

The station subscribes to the command topic for each irrigation point. When a command is received, the station opens or closes the corresponding valve and publishes the new state.

### Home Assistant status

**Topic:** `homeassistant/status`

When Home Assistant publishes `"online"` (after a restart), the station re-publishes its availability and all discovery messages so entities are re-registered.

## Reconnection behavior

On MQTT reconnection, the station automatically:

1. Re-publishes availability as `"online"`
2. Re-subscribes to `homeassistant/status`
3. Re-subscribes to all valve command topics
