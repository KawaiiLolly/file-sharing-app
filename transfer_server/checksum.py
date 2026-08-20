import hashlib

class ChecksumVerifier:
    def __init__(self, algorithm='sha256'):
        if algorithm not in hashlib.algorithms_available:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        self.algorithm = algorithm
        self.hasher = hashlib.new(algorithm)

    def update(self, chunk: bytes):
        self.hasher.update(chunk)

    def get_hexdigest(self) -> str:
        return self.hasher.hexdigest()

    @staticmethod
    def verify_file(filepath: str, expected_hash: str, algorithm='sha256') -> bool:
        hasher = hashlib.new(algorithm)
        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096 * 1024), b""): # 4MB chunks
                    hasher.update(chunk)
            return hasher.hexdigest() == expected_hash
        except FileNotFoundError:
            return False
