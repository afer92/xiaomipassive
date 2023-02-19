# xiaomipassive
LYWSD02 and MiFlora passive scanner
### Exemple
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
