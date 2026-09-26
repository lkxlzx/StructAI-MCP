"""Service layer — shared by the REST management API and the MCP tools.

v1.2 §39: 「REST API 是管理与调试接口。MCP Tool 是给 AI Agent 的稳定执行接口。
二者共享 Service Layer。」  This package holds that shared layer.

The Task Engine (V2.1 §26) is split in two:

* :mod:`app.services.task_store` — the durable storage protocol, the
  in-memory implementation (the default) and the ``tasks`` / ``task_events``
  implementation.
* :mod:`app.services.task_service` — the engine itself: state machine,
  concurrency, timeout, retry budget, events.

Application bootstrap must ``await init_task_service()`` once, after the store is
wired and before traffic is served, so that tasks a previous process left behind
are reconciled (:meth:`TaskService.recover_orphans`).
"""

from app.services.task_service import (
    DEFAULT_GLOBAL_CONCURRENCY,
    ORPHAN_STATUSES,
    TERMINAL_STATUSES,
    TaskEventRecord,
    TaskRecord,
    TaskService,
    get_task_service,
    init_task_service,
    reset_task_service,
)
from app.services.task_store import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TASK_TIMEOUT_SECONDS,
    InMemoryTaskStore,
    SqlAlchemyTaskStore,
    SyncTaskStore,
    TaskStore,
)

__all__ = [
    "TaskService",
    "TaskRecord",
    "TaskEventRecord",
    "TaskStore",
    "SyncTaskStore",
    "InMemoryTaskStore",
    "SqlAlchemyTaskStore",
    "DEFAULT_GLOBAL_CONCURRENCY",
    "DEFAULT_TASK_TIMEOUT_SECONDS",
    "DEFAULT_MAX_RETRIES",
    "TERMINAL_STATUSES",
    "ORPHAN_STATUSES",
    "get_task_service",
    "reset_task_service",
    "init_task_service",
]
