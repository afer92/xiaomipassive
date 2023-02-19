# xiaomipassive
LYWSD02 and MiFlora passive scanner
## Installation
```
git clone https://github.com/afer92/xiaomipassive.git
cd xiaomipassive
pip3 install .
```
## class XiaomiPassiveScanner
```Python
loop = asyncio.get_event_loop()
scanner = XiaomiPassiveScanner(loop, callback, timeout_seconds=240)
```
### callback
Function call at each received advertissement
```Python
def callback(self, data):
    print(self.dump_result(data))
```
Output:
```
mac: C4:7C:8D:65:xx:yy conductivity: 376 µS/cm
mac: 80:EA:CA:89:xx:yy light:        283 lux
mac: 15:03:10:12:xx:yy moisture:     47.0 %
mac: C4:7C:8D:65:xx:yy temperature:  20.8 °C
mac: E7:2E:01:71:xx:yy battery:      18 %
```
Function **dump_result** format the data decoded in an advertisement

Dictionnary **data**:
```Python
{'ok': True,
 'mac': 'C4:7C:8D:6C:xx:yy',
 'sensor': 4100,
 'stype': 'temperature',
 'svalue': ListContainer([123, 0]),
 'typeCst': ListContainer([113, 32, 152, 0]),
 'num': 247,
 'tab': 13,
 'name': 'Flower care',
 'rssi': -87,
 'value': 12.3
 }
```
### timeout_seconds
Scan for **timeout_seconds**, default=240s
### devices
After **timeout_seconds** scanning, data collected for each mac address

Function **dump_device(mac)** format the data for one mac address
```
E7:2E:01:71:xx:yy LYWSD02
=================
rssi:          -89 dBm
battery:      18 %
temperature:  20.9 °C
moisture:     49.0 %


C4:7C:8D:6C:xx:yy Flower care
=================
rssi:          -87 dBm
temperature:  12.4 °C
moisture:     28 %
light:        151 lux
conductivity: 432 µS/cm
```

## Example
```Python
#!/usr/bin/python3

from xiaomipassive import xiaomipassive as xiaomi
import asyncio

def main():

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

        for mac, device in miflora_scanner.devices.items():
            print(miflora_scanner.dump_device(mac))

    get_data()


if __name__ == '__main__':
    exit(main())
```
