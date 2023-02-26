#!/usr/bin/python3

import argparse
import sys

from xiaomipassive import xiaomipassive as xiaomi
import asyncio

VERSION = "0.9.0 du 18/02/2023"

sclass = {"temperature": {"short": "Temp",
                          "expire_after": 1200,
                          "unit_of_measurement": "°C",
                          "device_class": "temperature",
                          "ejson": "temperature"},
          "moisture": {"short": "Moisture",
                       "expire_after": 1200,
                       "unit_of_measurement": "%",
                       "device_class": "humidity",
                       "ejson": "moisture"},
          "light": {"short": "Light",
                    "expire_after": 1200,
                    "unit_of_measurement": "lux",
                    "device_class": "illuminance",
                    "ejson": "light"},
          "conductivity": {"short": "Conductivity",
                           "expire_after": 1200,
                           "unit_of_measurement": "µS/cm",
                           "device_class": "humidity",
                           "ejson": "conductivity"},
          "battery": {"short": "battery",
                      "expire_after": 3600,
                      "unit_of_measurement": "%",
                      "device_class": "battery",
                      "ejson": "battery"},
          "signal": {"short": "Signal",
                     "expire_after": 1200,
                     "unit_of_measurement": "dBm",
                     "device_class": "signal_strength",
                     "ejson": "rssi"},
          "voltage": {"short": "Voltage",
                      "expire_after": 3600,
                      "unit_of_measurement": "V",
                      "device_class": "voltage",
                      "ejson": "volt"},
}


device = '''
    "identifiers": [
      "{topic1}{mac_id}"
    ],
    "connections": [
      [
        "mac",
        "{mac}"
      ]
    ],
    "manufacturer": "Xiaomi",
    "name": "{name_short}",
    "model": "{model_long}",
    "sw_version": "3.3.5"
'''

model1 = '''  "name": "{name_long} {device_classc}",
  "unique_id": "{mac_id}-{ejson}",
  "state_topic": "miflora/sensor/{topic}/state",
{device}
  "expire_after": "{expire_after}",
  "unit_of_measurement": "{unit_of_measurement}",
  "device_class": "{device_class}",
  "state_class": "measurement",
  "value_template": "{value_template}"
'''

stype2topic = {"temperature": "temperature",
               "moisture": "moisture",
               "humidity": "humidity",
               "volt" : "voltage",
               "light": "light",
               "battery": "battery",
               "conductivity": "conductivity",
               }
               

def auto_json(dclass = "temperature",
              mac = "15:03:10:12:F0:81",
              name_long = "LYWSD02 Cuisine 1",
              name_short = "Cuisine1",
              topic = "lywsd023",
              model = "LYWSD02",
              cmodel = "Xiaomi BLE",
              ):

    model_long = "{} Sensor ({})".format(cmodel, model.upper())
    topic1 = topic.capitalize()
    topic = topic.lower()

    dev = device.format(topic1=topic1,
                        name_short= name_short,
                        model_long=model_long,
                        # sclass=sclass[dclass]["short"],
                        mac_id=mac.lower().replace(":", ""),
                        mac=mac.lower(),
                        )
    dev = '  "device": {' + dev + "  },"
    aut = model1.format(name_long=name_long,
                        mac_id=mac.lower().replace(":", ""),
                        topic=topic,
                        device=dev,
                        ejson=sclass[dclass]["ejson"],
                        expire_after=sclass[dclass]["expire_after"],
                        unit_of_measurement=sclass[dclass]["unit_of_measurement"],
                        device_class=sclass[dclass]["device_class"],
                        device_classc=sclass[dclass]["device_class"].capitalize(),
                        value_template='{{ value_json.' + sclass[dclass]["ejson"] + ' }}'
                        )
    aut = "{\n" + aut + "}\n"

    return aut


def autostr(mac, dclass,
            topic='topic',
            model='model',
            name='name',
            cmodel='cmodel'):

    name_long = f"{name}"
    name_parts = name.split(" ")
    name_partsc = []
    for name_part in name_parts:
        name_partsc.append(name_part.capitalize())
    name_short = "".join(name_partsc)

    print("---- {} ----".format(dclass))
    print(f"Topic: homeassistant/sensor/{mac.lower().replace(':', '')}/{dclass}/config\nmsg:")
    print(auto_json(dclass=dclass,
                    name_long=name_long,
                    name_short=name_short,
                    topic=topic,
                    mac=mac,
                    model=model,
                    cmodel=cmodel,
                    ))
    print("----")


def scan():

    def callback(self, result):
        print(self.dump_result(result))

    def get_data():
        loop = asyncio.get_event_loop()
        scanner = xiaomi.XiaomiPassiveScanner
        miflora_scanner = scanner(loop, callback, timeout_seconds=240)
        try:
            loop.run_until_complete(miflora_scanner.run())
        except KeyboardInterrupt as err:
            print(err)

        for mac, device in miflora_scanner.xdevices.items():
            print(device)

        for mac, device in miflora_scanner.xdevices.items():
            name = device.name
            print(f"mac: {mac} name:{name}")
            dclass = 'signal'
            autostr(mac, dclass,
                    topic=dclass,
                    model=device.model,
                    name=name,
                    cmodel='Xiaomi BLE')
            dclass = 'battery'
            autostr(mac, dclass,
                    topic=dclass,
                    model=device.model,
                    name=name,
                    cmodel='Xiaomi BLE')
            for sensor in device.sensors:
                # print(f"stype: {sensor.stype}, {stype2topic[sensor.stype]}")
                dclass = stype2topic[sensor.stype]
                autostr(mac, dclass,
                        topic=stype2topic[sensor.stype],
                        model=device.model,
                        name=name,
                        cmodel='Xiaomi BLE')
            

    get_data()


def main():

    if len(sys.argv) == 1:
        return scan()

    parser = argparse.ArgumentParser(
                    prog = 'autodiscovery',
                    description = 'generate Mqtt json Autodiscovery msg',
                    epilog = "Version: {}".format(VERSION))
    parser.add_argument('-m', '--mac',
                        default="15:03:10:12:F0:81",
                        help="Mac address (default: %(default)s)")
    parser.add_argument('-n', '--name',
                        default="Cuisine 1",
                        help="Sensor name (default: %(default)s)")
    parser.add_argument('-t', '--topic',
                        default="lywsd023",
                        help="mqtt topic (default: %(default)s)")
    parser.add_argument('-w', '--hardware',
                        default="LYWSD02",
                        help="sensor model (default: %(default)s)")
    parser.add_argument('-c', '--chardware',
                        default="Xiaomi BLE",
                        help="class model (default: %(default)s)")

    args = parser.parse_args()


    mac = args.mac
    topic = args.topic
    model = args.hardware
    name = args.name
    cmodel = args.chardware

    for dclass in sclass.keys():
        autostr(mac, dclass,
                topic=topic,
                model=model,
                name=name,
                cmodel=cmodel)


if __name__ == "__main__":
    exit(main())
