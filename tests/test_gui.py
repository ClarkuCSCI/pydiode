import unittest

from pydiode.gui.common import stuck_running


class TestGUI(unittest.TestCase):
    def test_stuck_running(self):
        self.assertTrue(stuck_running([None, 0]))
        self.assertTrue(stuck_running([None, None, 0]))
        self.assertTrue(stuck_running([None, 0, None]))

        self.assertFalse(stuck_running([0]))
        self.assertFalse(stuck_running([None]))

        self.assertFalse(stuck_running([0, 0]))
        self.assertFalse(stuck_running([0, None]))
        self.assertFalse(stuck_running([0, None, None]))
        self.assertFalse(stuck_running([0, 0, None]))
        self.assertFalse(stuck_running([None, None]))
