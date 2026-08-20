import asyncio
import json
import os
import hashlib

async def upload_file(host, port, username, file_path):
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    reader, writer = await asyncio.open_connection(host, port)
    
    # 1. Handshake
    handshake = {
        "action": "upload",
        "username": username,
        "file_name": file_name,
        "file_size": file_size,
        "visibility": "PUBLIC_VIEW" # Hardcoding for testing purposes
    }
    writer.write(json.dumps(handshake).encode('utf-8') + b'\n')
    await writer.drain()
    
    # 2. Receive auth check & ready
    response_line = await reader.readline()
    response = json.loads(response_line.decode('utf-8').strip())
    
    if response.get("status") != "ready":
        print(f"Error: {response}")
        return
        
    missing_intervals = response.get("missing_intervals", [])
    print(f"Server ready. Missing intervals: {missing_intervals}")
    
    # 3. Transfer chunks
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for start, end in missing_intervals:
            f.seek(start)
            bytes_to_read = end - start
            while bytes_to_read > 0:
                chunk_size = min(4096 * 1024, bytes_to_read) # 4MB chunks
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                hasher.update(chunk)
                
                header = {
                    "start": start + (end - start) - bytes_to_read,
                    "length": len(chunk)
                }
                writer.write(json.dumps(header).encode('utf-8') + b'\n')
                writer.write(chunk)
                await writer.drain()
                
                # Wait for ack
                ack_line = await reader.readline()
                ack = json.loads(ack_line.decode('utf-8').strip())
                if ack.get("status") != "ack":
                    print(f"Transfer failed: {ack}")
                    return
                
                bytes_to_read -= len(chunk)
                
    # 4. Verification
    verify_header = {
        "action": "verify",
        "checksum": hasher.hexdigest()
    }
    writer.write(json.dumps(verify_header).encode('utf-8') + b'\n')
    await writer.drain()
    
    final_response_line = await reader.readline()
    final_response = json.loads(final_response_line.decode('utf-8').strip())
    print(f"Transfer complete: {final_response}")
    
    writer.close()
    await writer.wait_closed()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python test_client.py <username> <filepath>")
        sys.exit(1)
    
    username = sys.argv[1]
    filepath = sys.argv[2]
    
    asyncio.run(upload_file('127.0.0.1', 8888, username, filepath))
