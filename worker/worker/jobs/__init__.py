# Importing this package registers every job and cron with the runtime.
from worker.jobs import ping, publish_scheduled  # noqa: F401
