import asyncio
import logging
from .connection import TransferSession
from .thread_pool import AsyncWorkerPool

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class TransferServer:
    def __init__(self, host='0.0.0.0', port=8888, max_workers=100, max_queue=200, bridge_client=None):
        self.host = host
        self.port = port
        self.bridge_client = bridge_client
        self.pool = AsyncWorkerPool(max_workers=max_workers, max_queue_size=max_queue)
        self.server = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        logger.info(f"New connection from {addr}")
        
        session = TransferSession(reader, writer, self.bridge_client)
        
        # Submit session to the worker pool
        accepted = await self.pool.submit(session.handle())
        if not accepted:
            logger.warning(f"Server busy. Rejecting connection from {addr}")
            writer.write(b'{"error": "SERVER_BUSY"}\n')
            await writer.drain()
            writer.close()
            await writer.wait_closed()

    async def start(self):
        await self.pool.start()
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        addr = self.server.sockets[0].getsockname()
        logger.info(f"Serving on {addr}")

        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await self.pool.stop()

if __name__ == "__main__":
    server = TransferServer()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server shutting down.")
