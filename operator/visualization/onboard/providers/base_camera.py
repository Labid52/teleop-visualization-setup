"""Camera-provider contract independent of any camera driver."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from visualization.common.models import FrameMetadata, ProviderStatus
from visualization.onboard.providers.errors import ProviderFailure


@dataclass(frozen=True)
class CameraFrame:
    metadata: FrameMetadata
    image: Any


class CameraProvider(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def get_frame(self) -> CameraFrame: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def status(self) -> ProviderStatus: ...
