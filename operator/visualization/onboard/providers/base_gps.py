"""GPS-provider contract without a device-specific assumption."""

from __future__ import annotations

from abc import ABC, abstractmethod

from visualization.common.models import GPSFix, ProviderStatus


class GPSProvider(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def get_latest(self) -> GPSFix: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def status(self) -> ProviderStatus: ...
