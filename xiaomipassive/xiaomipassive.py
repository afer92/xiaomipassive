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
from construct import Int8ul, Int16ul, Int16sl, Int16sb
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
    "typeCst" / Array(2, Byte),
    "typeDev" / Int16ul,
    "num" / Int8ul,
    "mac" / Array(6, Byte),
    "tab" / Int8ul,
    "sensor" / Int16ul,
    "datal" / Int8ul,
    "value" / Array(this.datal, Byte)
)

xiaomi1_format = Struct(
    "mac" / Array(6, Byte),
    "temp" / Int16sb,
    "moisture" / Int8ub,
    "battery" / Int8ub,
    "volt" / Int16ub,
    "cpt" / Int8ub,
)

senso2type = {0x1004: 'temperature', # Temperature
              0x1006: 'moisture', # Humidity
              0x1007: 'light', # Illuminance
              0x1008: 'moisture', # Moisture
              0x1009: 'conductivity', # Conductivity
              0x100a: 'battery', # Battery
              0x100d: 'battery', # Temperature and humidity
              }

uuid_lywsd03 = '0000181a-0000-1000-8000-00805f9b34fb'

stype2unit = {'temperature': '°C',
              'moisture': '%',
              'humidity': '%',
              'light': 'lux',
              'conductivity': 'µS/cm',
              'battery': '%',
              'volt': 'V',
              'rssi': 'dBm',
              }


# Device type dictionary
# {device type code: device name}
XIAOMI_TYPE_DICT = {
    0x0098: "HHCCJCY01",  # Miflora Flower care
    0x045B: "LYWSD02",
    0x16e4: "LYWSD02MMC",
    0x055B: "LYWSD03MMC",
}

DEBUG = False


class XiaomiSensor:

    def __init__(self, device, stype, value):
        self._device = device
        self._stype = stype
        self._value = value
        dtnow = "{}".format(datetime.now())[:19].replace(' ', 'T')
        self._dtmsg = dtnow

    def sensor_update(self, value):
        dtnow = "{}".format(datetime.now())[:19].replace(' ', 'T')
        self._dtmsg = dtnow
        self._value = value

    @property
    def value(self):
        return self._value

    @property
    def stype(self):
        return self._stype

    @property
    def dtmsg(self):
        return self._dtmsg

    def __repr__(self):
        if self._stype in stype2unit.keys():
            strresult = f"mac: {self._device.mac} "\
                f"{self._stype+':':<13}"\
                f"{self._value:>5} "\
                f"{stype2unit[self._stype]:<5} "\
                f"({self._dtmsg})"
        else:
            strresult = f"mac: {self._device.mac} "\
                f"{self._stype+':':<13}"\
                f"{self._value:>5} "\
                f"({self._dtmsg})"
        return strresult


class XiaomiDevice:

    def __init__(self, mac, rssi=None, name=None):
        self._mac = mac
        self._rssi = rssi
        self._name = name
        self._server = gethostname()
        self._sensors = []
        self._stype2sensor = {}

    def init(self, load_data):
        for key, value in data_items():
            if key == 'name':
                self._name = value

    def sensor_add(self, stype, value):
        if stype in self._stype2sensor.keys():
            self.sensor_update(stype, value)
        else:
            sensor = XiaomiSensor(self, stype, value)
            self._stype2sensor[stype] = sensor
            self._sensors.append(sensor)

    def sensor_update(self, stype, value):
        if stype in self._stype2sensor.keys():
            sensor = self._stype2sensor[stype]
            sensor.sensor_update(value)
        else:
            self.sensor_add(stype, value)

    def __repr__(self):
        strresult = f"\n{self._mac} {self._name}\n=================\n"
        if self._rssi is not None:
            sensor = XiaomiSensor(self, 'rssi', self._rssi)
            line = f'{sensor}'
            strresult += line + "\n"
        for sensor in self._sensors:
            line = f'{sensor}'
            strresult += line + "\n"
        return strresult

    @property
    def mac(self):
        return self._mac

    @property
    def rssi(self):
        return self._rssi

    @rssi.setter
    def rssi(self, rssi):
        self._rssi = rssi

    @property
    def signal(self):
        return self._rssi

    @signal.setter
    def signal(self, signal):
        self._rssi = signal

    @property
    def name(self):
        return self._name

    @property
    def server(self):
        return self._server

    @property
    def sensors(self):
        return self._sensors

    @property
    def data(self):
        data = {}
        data['sensor'] = self._mac
        data['name'] = self._name
        data['rssi'] = self._rssi
        data['from'] = self._server
        for sensor in self._sensors:
            data['dtmsg'] = sensor.dtmsg
            data[sensor.stype] = sensor.value
        return data


class XiaomiPassiveScanner:

    def __init__(self, loop, callback, timeout_seconds=240):
        self.loop = loop
        self.callback = callback
        or_patterns = []
        #self.devices = {}
        self.xdevices = {}
        self.timeout_seconds = timeout_seconds

        self._scanner = BleakScanner(scanning_mode='passive',
                                     detection_callback=self.detection_callback,
                                     )
        self.scanning = asyncio.Event()

    def hex_string_ip_1(self, data):
        result = bytearray(data)
        return ':'.join('{:02x} '.format(x)
                        for x in result).upper().replace(" ", "")

    def test_data(self, data, min, max):
        if data < min:
            return False
        elif data > max:
            return False
        return True

    def ad_decode1(self, todecode):
        result = {"ok": False,
                  "mac": "",
                  "sensor": 0,
                  "stype": "",
                  "svalue": None}
        try:
            test = xiaomi1_format.parse(todecode)
        except construct.core.StreamError:
            return result

        result["ok"] = True
        result["mac"] = self.hex_string_ip_1(test.mac)
        result["stype"] = "multi"
        if self.test_data(test.temp, -200, 600):
            result["temperature"] = round(test.temp * 0.1, 1)
        else:
            result["ok"] = False
        if self.test_data(test.moisture, 0, 100):
            result["moisture"] = test.moisture
        else:
            result["ok"] = False
        if self.test_data(test.battery, 0, 100):
            result["battery"] = test.battery
        else:
            result["ok"] = False
        if self.test_data(test.volt, 0, 4000):
            result["volt"] = round(test.volt * 0.001, 3)
        else:
            result["ok"] = False
        return result

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
        if test.typeDev in XIAOMI_TYPE_DICT.keys():
            result['xtype'] = test.typeDev
            # print(f"typeDev: {test.typeDev:04x} {XIAOMI_TYPE_DICT[test.typeDev]}")
        else:
            print(f"typeDev: {test.typeDev:04x}")
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

    def dump_result(self, result):
        if result["stype"] != "multi":
            xsensor = XiaomiSensor(XiaomiDevice(result['mac']),
                                   result["stype"], result['value'])
            strresult = f"{xsensor}"
        else:
            strresult = self.dump_device(result["mac"])
        return strresult

    def dump_device(self, mac):
        if mac not in self.xdevices.keys():
            return ""
        device = self.xdevices[mac]
        return f"{device}"

    def detection_callback(self, device, advertisement_data):

        def init_device(result):
            deviceh = {}
            deviceh['name'] = result["name"]
            deviceh['sensor'] = result["mac"]
            deviceh['rssi'] = result["rssi"]
            dtnow = "{}".format(datetime.now())[:19].replace(' ', 'T')
            deviceh['dtmsg'] = dtnow
            deviceh['from'] = gethostname()
            for key in ("temperature", "moisture", "battery", "volt"):
                if key in result.keys():
                    deviceh[key] = result[key]
            return deviceh

        if advertisement_data.service_data is None:
            return
        elif advertisement_data.service_data.keys() is None:
            return
        elif advertisement_data.service_data.keys == []:
            return
        for key, value in advertisement_data.service_data.items():
            address = device.address
            name = advertisement_data.local_name
            rssi = device.rssi
            if (len(value) == 13) and (key == uuid_lywsd03):
                # LYWSD03mmc custom
                temperature = int.from_bytes(value[6:8], "big", signed=True)
                temperature = round(temperature * 0.1, 2)
                moisture = int.from_bytes(value[8:9], "big", signed=False)
                battery = int.from_bytes(value[9:10], "big", signed=False)
                vbattery = int.from_bytes(value[10:12], "big", signed=False)
                vbattery = round(vbattery * 0.001, 2)
                """
                print("temperature: {} °C".format(temperature))
                print("moisture: {} %".format(moisture))
                print("battery: {} %".format(battery))
                print("vbattery: {} V".format(vbattery))
                """
                result = self.ad_decode1(value)
                result["mac"] = address
                result["name"] = name
                result["rssi"] = rssi
                if result["ok"] is False:
                    return
                if result["mac"] != device.address:
                    return
                if device.address not in self.xdevices.keys():
                    self.xdevices[device.address] = XiaomiDevice(address,
                                                                 rssi=rssi,
                                                                 name=name)
                    xd = self.xdevices[device.address]
                    xd.sensor_add('temperature', temperature)
                    xd.sensor_add('moisture', moisture)
                    xd.sensor_add('battery', battery)
                    xd.sensor_add('volt', vbattery)
                else:
                    xd = self.xdevices[device.address]
                    xd.sensor_update('temperature', temperature)
                    xd.sensor_update('moisture', moisture)
                    xd.sensor_update('battery', battery)
                    xd.sensor_update('volt', vbattery)
                if self.callback is not None:
                    self.callback(self, result)
            elif len(value) > 15:
                result = self.ad_decode(value)
                result["mac"] = address
                result["name"] = name
                result["rssi"] = rssi
                if result["ok"] is False:
                    return
                if result["mac"] != device.address:
                    return
                init_device(result)
                result["name"] = advertisement_data.local_name
                result["rssi"] = device.rssi
                self.decode2val(result)
                if 'value' in  result.keys():
                    if device.address not in self.xdevices.keys():
                        self.xdevices[device.address] = XiaomiDevice(address,
                                                                     rssi=rssi,
                                                                     name=name)
                        xd = self.xdevices[device.address]
                        xd.sensor_add(result['stype'], result['value'])
                    else:
                        xd = self.xdevices[device.address]
                        xd.sensor_update(result['stype'], result['value'])
                    if self.callback is not None:
                        self.callback(self, result)
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

        for mac, device in miflora_scanner.xdevices.items():
            print(device)

    get_data()


if __name__ == '__main__':
    exit(main())
