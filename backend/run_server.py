import sys
import os

# Add parent dir to path so we can import apps easily
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from transfer_server.server import TransferServer
from bridge.ipc import DjangoBridge
import logging

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    bridge = DjangoBridge()
    server = TransferServer(bridge_client=bridge)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logging.info("Server shutting down.")
