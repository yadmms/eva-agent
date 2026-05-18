"""ESP32 thin-node device registry"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class DeviceRegistry:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or Path.home() / ".nuwa_palace" / "devices")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.devices: dict = {}
        self._load()

    def _load(self):
        f = self.data_dir / "devices.json"
        if f.exists():
            self.devices = json.loads(f.read_text())

    def _save(self):
        (self.data_dir / "devices.json").write_text(json.dumps(self.devices, ensure_ascii=False, indent=2))

    def register(self, device_id: str, name: str, capabilities: list[str], pins: dict = None) -> dict:
        """Register a new ESP32 device. Returns device record."""
        self.devices[device_id] = {
            "device_id": device_id,
            "name": name,
            "capabilities": capabilities,
            "pins": pins or {},
            "status": "online",
            "last_seen": datetime.now().isoformat(),
            "reports": [],
        }
        self._save()
        return self.devices[device_id]

    def heartbeat(self, device_id: str) -> bool:
        """Update device last_seen timestamp."""
        if device_id in self.devices:
            self.devices[device_id]["last_seen"] = datetime.now().isoformat()
            self.devices[device_id]["status"] = "online"
            self._save()
            return True
        return False

    def report(self, device_id: str, data: dict) -> bool:
        """Receive sensor data report from device."""
        if device_id in self.devices:
            report = {"time": datetime.now().isoformat(), "data": data}
            self.devices[device_id]["reports"].append(report)
            self.devices[device_id]["reports"] = self.devices[device_id]["reports"][-100:]
            self.devices[device_id]["last_seen"] = datetime.now().isoformat()
            self._save()
            return True
        return False

    def list_devices(self) -> list[dict]:
        return list(self.devices.values())

    def get_device(self, device_id: str) -> Optional[dict]:
        return self.devices.get(device_id)


_registry: Optional[DeviceRegistry] = None


def get_registry() -> DeviceRegistry:
    global _registry
    if _registry is None:
        _registry = DeviceRegistry()
    return _registry
