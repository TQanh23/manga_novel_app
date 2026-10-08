"""Run the worker: `python -m worker`. `python -m worker --check` is the health probe.

Used instead of the `arq` command so logging is configured before arq writes
its first line, and every line the worker emits is JSON.
"""

import sys

from arq.worker import check_health, run_worker

from api.core.config import get_settings
from api.core.logging import configure_logging
from worker.settings import WorkerSettings


def main() -> None:
    configure_logging(get_settings().log_level)
    if sys.argv[1:] == ["--check"]:
        # 0 while the worker keeps refreshing its health key in Redis.
        sys.exit(check_health(WorkerSettings))  # type: ignore[arg-type]
    run_worker(WorkerSettings)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
