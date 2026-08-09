import re
from json import dump, load

# Default calibration voltages (in volts) for soil moisture sensors.
# These match the SENSOR_DRY / SENSOR_WET constants in sensor.py.
# Used as fallback when calibration.json has no entry for a point.
_DEFAULT_DRY_V: float = 2.4  # 0.48 normalized * 5.0
_DEFAULT_WET_V: float = 0.95  # 0.19 normalized * 5.0
from machine import unique_id


def _get_if_valid(key: str, conf: dict, value_type: type) -> any:  # type: ignore
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
    return "".join(f"{b:02x}" for b in unique_id())[-8:]


def _parse_ads_address(conf: dict) -> int:
    """Fetch and validate ADS1115 address from config dict."""
    ads_address_str: str = _get_if_valid("ads_address", conf, str)
    try:
        address = int(ads_address_str.strip(), 16)
    except ValueError:
        raise ValueError(
            f"Invalid ads_address '{ads_address_str}': must be a valid hexadecimal string (e.g., '0x48')"
        )

    valid_addresses = [0x48, 0x49, 0x4A, 0x4B]
    if address not in valid_addresses:
        raise ValueError(
            f"Invalid ads_address {hex(address)}: must be one of {', '.join(hex(a) for a in valid_addresses)}"
        )

    return address


def _get_publish_interval(conf: dict) -> int:
    """Extract and convert publish_interval_minutes to milliseconds."""
    publish_interval_minutes: int = _get_if_valid("publish_interval_minutes", conf, int)
    return publish_interval_minutes * 60


def _get_max_valve_open_time(conf: dict) -> int:
    """Extract and convert max_valve_open_time_minutes to seconds."""
    max_valve_open_time_minutes: int = _get_if_valid(
        "max_valve_open_time_minutes", conf, int
    )
    return max_valve_open_time_minutes * 60


def _parse_ads_channel(conf: dict) -> int:
    """Fetch and validate ADS1115 channel index."""
    channel: int = _get_if_valid("ads_channel", conf, int)
    if not 0 <= channel <= 3:
        raise ValueError(
            f"Config key `ads_channel` must be between 0 and 3, got {channel}"
        )
    return channel


class NetworkConfig:
    def __init__(self, conf: dict) -> None:
        self.wifi_ssid: str = _get_if_valid("wifi_ssid", conf, str)
        self.wifi_password: str = _get_if_valid("wifi_password", conf, str)
        self.mqtt_broker_ip: str = _get_if_valid("mqtt_broker_ip", conf, str)


class IrrigationPointConfig:
    def __init__(self, conf: dict) -> None:
        self.name: str = _get_if_valid("name", conf, str)
        self.valve_pin: int = _get_if_valid("valve_pin", conf, int)
        self.ads_address: int = _parse_ads_address(conf)
        self.ads_channel: int = _parse_ads_channel(conf)
        self.id: str = _clean_string(self.name)
        # These will be set from global config
        self.rolling_window: int = 5
        self.ema_alpha: float = 0.2
        # Sensor calibration voltages — set by Config from calibration.json
        self.dry_voltage: float | None = None
        self.wet_voltage: float | None = None


class Config:
    def __init__(self, file_path: str) -> None:
        conf = _load_json_file(file_path)
        network_conf: dict = _get_if_valid("network", conf, dict)
        irrigation_points_conf: list = _get_if_valid("irrigation_points", conf, list)

        self.station_name: str = _get_if_valid("station_name", conf, str)
        self.station_id: str = _compute_device_id()
        self.station_mqtt_id: str = (
            f"{_clean_string(self.station_name)}-{self.station_id}"
        )
        self.network = NetworkConfig(network_conf)
        self.irrigation_points: dict[str, IrrigationPointConfig] = {}

        # Global smoothing parameters
        self.rolling_window: int = _get_if_valid("rolling_window", conf, int)
        if self.rolling_window <= 0:
            raise ValueError(f"rolling_window must be > 0, got {self.rolling_window}")

        self.ema_alpha: float = _get_if_valid("ema_alpha", conf, float)
        if not 0.0 <= self.ema_alpha <= 1.0:
            raise ValueError(
                f"ema_alpha must be between 0.0 and 1.0, got {self.ema_alpha}"
            )

        # Publish interval in minutes, converted to seconds
        self.publish_interval: int = _get_publish_interval(conf)
        if self.publish_interval <= 0:
            raise ValueError(
                f"publish_interval must be > 0, got {self.publish_interval}"
            )

        # Maximum valve open time in minutes, converted to seconds
        self.max_valve_open_time: int = _get_max_valve_open_time(conf)
        if self.max_valve_open_time <= 0:
            raise ValueError(
                f"max_valve_open_time must be > 0, got {self.max_valve_open_time}"
            )

        # Measurement interval in seconds (publish_interval // rolling_window)
        self.measurement_interval: int = self.publish_interval // self.rolling_window
        if self.measurement_interval <= 0:
            raise ValueError(
                f"measurement_interval would be {self.measurement_interval} "
                f"(publish_interval={self.publish_interval} // rolling_window={self.rolling_window}). "
                "Increase publish_interval or decrease rolling_window."
            )

        for irrigation_point_conf in irrigation_points_conf:
            irrigation_point = IrrigationPointConfig(irrigation_point_conf)
            # Copy global smoothing params to each point for convenience
            irrigation_point.rolling_window = self.rolling_window
            irrigation_point.ema_alpha = self.ema_alpha
            self.irrigation_points[irrigation_point.id] = irrigation_point

        self._load_calibration()

    def _load_calibration(self) -> None:
        """Load per-point calibration from calibration.json, falling back to defaults."""
        self._calibration_data: dict[str, dict[str, float]] = {}
        try:
            with open("calibration.json") as f:
                file_data: dict = load(f)
        except Exception:
            file_data = {}

        for point_id, point in self.irrigation_points.items():
            cal = file_data.get(point_id, {})
            dry = cal.get("dry_v")
            wet = cal.get("wet_v")

            point.dry_voltage = float(dry) if dry is not None else _DEFAULT_DRY_V
            point.wet_voltage = float(wet) if wet is not None else _DEFAULT_WET_V

            if point_id in file_data:
                self._calibration_data[point_id] = {
                    k: float(v) for k, v in file_data[point_id].items()
                }

    def update_calibration(
        self, point_id: str, dry_v: float | None = None, wet_v: float | None = None
    ) -> None:
        """Update calibration voltages for a point and persist to calibration.json."""
        if point_id not in self.irrigation_points:
            raise ValueError(f"Unknown irrigation point: {point_id}")
        point = self.irrigation_points[point_id]
        if dry_v is not None:
            point.dry_voltage = dry_v
        if wet_v is not None:
            point.wet_voltage = wet_v
        if point_id not in self._calibration_data:
            self._calibration_data[point_id] = {}
        if dry_v is not None:
            self._calibration_data[point_id]["dry_v"] = dry_v
        if wet_v is not None:
            self._calibration_data[point_id]["wet_v"] = wet_v
        self._save_calibration()

    def _save_calibration(self) -> None:
        """Write current calibration data to calibration.json."""
        with open("calibration.json", "w") as f:
            dump(self._calibration_data, f)

    def __str__(self) -> str:
        lines: list[str] = [
            "Irrigation station config:",
            f"station_id:       {self.station_id}",
            f"station_mqtt_id:  {self.station_mqtt_id}",
            f"station_name:     {self.station_name}",
            "network:",
            f"  wifi_ssid:      {self.network.wifi_ssid}",
            f"  mqtt_broker_ip: {self.network.mqtt_broker_ip}",
            f"rolling_window:   {self.rolling_window}",
            f"ema_alpha:        {self.ema_alpha}",
            f"publish_interval: {self.publish_interval} seconds",
            f"max_valve_open_time: {self.max_valve_open_time} seconds",
            f"measurement_interval: {self.measurement_interval} seconds",
            "irrigation_points:",
        ]
        for ip in self.irrigation_points.values():
            lines.append(f"  id:             {ip.id}")
            lines.append(f"    name:         {ip.name}")
            lines.append(f"    valve_pin:    {str(ip.valve_pin)}")
            lines.append(f"    ads_address:  {hex(ip.ads_address)}")
            lines.append(f"    ads_channel:  {str(ip.ads_channel)}")
            lines.append(f"    rolling_window: {ip.rolling_window}")
            lines.append(f"    ema_alpha:    {ip.ema_alpha}")

        return "\n".join(lines)
