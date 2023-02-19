#!/usr/bin/python3

from time import sleep
from datetime import datetime
from socket import gethostname
import os
import asyncio

from bleak import BleakScanner
from bleak import _logger as logger

import logging
import logging.handlers
import queue

import construct
from construct import Array, Byte, Const, Int8sl, Int8ub, Int16ub, Struct
from construct import Int8ul, Int16ul, Int16sl
from construct.core import ConstError, StreamError
from construct import this


"""
type    length  data
1004    02      c900    -> temperature in 0.1°C  0x00c9 = 201 (20.1°C)(MiFlora)
1006                    -> moisture in 0.1%                           (LYWDS02)
1007    03      d24101  -> light in lux          0x0141d2 = 82386 lux (MiFlora)
1008    01      38      -> moisture in %         0x38 = 56%           (MiFlora)
1009    02      7011    -> conductivity in µS/cm 0x0619 = 1561 µS/cm  (MiFlora)
"""

xiaomi_format = Struct(
    "typeCst" / Array(4, Byte),
    "num" / Int8ul,
    "mac" / Array(6, Byte),
    "tab" / Int8ul,
    "sensor" / Int16ul,
    "datal" / Int8ul,
    "value" / Array(this.datal, Byte)
)

senso2type = {0x1004: 'temperature',
              0x1006: 'moisture',
              0x1007: 'light',
              0x1008: 'moisture',
              0x1009: 'conductivity',
              0x100a: 'battery',
              }

DEBUG = False


class XiaomiPassiveScanner:

    def __init__(self, loop, callback, timeout_seconds=240):
        self.loop = loop
        self.callback = callback
        or_patterns = []
        self.devices = {}
        self.timeout_seconds = timeout_seconds

        self._scanner = BleakScanner(scanning_mode='passive',
                                     detection_callback=self.detection_callback,
                                     )
        self.scanning = asyncio.Event()

    def ad_decode(self, todecode):
        result = {"ok": False,
                  "mac": "",
                  "sensor": 0,
                  "stype": "",
                  "svalue": None}
        try:
            test = xiaomi_format.parse(todecode)
        except construct.core.StreamError:
            return result
        result["ok"] = True
        result["mac"] = self.to_hex_string(test.mac)
        result["typeCst"] = test.typeCst
        result["sensor"] = test.sensor
        result["num"] = test.num
        result["tab"] = test.tab
        if test.sensor in senso2type.keys():
            result["stype"] = senso2type[test.sensor]
        else:
            result["stype"] = "{:04X}".format(test.sensor)
        result["svalue"] = test.value
        return result

    def hex_string_ip(self, data):
        result = bytearray(data)
        result.reverse()
        return ':'.join('{:02x} '.format(x)
                        for x in result).upper().replace(" ", "")

    def to_hex_string(self, data):
        macdecode = ""
        for one in data:
            macdecode = "{:02X}:{}".format(one, macdecode)
        return macdecode[:-1]

    def decode2val(self, result):
        if result["stype"] == 'temperature':
            temperature = int.from_bytes(result["svalue"],
                                         "little", signed=True)
            if (temperature > -200) and (temperature < 600):
                temperature = round(temperature * 0.1, 1)
                result["value"] = temperature
            else:
                print("==> temperature: {} °C".format(temperature))
        elif result["stype"] == 'conductivity':
            conductivity = int.from_bytes(result["svalue"],
                                          "little", signed=False)
            result["value"] = conductivity
        elif result["stype"] == 'moisture':
            moisture = int.from_bytes(result["svalue"], "little", signed=False)
            if result["name"] == 'LYWSD02':
                moisture = round(moisture * 0.1, 1)
            if (moisture >= 0) and (moisture <= 100):
                result["value"] = moisture
        elif result["stype"] == 'light':
            light = int.from_bytes(result["svalue"], "little", signed=False)
            result["value"] = light
        elif result["stype"] == 'battery':
            battery = int.from_bytes(result["svalue"], "little", signed=False)
            if battery <= 100:
                result["value"] = battery
        else:
            print("==> {}: {}".format(result["stype"], result["svalue"]))
        return result

    def _unit_from_stype(self, stype):
        formatstr = "{}"
        if stype == "temperature":
            formatstr += ":  {} °C"
        elif stype == "battery":
            formatstr += ":      {} %"
        elif stype == "moisture":
            formatstr += ":     {} %"
        elif stype == "light":
            formatstr += ":        {} lux"
        elif stype == "conductivity":
            formatstr += ": {} µS/cm"
        elif stype == "rssi":
            formatstr += ":          {} dBm"
        return formatstr

    def dump_result(self, result):
        formatstr = "mac: {} " + self._unit_from_stype(result["stype"])
        strresult = formatstr.format(result["mac"],
                                     result["stype"], result["value"])
        return strresult

    def dump_device(self, mac):
        if mac not in self.devices.keys():
            return ""
        data = self.devices[mac]
        strresult = "\n{} {}\n=================\n".format(mac, data["name"])
        for key in ("rssi", "battery", "temperature",
                    "moisture", "light", "conductivity"):
            if key in data.keys():
                line = self._unit_from_stype(key).format(key, data[key])
                strresult += line + "\n"
        return strresult

    def detection_callback(self, device, advertisement_data):

        if advertisement_data.service_data is None:
            return
        elif advertisement_data.service_data.keys() is None:
            return
        elif advertisement_data.service_data.keys == []:
            return
        for key, value in advertisement_data.service_data.items():
            if len(value) > 15:
                result = self.ad_decode(value)
                if result["ok"] is False:
                    return
                if result["mac"] != device.address:
                    return
                result["name"] = advertisement_data.local_name
                # result["rssi"] = advertisement_data.rssi
                result["rssi"] = device.rssi
                address = result["mac"]
                if (result["mac"] in self.devices.keys()) is False:
                    self.devices[address] = {}
                    self.devices[address]['name'] = result["name"]
                    self.devices[address]['sensor'] = result["mac"]
                    self.devices[address]['from'] = gethostname()
                    dtnow = "{}".format(datetime.now())[:19].replace(' ', 'T')
                    self.devices[address]['dtmsg'] = dtnow
                    self.devices[address]['rssi'] = result["rssi"]
                # print(result)
                self.decode2val(result)
                if self.callback is not None:
                    self.callback(self, result)
                if "value" in result.keys():
                    self.devices[address][result['stype']] = result['value']
                # print(self.devices[address])
            else:
                return
        return

    async def run(self):
        await self._scanner.start()
        self.scanning.set()
        end_time = self.loop.time() + self.timeout_seconds
        while self.scanning.is_set():
            if self.loop.time() > end_time:
                self.scanning.clear()
                # print('\t\tScan has timed out so we terminate')
            await asyncio.sleep(0.1)
        await self._scanner.stop()
        # self.callback(self)


def main():

    def callback(self, result):
        print(self.dump_result(result))

    def get_data():
        loop = asyncio.get_event_loop()
        miflora_scanner = XiaomiPassiveScanner(loop,
                                               callback,
                                               timeout_seconds=240)
        try:
            loop.run_until_complete(miflora_scanner.run())
        except KeyboardInterrupt as err:
            print(err)

        for mac, device in miflora_scanner.devices.items():
            print(miflora_scanner.dump_device(mac))

    get_data()


if __name__ == '__main__':
    exit(main())
