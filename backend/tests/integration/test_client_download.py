import asyncio
import json
import os
import hashlib
import sys

async def download_file(host, port, username, file_name, save_path):
    reader, writer = await asyncio.open_connection(host, port)
    
    # 1. Handshake
    handshake = {
        "action": "download",
        "username": username,
        "file_name": file_name
    }
    writer.write(json.dumps(handshake).encode('utf-8') + b'\n')
    await writer.drain()
    
    # 2. Receive auth check & ready
    response_line = await reader.readline()
    if not response_line:
        print("Error: Server closed connection abruptly.")
        return
        
    response = json.loads(response_line.decode('utf-8').strip())
    
    if response.get("status") != "ready":
        print(f"Error: {response}")
        return
        
    file_size = response.get("file_size")
    expected_checksum = response.get("expected_checksum")
    print(f"Server ready. File size: {file_size} bytes. Expected Checksum: {expected_checksum}")
    
    # 3. Resumability Check
    missing_intervals = []
    if os.path.exists(save_path):
        local_size = os.path.getsize(save_path)
        if local_size < file_size:
            missing_intervals = [[local_size, file_size]]
        elif local_size > file_size:
            print("Local file is larger than server file. Truncating or overwriting might be needed. For now, starting over.")
            missing_intervals = [[0, file_size]]
            os.remove(save_path) # Restart
    else:
        missing_intervals = [[0, file_size]]
        
    if not missing_intervals:
        print("File is already fully downloaded locally!")
        # We can just verify it
    else:
        print(f"Requesting intervals: {missing_intervals}")
        req = {
            "action": "request_intervals",
            "intervals": missing_intervals
        }
        writer.write(json.dumps(req).encode('utf-8') + b'\n')
        await writer.drain()
        
        with open(save_path, 'ab' if os.path.exists(save_path) else 'wb') as f:
            for start, end in missing_intervals:
                bytes_to_receive = end - start
                
                while bytes_to_receive > 0:
                    header_line = await reader.readline()
                    if not header_line:
                        print("Connection lost during transfer")
                        return
                    header = json.loads(header_line.decode('utf-8').strip())
                    
                    chunk_start = header["start"]
                    chunk_length = header["length"]
                    
                    # Read exact chunk bytes
                    data = await reader.readexactly(chunk_length)
                    
                    f.seek(chunk_start)
                    f.write(data)
                    
                    # Send ack
                    ack = {"status": "ack"}
                    writer.write(json.dumps(ack).encode('utf-8') + b'\n')
                    await writer.drain()
                    
                    bytes_to_receive -= chunk_length

    # 4. Final verification
    print("Verifying file checksum...")
    hasher = hashlib.sha256()
    with open(save_path, 'rb') as f:
        while chunk := f.read(4096 * 1024):
            hasher.update(chunk)
            
    local_checksum = hasher.hexdigest()
    if local_checksum == expected_checksum:
        print("Checksum matched! Download successful.")
        verify = {
            "action": "verify",
            "status": "success"
        }
        writer.write(json.dumps(verify).encode('utf-8') + b'\n')
        await writer.drain()
    else:
        print(f"Checksum mismatch! Expected {expected_checksum}, got {local_checksum}")
        verify = {
            "action": "verify",
            "status": "error"
        }
        writer.write(json.dumps(verify).encode('utf-8') + b'\n')
        await writer.drain()
        
    writer.close()
    await writer.wait_closed()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python test_client_download.py <username> <file_name> <save_path>")
        sys.exit(1)
    
    username = sys.argv[1]
    filename = sys.argv[2]
    savepath = sys.argv[3]
    
    asyncio.run(download_file('127.0.0.1', 8888, username, filename, savepath))
