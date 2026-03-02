"""
System Monitor Service.

Tracks the real-time state of the ingestion pipeline and NLP processing
to provide live feedback to the UI via HTMX widgets.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class PipelineState:
    """Snapshot of the current system state."""

    is_ingesting: bool = False
    current_source: str | None = None
    current_task: str = (
        "Idle"  # e.g. "Fetching RSS", "Extracting content", "Classifying"
    )
    items_queued: int = 0  # Found in RSS but not yet processed
    items_processed: int = 0  # Successfully ingested/updated in this cycle
    items_classified: int = 0  # NLP classification completed in this cycle
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SystemMonitor:
    """Singleton monitor for system status."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemMonitor, cls).__new__(cls)
            cls._instance._state = PipelineState()
        return cls._instance

    @property
    def state(self) -> PipelineState:
        return self._state

    def start_cycle(self):
        """Mark cycle as started (counters are cumulative)."""
        self._state.is_ingesting = True
        self._state.current_source = None
        self._state.current_task = "Starting ingestion cycle..."
        self._touch()

    def end_cycle(self):
        """Mark cycle as finished."""
        self._state.is_ingesting = False
        self._state.current_source = None
        self._state.current_task = "Idle"
        self._touch()

    def set_source(self, source_name: str):
        self._state.current_source = source_name
        self._touch()

    def set_task(self, task_description: str):
        self._state.current_task = task_description
        self._touch()

    def add_queued(self, count: int):
        self._state.items_queued += count
        self._touch()

    def add_processed(self, count: int = 1):
        self._state.items_processed += count
        self._touch()

    def add_classified(self, count: int = 1):
        self._state.items_classified += count
        self._touch()

    def _touch(self):
        self._state.last_update = datetime.now(timezone.utc)

    def get_snapshot(self) -> dict:
        """Return a dict representation suitable for API response."""
        data = asdict(self._state)
        # Convert datetime to ISO string for JSON serialization
        data["last_update"] = data["last_update"].isoformat()
        return data


# Global instance
monitor = SystemMonitor()
