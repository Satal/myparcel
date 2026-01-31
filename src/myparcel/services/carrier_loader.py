"""Service for loading and managing carrier adapters."""

import importlib.util
from pathlib import Path

from myparcel.carriers.base import BaseCarrier, CarrierConfig
from myparcel.config import settings


class CarrierLoader:
    """Loads carrier adapters from the carriers directory."""

    def __init__(self, carriers_dir: Path | None = None):
        self.carriers_dir = carriers_dir or settings.carriers_dir
        self._carriers: dict[str, BaseCarrier] = {}
        self._configs: dict[str, CarrierConfig] = {}

    def load_all(self) -> dict[str, BaseCarrier]:
        """Load all carrier adapters from the carriers directory."""
        if self._carriers:
            return self._carriers

        for carrier_dir in self.carriers_dir.iterdir():
            if not carrier_dir.is_dir():
                continue
            if carrier_dir.name.startswith("_") or carrier_dir.name.startswith("."):
                continue

            self._load_carrier(carrier_dir)

        return self._carriers

    def _load_carrier(self, carrier_dir: Path) -> None:
        """Load a single carrier adapter."""
        config_path = carrier_dir / "carrier.yaml"
        tracker_path = carrier_dir / "tracker.py"

        if not config_path.exists():
            print(f"Skipping {carrier_dir.name}: no carrier.yaml")
            return

        try:
            config = CarrierConfig.from_yaml(config_path)
        except Exception as e:
            print(f"Error loading config for {carrier_dir.name}: {e}")
            return

        if not config.enabled:
            print(f"Skipping {carrier_dir.name}: disabled")
            return

        self._configs[config.id] = config

        if not tracker_path.exists():
            print(f"Warning: {carrier_dir.name} has no tracker.py")
            return

        try:
            # Dynamically load the tracker module
            spec = importlib.util.spec_from_file_location(
                f"myparcel.carriers.{carrier_dir.name}.tracker",
                tracker_path,
            )
            if spec is None or spec.loader is None:
                print(f"Error loading tracker for {carrier_dir.name}: invalid spec")
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the carrier class (should be a subclass of BaseCarrier)
            carrier_class = None
            for name in dir(module):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseCarrier)
                    and obj is not BaseCarrier
                ):
                    carrier_class = obj
                    break

            if carrier_class is None:
                print(f"No carrier class found in {tracker_path}")
                return

            # Instantiate the carrier
            carrier = carrier_class(config)
            self._carriers[config.id] = carrier
            print(f"Loaded carrier: {config.name}")

        except Exception as e:
            print(f"Error loading tracker for {carrier_dir.name}: {e}")

    def get_carrier(self, carrier_id: str) -> BaseCarrier | None:
        """Get a carrier by ID."""
        if not self._carriers:
            self.load_all()
        return self._carriers.get(carrier_id)

    def get_config(self, carrier_id: str) -> CarrierConfig | None:
        """Get a carrier config by ID."""
        if not self._configs:
            self.load_all()
        return self._configs.get(carrier_id)

    def detect_carrier(self, tracking_number: str) -> list[BaseCarrier]:
        """Detect which carriers might handle a tracking number.

        Returns a list of carriers whose patterns match, ordered by specificity.
        """
        if not self._carriers:
            self.load_all()

        matches = []
        for carrier in self._carriers.values():
            if carrier.matches_tracking_number(tracking_number):
                matches.append(carrier)

        return matches

    def list_carriers(self) -> list[CarrierConfig]:
        """List all loaded carrier configurations."""
        if not self._configs:
            self.load_all()
        return list(self._configs.values())


# Global carrier loader instance
carrier_loader = CarrierLoader()
