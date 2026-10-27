import asyncio
import json
import logging
from collections.abc import AsyncIterator

import aiohttp

from .models import Candle

LOGGER = logging.getLogger(__name__)


class MarketStream:
    def __init__(self, provider: str, symbol: str):
        self.provider = provider
        self.symbol = symbol.upper()

    async def candles(self) -> AsyncIterator[Candle]:
        delay = 1
        while True:
            try:
                if self.provider == "bitget":
                    async for candle in self._bitget():
                        delay = 1
                        yield candle
                else:
                    async for candle in self._binance():
                        delay = 1
                        yield candle
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
                LOGGER.warning("WebSocket %s desconectado: %s", self.provider, exc)
                if self.provider == "bitget":
                    LOGGER.warning("Bitget no disponible; cambiando al WebSocket público de Binance")
                    self.provider = "binance"
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    async def hourly_history(self, start_ms: int) -> list[Candle]:
        """Load closed 1h candles from start_ms through the latest closed hour."""
        try:
            if self.provider == "bitget":
                return await self._bitget_hourly_history(start_ms)
            return await self._binance_hourly_history(start_ms)
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            if self.provider != "bitget":
                raise
            LOGGER.warning("No se pudo cargar histórico de Bitget: %s. Usando Binance.", exc)
            self.provider = "binance"
            return await self._binance_hourly_history(start_ms)

    async def _bitget_hourly_history(self, start_ms: int) -> list[Candle]:
        url = "https://api.bitget.com/api/v2/spot/market/candles"
        candles: list[Candle] = []
        cursor = start_ms
        async with aiohttp.ClientSession() as session:
            while cursor < _now_ms():
                params = {"symbol": self.symbol, "granularity": "1H", "startTime": str(cursor), "limit": "1000"}
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    payload = await response.json()
                rows = payload.get("data", [])
                if not rows:
                    break
                page = [_candle_from_row(row) for row in rows]
                candles.extend(page)
                newest = max(item.timestamp for item in page)
                if newest <= cursor:
                    break
                cursor = newest + 3_600_000
        return _closed(candles)

    async def _binance_hourly_history(self, start_ms: int) -> list[Candle]:
        url = "https://api.binance.com/api/v3/klines"
        candles: list[Candle] = []
        cursor = start_ms
        async with aiohttp.ClientSession() as session:
            while cursor < _now_ms():
                params = {"symbol": self.symbol, "interval": "1h", "startTime": cursor, "limit": 1000}
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    rows = await response.json()
                if not rows:
                    break
                page = [_candle_from_row(row) for row in rows]
                candles.extend(page)
                newest = max(item.timestamp for item in page)
                if newest <= cursor:
                    break
                cursor = newest + 3_600_000
        return _closed(candles)

    async def _bitget(self) -> AsyncIterator[Candle]:
        url = "wss://ws.bitget.com/v2/ws/public"
        request = {"op": "subscribe", "args": [{"instType": "SPOT", "channel": "candle1m", "instId": self.symbol}]}
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url, heartbeat=20) as ws:
                await ws.send_json(request)
                async for message in ws:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        if message.data == "ping":
                            await ws.send_str("pong")
                            continue
                        if message.data == "pong":
                            continue
                        payload = json.loads(message.data)
                        for row in payload.get("data", []):
                            yield Candle(int(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]))
                    elif message.type in {aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED}:
                        raise aiohttp.ClientError("Bitget cerró el WebSocket")

    async def _binance(self) -> AsyncIterator[Candle]:
        url = f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@kline_1m"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url, heartbeat=20) as ws:
                async for message in ws:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(message.data)["k"]
                        if data["x"]:  # solo vela cerrada
                            yield Candle(int(data["t"]), float(data["o"]), float(data["h"]), float(data["l"]), float(data["c"]), float(data["v"]))
                    elif message.type in {aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED}:
                        raise aiohttp.ClientError("Binance cerró el WebSocket")


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


def _candle_from_row(row: list) -> Candle:
    return Candle(int(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]))


def _closed(candles: list[Candle]) -> list[Candle]:
    now = _now_ms()
    unique = {candle.timestamp: candle for candle in candles if candle.timestamp + 3_600_000 <= now}
    return [unique[timestamp] for timestamp in sorted(unique)]
