
import unittest

import pandas as pd

from technical_analysis import calculate_indicators
from database import Database
from paper_trading import PaperTrader
from decision_engine import evaluate_setup


class CoreTests(unittest.TestCase):

    def setUp(self):
        self.db = Database(":memory:")
        self.trader = PaperTrader(self.db)

    def tearDown(self):
        self.db.close()

    @staticmethod
    def candles(n=260):
        close = [100 + i * 0.2 for i in range(n)]

        return pd.DataFrame({
            "open": close,
            "high": [x + 1 for x in close],
            "low": [x - 1 for x in close],
            "close": close,
            "volume": [1000 + i for i in range(n)],
        })

    @staticmethod
    def valid_frames():
        frame = {
            "price": 100,
            "ema9": 103,
            "ema21": 102,
            "ema50": 101,
            "rsi": 55,
            "macd": 2,
            "macd_signal": 1,
            "atr": 1,
            "volume": 100,
            "volume_avg": 50,
        }

        return {
            "15m": dict(frame),
            "1h": dict(frame),
            "4h": dict(frame),
        }

    def test_indicators(self):
        result = calculate_indicators(self.candles())

        self.assertIsNotNone(result["ema200"])
        self.assertGreater(result["atr"], 0)
        self.assertEqual(result["candles"], 260)

    def test_insufficient_candles_rejected(self):
        with self.assertRaises(ValueError):
            calculate_indicators(self.candles(20))

    def test_bad_data_rejected(self):
        invalid = pd.DataFrame({
            "close": [1, 2],
        })

        with self.assertRaises(ValueError):
            calculate_indicators(invalid)

    def test_ai_unavailable_fails_closed(self):
        result = evaluate_setup(
            self.valid_frames(),
            "UNAVAILABLE",
            0,
        )

        self.assertEqual(result["action"], "HOLD")

    def test_invalid_ai_agreement_fails_closed(self):
        result = evaluate_setup(
            self.valid_frames(),
            "BUY",
            float("nan"),
        )

        self.assertEqual(result["action"], "HOLD")

    def test_exposure_cap_and_recalculation(self):
        opened = self.trader.open_position(
            "BTC-USDT",
            100,
            2,
        )

        self.assertTrue(opened)

        equity_before = self.trader.equity()
        exposure_before = self.trader.exposure()

        self.assertLessEqual(
            exposure_before,
            equity_before * 0.10 + 1e-8,
        )

        # The same symbol must not be opened twice.
        self.assertFalse(
            self.trader.open_position(
                "BTC-USDT",
                100,
                2,
            )
        )

        # A higher market price changes mark-to-market values.
        marked_equity = self.trader.equity({
            "BTC-USDT": 120,
        })

        marked_exposure = self.trader.exposure({
            "BTC-USDT": 120,
        })

        self.assertGreater(marked_equity, equity_before)
        self.assertGreater(marked_exposure, exposure_before)

        self.assertLessEqual(
            self.trader.total_open_risk(),
            self.trader.risk_budget({
                "BTC-USDT": 120,
            }) + 1e-8,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
