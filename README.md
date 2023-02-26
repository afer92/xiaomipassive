# xiaomipassive
LYWSD02, LYWSD03MMC (custom firmware ATC) and MiFlora passive scanner
## Installation
```
git clone https://github.com/afer92/xiaomipassive.git
cd xiaomipassive
pip3 install .
```
## Command line tool
```
xiaomipassivec
```
Output:
```
mac: 80:EA:CA:89:xx:yy conductivity:   54 µS/cm (2023-02-26T00:42:25)
mac: C4:7C:8D:64:xx:yyconductivity:  837 µS/cm (2023-02-26T00:42:25)
mac: C4:7C:8D:6C:xx:yy light:          26 lux   (2023-02-26T00:42:26)
...
A4:C1:38:09:xx:yy ATC_0990AB
=================
mac: A4:C1:38:09:xx:yyB rssi:          -35 dBm   (2023-02-26T00:42:39)
mac: A4:C1:38:09:xx:yy temperature:  21.6 °C    (2023-02-26T00:42:39)
mac: A4:C1:38:09:xx:yy moisture:       32 %     (2023-02-26T00:42:39)
mac: A4:C1:38:09:xx:yyB battery:        93 %     (2023-02-26T00:42:39)
mac: A4:C1:38:09:xx:yy volt:         3.04 V     (2023-02-26T00:42:39)
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
mac: E7:2E:01:71:xx:yy rssi:          -93 dBm   (2023-02-24T19:34:19)
mac: E7:2E:01:71:xx:yy moisture:     47.0 %     (2023-02-24T19:32:44)
mac: E7:2E:01:71:xx:yy temperature:  20.6 °C    (2023-02-24T19:34:18)
mac: E7:2E:01:71:xx:yy battery:        18 %     (2023-02-24T19:33:37)

C4:7C:8D:65:B1:1D Flower care
=================
mac: C4:7C:8D:65:xx:yy rssi:          -81 dBm   (2023-02-24T19:34:19)
mac: C4:7C:8D:65:xx:yy light:         118 lux   (2023-02-24T19:33:41)
mac: C4:7C:8D:65:xx:yy moisture:       21 %     (2023-02-24T19:33:52)
mac: C4:7C:8D:65:xx:yy conductivity:  309 µS/cm (2023-02-24T19:34:04)
mac: C4:7C:8D:65:xx:yy temperature:  20.7 °C    (2023-02-24T19:34:15)
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

        for mac, device in miflora_scanner.xdevices.items():
            print(device)

    get_data()


if __name__ == '__main__':
    exit(main())
```
