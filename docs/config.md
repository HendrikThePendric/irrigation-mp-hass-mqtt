# Configuration

The irrigation station reads its configuration from `config.json` in the project root. A template is provided in `config.template.json`.

## Example

```json
{
  "station_name": "Backyard irrigation station",
  "network": {
    "wifi_ssid": "MyNetwork",
    "wifi_password": "MyPassword",
    "mqtt_broker_ip": "192.168.1.100"
  },
  "rolling_window": 3,
  "ema_alpha": 0.2,
  "publish_interval_minutes": 5,
  "max_valve_open_time_minutes": 45,
  "irrigation_points": [
    {
      "name": "Location A",
      "valve_pin": 2,
      "ads_address": "0x48",
      "ads_channel": 0
    },
    {
      "name": "Location B",
      "valve_pin": 3,
      "ads_address": "0x49",
      "ads_channel": 1
    }
  ]
}
```

## Fields

### Station settings

| Field | Type | Description |
|-------|------|-------------|
| `station_name` | string | Human-readable station name. Used in Home Assistant device info and to derive the MQTT client ID. |

### Network

| Field | Type | Description |
|-------|------|-------------|
| `network.wifi_ssid` | string | WiFi network name. |
| `network.wifi_password` | string | WiFi password. |
| `network.mqtt_broker_ip` | string | IP address of the MQTT broker. |

### Sensor smoothing

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rolling_window` | int | 3 | Number of sensor readings to average before publishing. Must be > 0. |
| `ema_alpha` | float | 0.2 | Exponential moving average alpha (0.0 - 1.0). Lower values = smoother, higher = more responsive. |

### Timing

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `publish_interval_minutes` | int | 5 | How often sensor values are published to MQTT (in minutes). Must be > 0. |
| `max_valve_open_time_minutes` | int | 45 | Safety limit: valves automatically close after this many minutes. Must be > 0. |

A derived value `measurement_interval` is calculated as `publish_interval / rolling_window` (in seconds). This determines how often the sensor is read within each publish cycle. If this value would be zero (e.g., `rolling_window` larger than `publish_interval`), startup fails with an error.

### Irrigation points

The `irrigation_points` array defines each sensor/valve pair. You can have up to 8 points.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Location label (e.g., "Front garden"). Used in Home Assistant entity names. Also used to derive the point ID (lowercased, non-alphanumeric characters stripped). |
| `valve_pin` | int | GPIO pin number on the Pico connected to the relay for this valve. |
| `ads_address` | string | I2C address of the ADS1115 module as a hex string. Valid values: `"0x48"`, `"0x49"`, `"0x4A"`, `"0x4B"`. |
| `ads_channel` | int | Channel on the ADS1115 for this sensor. Valid values: 0, 1, 2, 3. |

The `rolling_window` and `ema_alpha` values from the top level are automatically applied to each irrigation point.

## Derived values

These are computed at startup from the configuration and are not set in the JSON file:

| Value | How it's derived |
|-------|-----------------|
| `station_id` | Last 8 hex digits of the Pico's hardware unique ID. |
| `station_mqtt_id` | `{cleaned_station_name}-{station_id}` (e.g., `backyardirrigationstation-a1b2c3d4`). Used as the MQTT client ID. |
| `point_id` | Derived from `name` by lowercasing and stripping non-alphanumeric characters (e.g., "Location A" becomes `locationa`). |
| `publish_interval` | `publish_interval_minutes * 60` (seconds). |
| `max_valve_open_time` | `max_valve_open_time_minutes * 60` (seconds). |
| `measurement_interval` | `publish_interval // rolling_window` (seconds). |

## Validation

The configuration is validated at startup. The station will not start if:

- Any required field is missing
- Any field has the wrong type
- Any string field is empty
- `rolling_window` is not > 0
- `ema_alpha` is not between 0.0 and 1.0
- `publish_interval_minutes` is not > 0
- `max_valve_open_time_minutes` is not > 0
- `ads_address` is not one of `0x48`, `0x49`, `0x4A`, `0x4B`
- `ads_channel` is not between 0 and 3
- `measurement_interval` would be 0 (increase `publish_interval` or decrease `rolling_window`)

## Security

`config.json` contains WiFi credentials and is excluded from git. Copy `config.template.json` to `config.json` and fill in your values.
