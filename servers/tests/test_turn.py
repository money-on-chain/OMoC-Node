import unittest

from oracle.src.oracle_turn import OracleTurn


class TestTurnFallback(unittest.TestCase):
    def test_multiplier0_base(self):
        self.assertEqual(OracleTurn.applyMultiplier([1]), [1])

    def test_multiplier0_base2(self):
        self.assertEqual(OracleTurn.applyMultiplier([1, 2, 3, 4]), [1, 2, 3, 4])

    def test_multiplier1_base(self):
        self.assertEqual(OracleTurn.applyMultiplier([1], 1), [1, 1])

    def test_multiplier1_base2(self):
        self.assertEqual(OracleTurn.applyMultiplier([1, 2, 3, 4], 1),
                         [1, 1, 2, 2, 3, 3, 4, 4])


if __name__ == '__main__':
    unittest.main()
