import unittest
import pandas as pd
from technical_analysis import calculate_indicators
from database import Database
from paper_trading import PaperTrader
from decision_engine import evaluate_setup

class CoreTests(unittest.TestCase):
    def candles(self,n=260):
        close=[100+i*.2 for i in range(n)]
        return pd.DataFrame({"open":close,"high":[x+1 for x in close],"low":[x-1 for x in close],"close":close,"volume":[1000+i for i in range(n)]})
    def test_indicators(self):
        x=calculate_indicators(self.candles())
        self.assertIsNotNone(x["ema200"]); self.assertGreater(x["atr"],0)
    def test_exposure_cap_and_recalculation(self):
        db=Database(":memory:"); trader=PaperTrader(db)
        self.assertTrue(trader.open_position("BTC-USDT",100,2))
        self.assertLessEqual(trader.exposure(),trader.equity()*0.10+1e-8)
        self.assertFalse(trader.open_position("ETH-USDT",100,2))
        # Mark-to-market equity and exposure use current prices, not entry prices.
        marked_equity=trader.equity({"BTC-USDT":120})
        self.assertGreater(marked_equity,trader.equity())
        self.assertGreater(trader.exposure({"BTC-USDT":120}),trader.exposure())
        db.close()
    def test_ai_unavailable_fails_closed(self):
        frames={"15m": {"price":100,"ema9":3,"ema21":2,"ema50":1,"rsi":55,"macd":2,"macd_signal":1,"atr":1,"volume":100,"volume_avg":50},
                "1h": {"price":100,"ema9":3,"ema21":2,"ema50":1,"rsi":55,"macd":2,"macd_signal":1,"atr":1,"volume":100,"volume_avg":50},
                "4h": {"price":100,"ema9":3,"ema21":2,"ema50":1,"rsi":55,"macd":2,"macd_signal":1,"atr":1,"volume":100,"volume_avg":50}}
        self.assertEqual(evaluate_setup(frames, "UNAVAILABLE", 0)["action"], "HOLD")

    def test_bad_data_rejected(self):
        with self.assertRaises(ValueError): calculate_indicators(pd.DataFrame({"close":[1,2]}))

if __name__=="__main__": unittest.main()
