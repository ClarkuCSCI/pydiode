import unittest
from unittest.mock import patch

from pydiode.gui.common import ProcessPipeline
from pydiode.gui.send import bitrate_str_to_int


class TestGUI(unittest.TestCase):

    def setUp(self):
        self.pipeline = ProcessPipeline()

    @patch.object(ProcessPipeline, "_returncodes")
    def test_stuck_running(self, mock_returncodes):
        # Stuck pipelines
        mock_returncodes.return_value = [None, 0]
        self.assertTrue(self.pipeline.stuck_running())
        mock_returncodes.return_value = [None, None, 0]
        self.assertTrue(self.pipeline.stuck_running())
        mock_returncodes.return_value = [None, 0, None]
        self.assertTrue(self.pipeline.stuck_running())

        # Simple non-stuck pipelines
        mock_returncodes.return_value = [0]
        self.assertFalse(self.pipeline.stuck_running())
        mock_returncodes.return_value = [None]
        self.assertFalse(self.pipeline.stuck_running())

        # Complex non-stuck pipelines
        mock_returncodes.return_value = [0, 0]
        self.assertFalse(self.pipeline.stuck_running())
        mock_returncodes.return_value = [0, None]
        self.assertFalse(self.pipeline.stuck_running())
        mock_returncodes.return_value = [0, None, None]
        self.assertFalse(self.pipeline.stuck_running())
        mock_returncodes.return_value = [0, 0, None]
        self.assertFalse(self.pipeline.stuck_running())
        mock_returncodes.return_value = [None, None]
        self.assertFalse(self.pipeline.stuck_running())

    def test_bitrate_str_to_int(self):
        self.assertEqual(bitrate_str_to_int("100 Mbit/s"), 100000000)
        self.assertEqual(bitrate_str_to_int("250 Mbit/s"), 250000000)
        self.assertEqual(bitrate_str_to_int("500 Mbit/s"), 500000000)
        self.assertEqual(bitrate_str_to_int("750 Mbit/s"), 750000000)
        self.assertEqual(bitrate_str_to_int("1 Gbit/s"), 1000000000)
