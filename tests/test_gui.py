import unittest
from unittest.mock import patch

from pydiode.gui.common import ProcessPipeline


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
