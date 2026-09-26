"""In-process asynchronous publish/subscribe for the REST/SSE layer.

Authoritative sources
---------------------
* v1.2 §21 任务实时 SSE — ``GET /api/v1/tasks/{task_id}/stream``; the event names
  and their payloads are owned by that table.
* v1.2 §22.3 日志 SSE — ``GET /api/v1/logs/stream``.
* 总纲 §4.3.1 / v1.2 §3.3 — exception 1 of the four: an SSE stream answers with
  ``text/event-stream`` and is therefore **not** wrapped in the REST envelope.
* V2.1 §26.3 「事件」 / §10.3 — ``task_events`` is append-only and every row
  carries the monotonic ``id`` that the ``since`` cursor is expressed in.

Why an in-process bus and not a message broker
----------------------------------------------
The Task Engine and the SSE endpoints live in **one** process (V2.1 §1.3 rule 8:
SQLite is the default deployment).  A broker would add a dependency and a second
source of truth for event ordering; the store already is the source of truth, and
this bus is only the *wake-up* channel that turns "a row was appended" into "the
open stream writes a chunk now".  Nothing here is durable on purpose: a client
that reconnects re-reads the durable rows through the ``since`` / ``Last-Event-ID``
cursor (v1.2 §21), so a lost in-process notification costs nothing but latency.

Design
------
* ``EventBus.publish(topic, event)`` hands the event to every live subscription on
  that topic with ``asyncio.Queue.put_nowait`` — **publish wakes subscribers
  directly**; there is no polling loop anywhere in this module.
* ``EventBus.subscribe(topic)`` returns a :class:`Subscription`: an explicit
  object with ``__aiter__`` / ``__anext__`` / ``close()``, which is what lets the
  SSE handler release it from ``client_close_handler_callable`` (the place
  ``sse_starlette`` documents for exactly that) and from a generator ``finally``.
* Multiple subscribers per topic are independent: ``publish`` iterates a **copy**
  of the subscriber list, so a subscription that closes mid-publish cannot affect
  the others, and a slow one cannot block the rest.

Slow-subscriber policy (bounded memory, documented)
---------------------------------------------------
Every subscription owns a **bounded** queue (``DEFAULT_SUBSCRIBER_QUEUE_SIZE``,
default 256 entries).  An unbounded queue is the one failure mode that turns a
stalled browser into a server-side memory leak, so it is not an option.

On overflow the bus **drops the oldest** buffered event, keeps the newest one, and
increments :attr:`Subscription.dropped`.  The two candidate policies are not
equivalent for this domain:

* *terminate the subscription* would silently kill a stream the client is still
  reading, and the client would have to notice a dead socket;
* *drop-oldest* keeps the **most recent** state, which is the half that matters —
  in particular a terminal ``failed`` / ``finished`` event is never the one
  dropped, so the stream still terminates on its own.

The counter is not silent: :attr:`Subscription.dropped` is readable at any time
and the SSE generators turn a growth in it into an SSE **comment** line
(``: dropped N event(s)``), which a client can log without a new event name being
invented (v1.2 §21 closes the task event-name table).

Threading
---------
An ``asyncio.Queue`` belongs to the event loop that first awaits it.  Publish and
consume must therefore happen on **one** loop; the Task Engine and the SSE
handlers share the application loop, so that holds.  ``publish`` is deliberately
``async`` even though it never awaits, so a future out-of-loop producer has a
single place to grow a ``call_soon_threadsafe`` hop instead of a second API.
"""

import asyncio
from typing import Any, AsyncIterator, Dict, Final, List, Optional

__all__ = [
    "EventBus",
    "Subscription",
    "TASKS_TOPIC",
    "TASK_TOPIC_PREFIX",
    "DEFAULT_SUBSCRIBER_QUEUE_SIZE",
    "task_topic",
]


#: The **global** topic every task event is mirrored onto.  v1.2 §22.3's log
#: stream and a dashboard feed both read it; v1.2 §21's per-task stream reads
#: ``task:<task_id>`` instead.
TASKS_TOPIC: Final[str] = "tasks"

#: Prefix of the per-task topic.  Deliberately *not* a business ID prefix
#: (总纲 §4.1.3 is a closed set and this is a bus topic, not an identifier).
TASK_TOPIC_PREFIX: Final[str] = "task:"

#: Default per-subscriber queue bound, in events.  Large enough that a normal
#: consumer never overflows, small enough that a stalled one cannot grow without
#: bound.
DEFAULT_SUBSCRIBER_QUEUE_SIZE: Final[int] = 256

#: Wake-up sentinel handed to a consumer that is parked on ``queue.get()`` when
#: its subscription closes.  Never leaves this module.
_CLOSED: Final[object] = object()


def task_topic(task_id: str) -> str:
    """Topic name for one task's stream (v1.2 §21).

    ``task:<task_id>`` — the ``task_id`` already carries the 总纲 §4.1.4 ``task_``
    prefix, so the topic reads ``task:task_20260925_000001``.
    """
    return f"{TASK_TOPIC_PREFIX}{task_id}"


class Subscription:
    """One subscriber's bounded mailbox on one topic.

    Produced by :meth:`EventBus.subscribe`; consumed with ``async for``.  The
    iteration ends (``StopAsyncIteration``) exactly when :meth:`close` runs, which
    is what makes ``close()`` safe to call from a ``finally`` block *and* from a
    disconnect callback at the same time — the second call is a no-op.
    """

    def __init__(self, bus: "EventBus", topic: str, *, maxsize: int) -> None:
        self._bus: Optional["EventBus"] = bus
        self._topic: str = topic
        self._queue: Optional[asyncio.Queue[Any]] = asyncio.Queue(maxsize=maxsize)
        self._maxsize: int = int(maxsize)
        self._dropped: int = 0
        self._closed: bool = False

    # ------------------------------------------------------------------ #
    # introspection
    # ------------------------------------------------------------------ #
    @property
    def topic(self) -> str:
        """The topic this subscription is attached to."""
        return self._topic

    @property
    def maxsize(self) -> int:
        """The bound of the mailbox, in events."""
        return self._maxsize

    @property
    def dropped(self) -> int:
        """How many events the slow-subscriber policy has discarded so far.

        Monotonic per subscription; see the module docstring for the policy.
        """
        return self._dropped

    @property
    def pending(self) -> int:
        """How many events are buffered right now (never exceeds ``maxsize``)."""
        queue = self._queue
        return queue.qsize() if queue is not None else 0

    @property
    def closed(self) -> bool:
        """True once :meth:`close` has run (or the bus has shut down)."""
        return self._closed

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Subscription topic={self._topic!r} pending={self.pending} "
            f"dropped={self._dropped} closed={self._closed}>"
        )

    # ------------------------------------------------------------------ #
    # iteration
    # ------------------------------------------------------------------ #
    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self

    async def __anext__(self) -> Dict[str, Any]:
        """Await the next event; raise ``StopAsyncIteration`` once closed."""
        queue = self._queue
        if queue is None:  # pragma: no cover - _queue is only nulled by a subclass
            raise StopAsyncIteration
        if self._closed and queue.empty():
            # The close sentinel has already been consumed; a further step must
            # end the loop rather than park forever on an empty queue.
            raise StopAsyncIteration
        item = await queue.get()
        if item is _CLOSED:
            raise StopAsyncIteration
        return item

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    async def close(self) -> None:
        """Detach from the bus and release the mailbox.  **Idempotent.**

        Called from two places on purpose, because either can be the first to
        notice that the consumer is gone:

        * the SSE generator's ``finally`` (the stream ended on its own), and
        * ``EventSourceResponse(client_close_handler_callable=...)`` (the client
          hung up while the generator was still parked on the queue).

        Whatever is still buffered is dropped — the consumer is gone, so keeping
        those events alive would be the memory growth this bound exists to
        prevent — and a sentinel is left behind so a coroutine parked inside
        :meth:`__anext__` wakes up and ends its ``async for`` instead of hanging.
        """
        if self._closed:
            return
        self._closed = True
        bus = self._bus
        self._bus = None
        if bus is not None:
            bus._forget(self)
        queue = self._queue
        if queue is None:
            return
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        try:
            queue.put_nowait(_CLOSED)
        except asyncio.QueueFull:  # pragma: no cover - the drain above empties it
            pass

    # ------------------------------------------------------------------ #
    # producer side (called by EventBus.publish)
    # ------------------------------------------------------------------ #
    def _offer(self, event: Dict[str, Any]) -> bool:
        """Buffer ``event``; on overflow drop the oldest.  Returns "buffered"."""
        if self._closed:
            return False
        queue = self._queue
        if queue is None:  # pragma: no cover - close() nulls _bus, not _queue
            return False
        try:
            queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            # Documented slow-subscriber policy: drop-oldest, count it, keep the
            # newest event (see the module docstring for why not "terminate").
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - QueueFull implies not
                pass
            self._dropped += 1
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - one slot was just freed
                self._dropped += 1
                return False
            return True


class EventBus:
    """Topic -> subscribers fan-out with bounded per-subscriber mailboxes.

    One instance per application, created by :func:`app.main.create_app` and
    handed to :class:`app.services.task_service.TaskService` as ``event_bus``.
    """

    def __init__(self, *, queue_size: int = DEFAULT_SUBSCRIBER_QUEUE_SIZE) -> None:
        if int(queue_size) < 1:
            raise ValueError(f"queue_size 必须 >= 1，收到 {queue_size!r}")
        self._queue_size: int = int(queue_size)
        self._subscribers: Dict[str, List[Subscription]] = {}
        self._closed: bool = False

    # ------------------------------------------------------------------ #
    # introspection
    # ------------------------------------------------------------------ #
    @property
    def queue_size(self) -> int:
        """The bound applied to every new subscription's mailbox."""
        return self._queue_size

    @property
    def closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._closed

    def subscriber_count(self, topic: str) -> int:
        """How many live subscriptions ``topic`` currently has.

        The SSE tests use this to prove that a client disconnect really released
        the subscription instead of leaving a leak behind.
        """
        return len(self._subscribers.get(topic, ()))

    def topics(self) -> List[str]:
        """Every topic that currently has at least one subscriber, sorted."""
        return sorted(topic for topic, bucket in self._subscribers.items() if bucket)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<EventBus queue_size={self._queue_size} "
            f"topics={self.topics()} closed={self._closed}>"
        )

    # ------------------------------------------------------------------ #
    # subscribe / publish
    # ------------------------------------------------------------------ #
    def subscribe(self, topic: str) -> Subscription:
        """Create and register a subscription on ``topic``.

        The subscription is registered **before** it is returned, so an event
        published immediately afterwards is already buffered for it — which is
        what lets the SSE handler subscribe first and replay second without
        racing the live feed.
        """
        if self._closed:
            raise RuntimeError(
                "EventBus 已关闭，不能再订阅（应用关闭后不得新建 SSE 流）。"
            )
        subscription = Subscription(self, topic, maxsize=self._queue_size)
        self._subscribers.setdefault(topic, []).append(subscription)
        return subscription

    async def publish(self, topic: str, event: Dict[str, Any]) -> int:
        """Deliver ``event`` to every live subscription on ``topic``.

        Returns the number of subscriptions the event was buffered for.  An
        unknown topic (or a closed bus) is not an error: publishing to a topic
        nobody listens to is the normal state of a dashboard feed.
        """
        if self._closed:
            return 0
        bucket = self._subscribers.get(topic)
        if not bucket:
            return 0
        delivered = 0
        # Iterate a copy: a subscription that closes while we fan out must not
        # disturb the others (and must not invalidate the iteration).
        for subscription in list(bucket):
            if subscription._offer(event):
                delivered += 1
        return delivered

    def _forget(self, subscription: Subscription) -> None:
        """Remove ``subscription`` from its topic bucket (called by close())."""
        bucket = self._subscribers.get(subscription.topic)
        if not bucket:
            return
        try:
            bucket.remove(subscription)
        except ValueError:  # pragma: no cover - already removed
            return
        if not bucket:
            self._subscribers.pop(subscription.topic, None)

    # ------------------------------------------------------------------ #
    # shutdown
    # ------------------------------------------------------------------ #
    async def close(self) -> None:
        """Close every subscription and refuse new ones.  **Idempotent.**

        Called from the application lifespan's shutdown half, so an open SSE
        stream ends instead of pinning the process during a reload.
        """
        if self._closed:
            return
        self._closed = True
        pending: List[Subscription] = [
            subscription
            for bucket in self._subscribers.values()
            for subscription in bucket
        ]
        self._subscribers.clear()
        for subscription in pending:
            await subscription.close()
