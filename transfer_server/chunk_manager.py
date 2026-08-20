class ChunkManager:
    def __init__(self, file_size):
        self.file_size = file_size
        self.received_intervals = [] # List of (start, end) tuples

    def add_chunk(self, start, end):
        """Adds a new received chunk and merges overlapping intervals."""
        if start >= end or start < 0 or end > self.file_size:
            raise ValueError(f"Invalid chunk range: {start}-{end}")

        self.received_intervals.append((start, end))
        self.received_intervals.sort()

        merged = []
        for interval in self.received_intervals:
            if not merged:
                merged.append(interval)
            else:
                prev_start, prev_end = merged[-1]
                curr_start, curr_end = interval
                if curr_start <= prev_end:
                    merged[-1] = (prev_start, max(prev_end, curr_end))
                else:
                    merged.append(interval)
        self.received_intervals = merged

    def get_missing_intervals(self):
        """Returns the gaps in received chunks."""
        missing = []
        current = 0
        for start, end in self.received_intervals:
            if current < start:
                missing.append((current, start))
            current = max(current, end)
        
        if current < self.file_size:
            missing.append((current, self.file_size))
            
        return missing

    def is_complete(self):
        return len(self.received_intervals) == 1 and self.received_intervals[0] == (0, self.file_size)

    def total_bytes_received(self):
        return sum(end - start for start, end in self.received_intervals)
