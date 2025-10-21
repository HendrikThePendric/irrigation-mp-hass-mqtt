import re
from json import load
from machine import unique_id


def get_if_valid(key: str, conf: dict, value_type: type) -> any:  # type: ignore
    if key not in conf:
        raise KeyError(f"Config key `{key}` is missing")

    val = conf[key]

    if not isinstance(val, value_type):
        raise TypeError(
            f"Type of `{key}` is `{type(val).__name__}, expected `{value_type.__name__}`"
        )

    if val == "":
        raise ValueError(f"Config key `{key}` is empty")

    return val


def _load_json_file(file_path: str) -> dict:
    with open(file_path) as file:
        conf = load(file)
        return conf


def _clean_string(input: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", input).lower()


def _compute_device_id() -> str:
    # Use last 8 hex digits of unique_id for a standard device ID
    return ''.join(f'{b:02x}' for b in unique_id())[-8:]


def _parse_ads_address(ads_address_str: str) -> int:
    """Parse and validate ADS1115 address from hex string."""
    try:
        address = int(ads_address_str, 16)
    except ValueError:
        raise ValueError(f"Invalid ads_address '{ads_address_str}': must be a valid hexadecimal string (e.g., '0x48')")
    
    valid_addresses = [0x48, 0x49, 0x4A, 0x4B]
    if address not in valid_addresses:
        raise ValueError(f"Invalid ads_address {hex(address)}: must be one of {', '.join(hex(a) for a in valid_addresses)}")
    
    return address


def _get_publish_interval_ms(conf: dict) -> int:
    """Extract and convert publish_interval_minutes to milliseconds."""
    publish_interval_minutes: int = get_if_valid("publish_interval_minutes", conf, int)
    return publish_interval_minutes * 60 * 1000


class NetworkConfig:
    def __init__(self, conf: dict) -> None:
        self.wifi_ssid: str = get_if_valid("wifi_ssid", conf, str)
        self.wifi_password: str = get_if_valid("wifi_password", conf, str)
        self.mqtt_broker_ip: str = get_if_valid("mqtt_broker_ip", conf, str)


class IrrigationPointConfig:
    def __init__(self, conf: dict) -> None:
        self.name: str = get_if_valid("name", conf, str)
        self.valve_pin: int = get_if_valid("valve_pin", conf, int)
        self.mosfet_pin: int = get_if_valid("mosfet_pin", conf, int)
        ads_address_str: str = get_if_valid("ads_address", conf, str)
        self.ads_address: int = _parse_ads_address(ads_address_str)
        self.ads_channel: int = get_if_valid("ads_channel", conf, int)
        self.id: str = _clean_string(self.name)
        # These will be set from global config
        self.rolling_window: int = 5
        self.ema_alpha: float = 0.2


class Config:
    def __init__(self, file_path: str) -> None:
        conf = _load_json_file(file_path)
        network_conf: dict = get_if_valid("network", conf, dict)
        irrigation_points_conf: list = get_if_valid("irrigation_points", conf, list)

        self.station_name: str = get_if_valid("station_name", conf, str)
        self.station_id: str = _compute_device_id()
        self.station_mqtt_id: str = (
            f"{_clean_string(self.station_name)}-{self.station_id}"
        )
        self.network = NetworkConfig(network_conf)
        self.irrigation_points: dict[str, IrrigationPointConfig] = {}

        # Global smoothing parameters
        self.rolling_window: int = get_if_valid("rolling_window", conf, int)
        self.ema_alpha: float = get_if_valid("ema_alpha", conf, float)

        # Publish interval in minutes, converted to ms
        self.publish_interval_ms: int = _get_publish_interval_ms(conf)

        for irrigation_point_conf in irrigation_points_conf:
            irrigation_point = IrrigationPointConfig(irrigation_point_conf)
            # Copy global smoothing params to each point for convenience
            irrigation_point.rolling_window = self.rolling_window
            irrigation_point.ema_alpha = self.ema_alpha
            self.irrigation_points[irrigation_point.id] = irrigation_point

    def __str__(self) -> str:
        lines: list[str] = [
            "Irrigation station config:",
            f"station_id:       {self.station_id}",
            f"station_mqtt_id:  {self.station_mqtt_id}",
            f"station_name:     {self.station_name}",
            "network:",
            f"  wifi_ssid:      {self.network.wifi_ssid}",
            f"  wifi_password:  {self.network.wifi_password}",
            f"  mqtt_broker_ip: {self.network.mqtt_broker_ip}",
            f"rolling_window:   {self.rolling_window}",
            f"ema_alpha:        {self.ema_alpha}",
            f"publish_interval: {self.publish_interval_ms // 60000} min ({self.publish_interval_ms} ms)",
            "irrigation_points:",
        ]
        for ip in self.irrigation_points.values():
            lines.append(f"  id:             {ip.id}")
            lines.append(f"    name:         {ip.name}")
            lines.append(f"    valve_pin:    {str(ip.valve_pin)}")
            lines.append(f"    mosfet_pin:   {str(ip.mosfet_pin)}")
            lines.append(f"    ads_address:  {hex(ip.ads_address)}")
            lines.append(f"    ads_channel:  {str(ip.ads_channel)}")
            lines.append(f"    rolling_window: {ip.rolling_window}")
            lines.append(f"    ema_alpha:    {ip.ema_alpha}")

        return "\n".join(lines)
