# File Sharing Platform Architecture

This document provides a high-level overview of the event-driven, resilient file sharing architecture, its key components, the workflow for file transfers, and potential questions that could be asked about the design.

## 1. Key Architectural Points

- **Event-Driven & Asynchronous:** The backend uses an asynchronous TCP server (`TransferServer` using `asyncio`) decoupled from the standard HTTP synchronous processing. This supports long-running connections (GB+ files) efficiently without blocking web workers.
- **Microservice-like Separation:** There's a clear separation between the "Control Plane" (Django HTTP server for UI, policies, metadata) and the "Data Plane" (Async TCP server for raw file transfers).
- **Django Bridge (IPC):** To communicate between the async Transfer Server and the synchronous Django environment, a `DjangoBridge` utilizes `sync_to_async` wrappers. This enables the Data Plane to securely authenticate users, check permissions, and update file states in the PostgreSQL database.
- **Resiliency & Fault Tolerance:** The system uses chunked transfers and tracks `bytes_transferred` in the database (`FileTransfer` state). If the server abruptly terminates or fails, the database maintains the last known state (`DISCONNECTED` or `TRANSFERRING`), allowing the client to resume the upload/download from the exact byte offset using HTTP Range requests or a custom chunking protocol.
- **Load Balancing Ready:** By tracking `ServerNode` status and current loads, the platform is structured to support multiple `TransferServer` instances. The UI visualizes which nodes are active.
- **Policy Engine:** A dedicated `PolicyEngine` enforces read/write permissions based on file visibility (`PRIVATE`, `PUBLIC`) and ownership.

## 2. Transfer Workflow (Upload)

1. **Initialization (HTTP/REST):** 
   - The user triggers an upload from the frontend.
   - The UI hits an API endpoint (`api_upload_init`) via the Control Plane to declare the intent (filename, size, visibility).
   - The Control Plane creates a `File` record and a `FileTransfer` state (`TRANSFERRING`), returning a unique `file_id` and expected offset.
2. **Chunking & Streaming (HTTP or TCP):**
   - The frontend reads the file in chunks and sends them either to the HTTP chunk endpoint (`api_upload_chunk`) or streams directly via the TCP `TransferServer`.
   - The `TransferServer` writes chunks to the designated path.
3. **State Updates:**
   - Periodically, the `TransferServer` or HTTP endpoint updates the `bytes_transferred` in the database via the `DjangoBridge`.
4. **Finalization:**
   - Once all bytes are sent, the client triggers `api_upload_finalize`.
   - The server verifies the file completeness, calculates a SHA-256 checksum, and marks the state as `COMPLETE`.
   - The UI reflects the finished transfer in the Masonry or File list views.

## 3. Potential Questions & Interview/Discussion Points

- **Q: How do you handle sudden server failures mid-transfer?**
  *A:* The client sends data in chunks. The server logs the transfer state and `bytes_transferred` in the DB. On restart, the client queries the init endpoint which detects the existing incomplete `FileTransfer` and tells the client to resume from the last known offset.
  
- **Q: Why use a separate Async TCP Transfer Server alongside Django?**
  *A:* Django's standard WSGI workers are synchronous and not optimized for long-lived, massive file streaming connections. A dedicated async event loop (`asyncio`) can handle thousands of concurrent file streams with minimal overhead, while Django focuses on what it does best: routing, templates, and ORM.

- **Q: How does the system ensure data integrity for large files?**
  *A:* Upon completion, the server calculates a SHA-256 checksum of the assembled file and stores it. The client can verify this against their local file hash.

- **Q: How are file sharing policies enforced?**
  *A:* All file access passes through a `PolicyEngine` (e.g., in `dashboard_view` and `check_download_permission`). It evaluates the user's identity against the file's ownership and visibility flags before returning a file or granting a download ticket.

- **Q: Can we scale the Transfer Servers horizontally?**
  *A:* Yes. The `ServerNode` table tracks multiple transfer nodes. With a load balancer distributing traffic, clients can upload/download from any node. Storage must be shared (e.g., NAS, S3, or NFS) so all nodes can read/write the same `UPLOADS_DIR`.
