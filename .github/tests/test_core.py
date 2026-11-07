    def test_indicators(self):
        x = calculate_indicators(self.candles())
        self.assertIsNotNone(x["ema200"])
        self.assertEqual(x["candles"], 240)

    def test_invalid_candles_rejected(self):
        with self.assertRaises(ValueError): 
            calculate_indicators(self.candles(20))

    def test_decision_fails_closed(self):
        self.assertEqual(
            evaluate_setup({"score": 85}, "UNAVAILABLE", 0)["action"], 
            "HOLD"
        )
        self.assertEqual(
            evaluate_setup({"score": 85, "zscore": 0.5}, "BUY", .9)["action"], 
            "PAPER_BUY"
        )

    def test_paper_position(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            db = Database(path)
            trader = PaperTrader(db)
            self.assertTrue(trader.open_position("BTC-USDT", 100, 2))
            self.assertFalse(trader.open_position("BTC-USDT", 100, 2))
            self.assertEqual(len(db.positions()), 1)
            self.assertLess(db.account()["balance"], 200)
            db.close()
        finally: 
            os.unlink(path)

    def test_backtest(self):
        result = run_backtest(self.candles())
        self.assertIn("max_drawdown_pct", result)

if __name__ == "__main__":
    unittest.main()
