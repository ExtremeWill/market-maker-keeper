# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2018 reverendus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import logging
import threading
import time
from decimal import *
from typing import Optional
from operator import neg
import zlib

import websocket


OK_WS_URL = "wss://real.OKEx.com:8443/ws/v3"

class OKPriceClient:
    logger = logging.getLogger()

    def __init__(self, ws_url: str, product_id: str, expiry: int):
        assert(isinstance(ws_url, str))
        assert(isinstance(product_id, str))
        assert(isinstance(expiry, int))

        self.logger.info("OKPriceFeed22222 =================%s" % ws_url)

        self.ws_url = ws_url
        self.product_id = product_id
        self.expiry = expiry
        self._last_price = None
        self._last_timestamp = 0
        self._last_obook_timestamp = 0
        self._expired = True
        self._obook_expired = True
        self._asks = None
        self._bids = None
        threading.Thread(target=self._background_run, daemon=True).start()

    def _background_run(self):
        self.logger.info("OKPriceFeed33333333 =================")
        while True:
            self.logger.info("OKPriceFeed5555555 =================")
            ws = websocket.WebSocketApp(url=self.ws_url,
                                        on_message=self._on_message,
                                        on_error=self._on_error,
                                        on_open=self._on_open,
                                        on_close=self._on_close)
            ws.run_forever(ping_interval=15, ping_timeout=10)
            time.sleep(1)

    def _on_open(self, ws):
        self.logger.info("OKPriceFeed444444444444 =================")
        self.logger.info(f"OKEX {self.product_id} WebSocket connected")

        ws.send("""{
                    "op": "subscribe",
                    "args":[
                    "spot/ticker:%s"
                    ]}""" % self.product_id)

    def _on_close(self, ws):
        self.logger.info(f"GDAX {self.product_id} WebSocket disconnected")

    def _on_message(self, ws, message):
        self.logger.info("message:%s" % message)

        decompress = zlib.decompressobj(
            -zlib.MAX_WBITS  # see above
        )
        inflated = decompress.decompress(message)
        inflated += decompress.flush()

        self.logger.info("message:%s" % inflated)
        try:
            message_obj = json.loads(message)
            if message_obj['type'] == 'subscriptions':
                pass

            elif message_obj['table'] == 'spot/ticker':
                self._process_ticker(message_obj)

            elif message_obj['type'] == 'heartbeat':
                self._process_heartbeat()

            # elif message_obj['type'] == 'snapshot':
            #     self._process_snapshot(message_obj)

            elif message_obj['type'] == 'l2update':
                self._process_l2update(message_obj)

            else:
                self.logger.warning(f"GDAX {self.product_id} WebSocket received unknown message type: '{message}'")
        except:
            self.logger.warning(f"GDAX {self.product_id} WebSocket received invalid message: '{message}'")

    def _on_error(self, ws, error):
        self.logger.info(f"GDAX {self.product_id} WebSocket error: '{error}'")

    def get_price(self) -> Optional[Decimal]:
        if time.time() - self._last_timestamp > self.expiry:
            if not self._expired:
                self.logger.warning(f"Price feed from GDAX ({self.product_id}) has expired")

            return None

        else:
            value = self._last_price

            return value

    def get_obook_price(self):
        '''
        get_obook_price process
        * if price feed is expired return None
        * else do best ask + best bid then divide by 2 for midpoint
        '''
        if time.time() - self._last_obook_timestamp > self.expiry:
            if not self._obook_expired:
                self.logger.warning(f"Orderbook price feed from GDAX ({self.product_id}) has expired")

            return None

        else:
            mid_point = Decimal((self._asks.peekitem(0)[0] + self._bids.peekitem(0)[0])/2)
            return mid_point


    def _process_ticker(self, message_obj):
        self.logger.debug("_process_ticker")
        self._last_price = Decimal(message_obj['data'][0]['last'])
        self._last_timestamp = time.time()

        self.logger.debug(f"Ticker price feed from OK is {self._last_price} ({self.product_id})")

        if self._expired:
            self.logger.info(f"Ticker price feed from OK ({self.product_id}) became available")
            self._expired = False


    # def _process_snapshot(self, message_obj):
    #     #NOTES: quantize is what allows us to specify decimal place
    #
    #     def _load_book(side, new_side):
    #
    #         for order in side:
    #             new_side[Decimal(order[0]).quantize(Decimal('1.00000000'))] = Decimal(order[1])
    #
    #         return new_side
    #
    #     self._bids = _load_book(message_obj['bids'], SortedDict(neg))
    #     self._asks = _load_book(message_obj['asks'], SortedDict())
    #     self._last_obook_timestamp = time.time()
    #
    #     if self._obook_expired:
    #         self.logger.info(f"Orderbook price feed from GDAX ({self.product_id}) became available")
    #         self._obook_expired = False

    def _process_l2update(self, message_obj):

        for change in message_obj['changes']:
            side = change[0]
            if side == 'buy':
                self._bids = self._update_book(self._bids, Decimal(change[1]), Decimal(change[2]))
            if side == 'sell':
                self._asks = self._update_book(self._asks, Decimal(change[1]), Decimal(change[2]))

        self._last_obook_timestamp = time.time()

    def _process_heartbeat(self):
        self._last_timestamp = time.time()

    def _update_book(self, orderb_side, price, amount):
        '''
        update_book process (utilizes SortedContainer)
        * if amount in incoming update = 0 -> remove
        * else if price already exists in book update amount
        * else order does not exist -> add

        return self._bids or self._asks
        '''

        if amount == Decimal('0'):
            orderb_side.__delitem__(price)

        elif orderb_side.__contains__(price):
            orderb_side.update({price: amount})

        else:
            orderb_side[price] = amount

        self.logger.debug(f"Orderbook price feed from GDAX is {self.get_obook_price()} ({self.product_id})")

        return orderb_side

    def _inflate(data):
        decompress = zlib.decompressobj(
            -zlib.MAX_WBITS  # see above
        )
        inflated = decompress.decompress(data)
        inflated += decompress.flush()
        return inflated


