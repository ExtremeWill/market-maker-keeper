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
import requests

class OasisPriceClient:
    logger = logging.getLogger()

    def __init__(self, expiry: int):
        assert(isinstance(expiry, int))

        self.expiry = expiry
        self._last_price = None
        self._last_timestamp = 0
        self._expired = True
        threading.Thread(target=self._background_run, daemon=True).start()

    def _background_run(self):
        while True:
            r = requests.get("https://api.oasisdex.com/v2/prices/dai/usdc",timeout=4)  # 发get请求
            if r.status_code == 200:
                jsondata = r.json()
                if jsondata["message"] == "success":
                    data = jsondata["data"]
                    if data:
                        self._last_price = data["last"]
                        self.logger.info("oasis========_last_price=%s" % self._last_price)
                        self._last_timestamp = time.time()
                        self.logger.info("oasis========_last_time=%d" % self._last_timestamp)

            time.sleep(10)

    def get_price(self) -> Optional[Decimal]:
        if time.time() - self._last_timestamp > self.expiry:
            if not self._expired:
                self.logger.warning("Price feed from OASIS DAI_USDC has expired")

            return None

        else:
            value = self._last_price
            return value



