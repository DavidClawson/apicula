import os
import unittest

from apycula import pindef


class GW1N2QN48Test(unittest.TestCase):
    def test_physical_pin_numbers_are_complete(self):
        self.assertEqual(len(pindef.GW1N_2_QN48_PINOUT), 48)
        self.assertEqual(set(pindef.GW1N_2_QN48_PINOUT),
                         {str(pin) for pin in range(1, 49)})

    @unittest.skipUnless(os.getenv("GOWINHOME"), "requires Gowin die metadata")
    def test_qn48_bondout_is_not_qfn48xf(self):
        pins = pindef.get_pin_locs("GW1N-1P5C", "QN48", pindef.VeryTrue)
        self.assertEqual(
            {pin: pins[pin][0] for pin in ("8", "9", "10", "11")},
            {"8": "IOT9B", "9": "IOT9A", "10": "IOT7B", "11": "IOT7A"})
        self.assertEqual(
            {pin: pins[pin][0] for pin in ("28", "29", "34", "35")},
            {"28": "IOB5B", "29": "IOB5A", "34": "IOB18A", "35": "IOB18B"})
