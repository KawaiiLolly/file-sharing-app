import unittest
from transfer_server.chunk_manager import ChunkManager

class TestChunkManager(unittest.TestCase):
    def test_add_chunk_simple(self):
        cm = ChunkManager(100)
        cm.add_chunk(0, 10)
        self.assertEqual(cm.received_intervals, [(0, 10)])
        
    def test_add_chunk_overlap(self):
        cm = ChunkManager(100)
        cm.add_chunk(0, 10)
        cm.add_chunk(5, 15)
        self.assertEqual(cm.received_intervals, [(0, 15)])
        
    def test_get_missing_intervals(self):
        cm = ChunkManager(100)
        cm.add_chunk(0, 10)
        cm.add_chunk(20, 30)
        missing = cm.get_missing_intervals()
        self.assertEqual(missing, [(10, 20), (30, 100)])
        
    def test_is_complete(self):
        cm = ChunkManager(100)
        cm.add_chunk(0, 50)
        self.assertFalse(cm.is_complete())
        cm.add_chunk(50, 100)
        self.assertTrue(cm.is_complete())

if __name__ == '__main__':
    unittest.main()
