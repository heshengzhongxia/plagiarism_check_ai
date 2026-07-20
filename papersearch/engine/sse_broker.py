import queue
import threading

class SSEBroker:
    """线程安全的事件队列"""

    def __init__(self):
        self._queues: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()

    def subscribe(self, task_id: str) -> queue.Queue:
        with self._lock:
            q = queue.Queue()
            self._queues[task_id] = q
            return q

    def publish(self, task_id: str, event: str, data: dict) -> None:
        with self._lock:
            q = self._queues.get(task_id)
        if q:
            q.put({"event": event, "data": data})

    def unsubscribe(self, task_id: str) -> None:
        with self._lock:
            self._queues.pop(task_id, None)


# 全局单例
sse_broker = SSEBroker()
