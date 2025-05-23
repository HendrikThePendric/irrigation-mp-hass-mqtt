import re
from json import load
from machine import unique_id


def get_if_valid(key: str, conf: dict, value_type):
    if key not in conf:
        raise Exception(f"Config key `{key}` is missing")

    val = conf[key]

    if not isinstance(val, value_type):
        raise Exception(
            f"Type of `{key}` is `{type(val).__name__}`, expected `{value_type.__name__}`"
        )

    if val == "":
        raise Exception(f"Config key `{key}` is empty")

    return val


def _load_json_file(file_path: str) -> dict:
    with open(file_path) as file:
        conf = load(file)
        return conf


def _clean_string(input: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", input).lower()


def _compute_device_id() -> str:
    device_id_byte_str = unique_id()
    byte_int_list = list(device_id_byte_str)
    byte_str_list = map(str, byte_int_list)
    bytes_str = "".join(byte_str_list)
    last_8_chars = bytes_str[-8:]
    return last_8_chars


class NetworkConfig:
    def __init__(self, conf: dict) -> None:
        self.wifi_ssid: str = get_if_valid("wifi_ssid", conf, str)
        self.wifi_password: str = get_if_valid("wifi_password", conf, str)
        self.mqtt_broker_ip: str = get_if_valid("mqtt_broker_ip", conf, str)


class IrrigationPointConfig:
    def __init__(self, conf: dict) -> None:
        self.name: str = get_if_valid("name", conf, str)
        self.valve_pin: int = get_if_valid("valve_pin", conf, int)
        self.sensor_pin: int = get_if_valid("sensor_pin", conf, int)
        self.id: str = _clean_string(self.name)


class Config:
    def __init__(self, file_path: str) -> None:
        conf = _load_json_file(file_path)
        network_conf: dict = get_if_valid("network", conf, dict)
        irrigation_points_conf: list = get_if_valid("irrigation_points", conf, list)

        self.station_name: str = get_if_valid("station_name", conf, str)
        self.station_id: str = (
            f"{_clean_string(self.station_name)}-{_compute_device_id()}"
        )
        self.network = NetworkConfig(network_conf)
        self.irrigation_points: dict[str, IrrigationPointConfig] = {}

        for irrigation_point_conf in irrigation_points_conf:
            irrigation_point = IrrigationPointConfig(irrigation_point_conf)
            self.irrigation_points[irrigation_point.id] = irrigation_point

    def __str__(self) -> str:
        lines: list[str] = [
            "=== Irrigation station config ===",
            f"station_id: {self.station_id}",
            f"station_name: {self.station_name}",
            "network:",
            f"  wifi_ssid: {self.network.wifi_ssid}",
            f"  wifi_password: {self.network.wifi_password}",
            f"  mqtt_broker_ip: {self.network.mqtt_broker_ip}",
            "irrigation_points:",
        ]
        for ip in self.irrigation_points.values():
            lines.append(f"  id: {ip.id}")
            lines.append(f"    name: {ip.name}")
            lines.append(f"    valve_pin: {str(ip.valve_pin)}")
            lines.append(f"    sensor_pin: {str(ip.sensor_pin)}")

        lines.append("---------------------------------")

        return "\n".join(lines)
