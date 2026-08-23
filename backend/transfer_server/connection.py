import asyncio
import json
import logging
import os
from enum import Enum
from .chunk_manager import ChunkManager
from .checksum import ChecksumVerifier

logger = logging.getLogger(__name__)

class TransferState(Enum):
    HANDSHAKE = 1
    AUTH_CHECK = 2
    TRANSFERRING = 3
    VERIFYING = 4
    COMPLETE = 5
    DISCONNECTED = 6
    ERROR = 7

class TransferSession:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, bridge_client=None):
        self.reader = reader
        self.writer = writer
        self.bridge = bridge_client # to talk to Django policies
        
        self.state = TransferState.HANDSHAKE
        self.action = None
        self.user = None
        self.file_name = None
        self.file_size = 0
        self.stored_name = None
        self.file_id = None
        self.visibility = None
        self.chunk_manager = None
        self.checksum_verifier = ChecksumVerifier()
        self.file_handle = None
        
        self.UPLOADS_DIR = "p:\\file-sharing\\storage"

    def get_full_path(self):
        # Prevent path traversal
        safe_name = os.path.basename(self.stored_name)
        return os.path.join(self.UPLOADS_DIR, safe_name)

    async def send_json(self, data: dict):
        msg = json.dumps(data).encode('utf-8') + b'\n'
        self.writer.write(msg)
        await self.writer.drain()

    async def receive_json(self) -> dict:
        line = await self.reader.readline()
        if not line:
            return None
        return json.loads(line.decode('utf-8').strip())

    async def handle(self):
        try:
            await self._run_state_machine()
        except asyncio.IncompleteReadError:
            logger.warning("Client disconnected abruptly.")
            self.state = TransferState.DISCONNECTED
        except Exception as e:
            logger.error(f"Transfer error: {e}")
            self.state = TransferState.ERROR
            await self.send_json({"status": "error", "message": str(e)})
        finally:
            if self.file_handle:
                self.file_handle.close()
            self.writer.close()
            await self.writer.wait_closed()
            if self.bridge and self.file_id and self.user:
                await self.bridge.update_transfer_state(self.file_id, self.user, self.state.name, 
                    self.chunk_manager.total_bytes_received() if self.chunk_manager else 0)
                if self.state == TransferState.COMPLETE and self.action == 'upload':
                    final_hash = getattr(self, 'final_checksum', self.checksum_verifier.get_hexdigest())
                    await self.bridge.finalize_upload(self.file_id, final_hash)

    async def _run_state_machine(self):
        while self.state not in (TransferState.COMPLETE, TransferState.DISCONNECTED, TransferState.ERROR):
            if self.state == TransferState.HANDSHAKE:
                await self._do_handshake()
            elif self.state == TransferState.AUTH_CHECK:
                await self._do_auth_check()
            elif self.state == TransferState.TRANSFERRING:
                if self.action == 'upload':
                    await self._do_upload_transfer()
                else:
                    await self._do_download_transfer()
            elif self.state == TransferState.VERIFYING:
                await self._do_verification()

    async def _do_handshake(self):
        req = await self.receive_json()
        if not req or req.get("action") not in ["upload", "download"]:
            raise ValueError("Expected upload or download action")
        
        self.action = req.get("action")
        self.user = req.get("username")
        self.file_name = os.path.basename(req.get("file_name"))
        
        if self.action == "upload":
            self.file_size = req.get("file_size")
            self.visibility = req.get("visibility", "PRIVATE")
            if not self.user or not self.file_name or self.file_size is None:
                raise ValueError("Missing metadata")
        else:
            if not self.user or not self.file_name:
                raise ValueError("Missing metadata")
                
        self.state = TransferState.AUTH_CHECK

    async def _do_auth_check(self):
        if not self.bridge:
            raise RuntimeError("Django Bridge not configured")
            
        if self.action == "upload":
            resp = await self.bridge.initialize_upload(self.user, self.file_name, self.file_size, self.visibility)
            if "error" in resp:
                await self.send_json({"status": "error", "message": resp["error"]})
                self.state = TransferState.ERROR
                return
                
            self.stored_name = resp["stored_name"]
            self.file_id = resp["file_id"]
            self.chunk_manager = ChunkManager(self.file_size)
            
            manifest_path = self.get_full_path() + '.manifest'
            self.chunk_manager.load_from_manifest(manifest_path)
            
            missing = self.chunk_manager.get_missing_intervals()
            await self.send_json({"status": "ready", "missing_intervals": missing})
            
            file_path = self.get_full_path()
            if os.path.exists(file_path):
                self.file_handle = open(file_path, "r+b")
            else:
                self.file_handle = open(file_path, "w+b")
            self.state = TransferState.TRANSFERRING
            
        elif self.action == "download":
            resp = await self.bridge.check_download_permission(self.user, self.file_name)
            if not resp.get("allowed"):
                await self.send_json({"status": "error", "message": resp.get("error", "Permission denied")})
                self.state = TransferState.ERROR
                return
                
            self.stored_name = resp["stored_name"]
            self.file_id = resp["file_id"]
            self.file_size = resp["file_size"]
            self.expected_checksum = resp["checksum"]
            
            if not os.path.exists(self.get_full_path()):
                await self.send_json({"status": "error", "message": "File missing on server storage"})
                self.state = TransferState.ERROR
                return
                
            await self.send_json({"status": "ready", "file_size": self.file_size, "expected_checksum": self.expected_checksum})
            self.file_handle = open(self.get_full_path(), "rb")
            self.state = TransferState.TRANSFERRING

    async def _do_upload_transfer(self):
        header = await self.receive_json()
        if not header:
            self.state = TransferState.DISCONNECTED
            return
            
        if header.get("action") == "verify":
            self.expected_checksum = header.get("checksum")
            self.state = TransferState.VERIFYING
            return

        start = header.get("start")
        length = header.get("length")
        
        if start is None or length is None:
            raise ValueError("Missing chunk metadata")

        data = await self.reader.readexactly(length)
        
        self.file_handle.seek(start)
        self.file_handle.write(data)
        
        self.chunk_manager.add_chunk(start, start + length)
        self.checksum_verifier.update(data)
        
        manifest_path = self.get_full_path() + '.manifest'
        self.chunk_manager.save_to_manifest(manifest_path)
        
        await self.send_json({"status": "ack", "start": start, "length": length})
        
        if self.bridge:
            await self.bridge.update_transfer_state(self.file_id, self.user, "TRANSFERRING", 
                self.chunk_manager.total_bytes_received())

    async def _do_download_transfer(self):
        req = await self.receive_json()
        if not req or req.get("action") != "request_intervals":
            raise ValueError("Expected request_intervals")
            
        intervals = req.get("intervals", [])
        
        for start, end in intervals:
            if start < 0 or end > self.file_size or start >= end:
                raise ValueError("Invalid interval")
                
            self.file_handle.seek(start)
            bytes_to_read = end - start
            while bytes_to_read > 0:
                chunk_size = min(4096 * 1024, bytes_to_read)
                chunk = self.file_handle.read(chunk_size)
                if not chunk:
                    break
                    
                header = {
                    "start": start + (end - start) - bytes_to_read,
                    "length": len(chunk)
                }
                
                msg = json.dumps(header).encode('utf-8') + b'\n'
                self.writer.write(msg)
                self.writer.write(chunk)
                await self.writer.drain()
                
                ack = await self.receive_json()
                if not ack or ack.get("status") != "ack":
                    raise ValueError("Failed to receive ack from client")
                    
                bytes_to_read -= len(chunk)
                
        # Wait for verify success
        verify = await self.receive_json()
        if verify and verify.get("action") == "verify" and verify.get("status") == "success":
            self.state = TransferState.COMPLETE
        else:
            self.state = TransferState.ERROR

    async def _do_verification(self):
        if self.chunk_manager.is_complete():
            import hashlib
            hasher = hashlib.sha256()
            self.file_handle.seek(0)
            for chunk in iter(lambda: self.file_handle.read(4096 * 1024), b""):
                hasher.update(chunk)
            actual_checksum = hasher.hexdigest()
            self.final_checksum = actual_checksum
            
            if actual_checksum == self.expected_checksum:
                await self.send_json({"status": "success", "message": "File completely received and verified."})
                self.state = TransferState.COMPLETE
                
                manifest_path = self.get_full_path() + '.manifest'
                if os.path.exists(manifest_path):
                    os.remove(manifest_path)
            else:
                await self.send_json({"status": "error", "message": "Checksum mismatch."})
                self.state = TransferState.ERROR
        else:
            await self.send_json({"status": "error", "message": "File incomplete."})
            self.state = TransferState.ERROR
