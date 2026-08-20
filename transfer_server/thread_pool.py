import asyncio
import logging

logger = logging.getLogger(__name__)

class AsyncWorkerPool:
    def __init__(self, max_workers: int, max_queue_size: int):
        self.max_workers = max_workers
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.workers = []
        self._running = False

    async def start(self):
        self._running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self.workers.append(worker)
        logger.info(f"Started pool with {self.max_workers} workers.")

    async def stop(self):
        self._running = False
        for _ in range(self.max_workers):
            await self.queue.put(None) # Sentinel to stop workers
        await asyncio.gather(*self.workers)
        logger.info("Pool stopped.")

    async def submit(self, coro):
        """Submit a coroutine. Returns True if accepted, False if queue is full."""
        try:
            self.queue.put_nowait(coro)
            return True
        except asyncio.QueueFull:
            return False

    async def _worker_loop(self, worker_id):
        while self._running:
            coro = await self.queue.get()
            if coro is None:
                self.queue.task_done()
                break
            
            try:
                await coro
            except Exception as e:
                logger.error(f"Worker {worker_id} caught exception: {e}")
            finally:
                self.queue.task_done()
