async def get_market_snapshot(self, symbol):

    symbol = str(symbol).upper()

    if symbol not in SYMBOLS:
        logger.warning(
            "SNAPSHOT REJECTED %s: Symbol not configured",
            symbol
        )
        return None

    try:

        ticker, candles = await asyncio.gather(
            self.get_ticker(symbol),
            self.get_klines(symbol)
        )

        if ticker is None:
            logger.warning(
                "SNAPSHOT REJECTED %s: Invalid ticker",
                symbol
            )
            return None

        if ticker["quote_volume"] < MIN_QUOTE_VOLUME:
            logger.warning(
                "SNAPSHOT REJECTED %s: Low volume %.2f < %.2f",
                symbol,
                ticker["quote_volume"],
                MIN_QUOTE_VOLUME
            )
            return None

        if candles is None or len(candles) < 61:
            logger.warning(
                "SNAPSHOT REJECTED %s: Insufficient candles (%s)",
                symbol,
                0 if candles is None else len(candles)
            )
            return None

        logger.info(
            "SNAPSHOT OK %s | Price: %.8f | Candles: %s",
            symbol,
            ticker["price"],
            len(candles)
        )

        return {
            "symbol": symbol,
            "ticker": ticker,
            "candles": candles,
            "klines": candles
        }

    except Exception:

        logger.exception(
            "MARKET SNAPSHOT ERROR: %s",
            symbol
        )

        return None
