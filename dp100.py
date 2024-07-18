import hid
import struct
import logging
import time
import crcmod
from threading import Lock, Event

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class DP100:
    VID = 0x2E3C
    PID = 0xAF01

    DR_H2D = 0xFB
    DR_D2H = 0xFA

    OP_DEVICEINFO = 0x10
    OP_BASICINFO = 0x30
    OP_BASICSET = 0x35
    OP_SYSTEMINFO = 0x40

    SET_MODIFY = 0x20
    SET_ACT = 0x80

    def __init__(self):
        self.device = None
        self._api_lock = Lock()
        self._abort_flag = Event()
        self.crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)

    def connect(self):
        try:
            self.device = hid.device()
            self.device.open(self.VID, self.PID)
            self.device.set_nonblocking(0)
            logger.info("Connected to DP100 device")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to DP100 device: {e}")
            return False

    def disconnect(self):
        if self.device:
            try:
                self.device.close()
                self.device = None
                logger.info("Disconnected from DP100 device")
            except Exception as e:
                logger.error(f"Error disconnecting from DP100 device: {e}")

    def abort_operation(self):
        self._abort_flag.set()

    def enable_output(self, enable=True):
        with self._api_lock:
            self._abort_flag.clear()
            data = self.gen_set(output=enable, vset=0, iset=0)
            if self.send_frame(self.OP_BASICSET, data):
                response = self.receive_frame()
                if response and response["op"] == self.OP_BASICSET:
                    set_info = self.parse_basic_set(response["data"])
                    if set_info and "status" in set_info and set_info["status"] == 1:
                        logger.info(
                            f"Output {'enabled' if enable else 'disabled'} successfully"
                        )
                        return True
            logger.error(f"Failed to {'enable' if enable else 'disable'} output")
            return False

    def gen_frame(self, op_code, data=b""):
        frame = bytes([self.DR_H2D, op_code & 0xFF, 0x0, len(data) & 0xFF]) + data
        crc = self.crc16(frame)
        return frame + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

    def send_frame(self, op_code, data=b""):
        frame = self.gen_frame(op_code, data)
        logger.debug(f"Sending frame: {frame.hex()}")
        try:
            self.device.write(frame)
            time.sleep(0.05)  # Wait for device to process
            return True
        except Exception as e:
            logger.error(f"Error sending frame: {e}")
            return False

    def receive_frame(self, timeout_ms=1000):
        start_time = time.time()
        while (time.time() - start_time) * 1000 < timeout_ms:
            if self._abort_flag.is_set():
                logger.warning("Operation aborted")
                return None
            try:
                response = self.device.read(64, timeout_ms=100)
                if response:
                    response_bytes = bytes(response)
                    logger.debug(f"Received raw data: {response_bytes.hex()}")
                    return self.check_frame(response_bytes)
            except Exception as e:
                logger.error(f"Error receiving frame: {e}")
            time.sleep(0.01)
        logger.error("Receive frame timed out")
        return None

    def check_frame(self, data):
        if len(data) < 6:
            logger.error("Received frame is too short")
            return None
        if data[0] == self.DR_D2H:
            op = data[1]
            data_len = data[3]
            if len(data) >= 4 + data_len + 2:
                if self.crc16(data[0 : 4 + data_len + 2]) == 0:
                    return {"op": op, "data": data[4 : 4 + data_len]}
        logger.error("Invalid frame received")
        return None

    def gen_set(self, output=False, vset=0, iset=0, ovp=30500, ocp=5050):
        data = bytes(
            [
                self.SET_MODIFY,
                1 if output else 0,
                vset & 0xFF,
                (vset >> 8) & 0xFF,
                iset & 0xFF,
                (iset >> 8) & 0xFF,
                ovp & 0xFF,
                (ovp >> 8) & 0xFF,
                ocp & 0xFF,
                (ocp >> 8) & 0xFF,
            ]
        )
        logger.debug(f"Generated set data: {data.hex()}")
        return data

    def get_device_info(self):
        with self._api_lock:
            self._abort_flag.clear()
            if self.send_frame(self.OP_DEVICEINFO):
                response = self.receive_frame()
                if response and response["op"] == self.OP_DEVICEINFO:
                    return self.parse_device_info(response["data"])
        return None

    def get_basic_info(self):
        with self._api_lock:
            self._abort_flag.clear()
            if self.send_frame(self.OP_BASICINFO):
                response = self.receive_frame()
                if response and response["op"] == self.OP_BASICINFO:
                    info = self.parse_basic_info(response["data"])
                    if info:
                        logger.debug(
                            f"Current output state: {info['vout']}V, {info['iout']}A"
                        )
                        return info
                    else:
                        logger.error("Failed to parse basic info")
                else:
                    logger.error("Unexpected or no response for basic info")
            else:
                logger.error("Failed to send basic info request")
        return None

    def set_output(self, voltage, current, max_retries=3):
        with self._api_lock:
            self._abort_flag.clear()
            for attempt in range(max_retries):
                if self._abort_flag.is_set():
                    logger.warning("Operation aborted")
                    return False

                # Set voltage and current
                data = self.gen_set(True, int(voltage * 1000), int(current * 1000))
                if not self.send_frame(self.OP_BASICSET, data):
                    logger.error("Failed to send set output frame")
                    continue

                response = self.receive_frame()
                if not response or response["op"] != self.OP_BASICSET:
                    logger.error(
                        f"Unexpected response type: {response['op'] if response else 'None'}"
                    )
                    continue

                set_info = self.parse_basic_set(response["data"])
                if not set_info or ("status" in set_info and set_info["status"] != 1):
                    logger.error(
                        f"Set output failed with status: {set_info['status'] if set_info else 'Unknown'}"
                    )
                    continue

                # Enable the output
                if not self.enable_output(True):
                    logger.error("Failed to enable output")
                    continue

                # Wait for the settings to take effect
                time.sleep(0.5)

                # Verify the output
                info = self.get_basic_info()
                if (
                    info
                    and abs(info["vout"] - voltage) < 0.1
                    and abs(info["iout"] - current) < 0.1
                ):
                    logger.info(
                        f"Output set and verified: {info['vout']}V, {info['iout']}A"
                    )
                    return True
                else:
                    logger.warning(
                        f"Output verification failed. Got: {info['vout']}V, {info['iout']}A"
                    )

                time.sleep(0.5)

            logger.error(
                f"Failed to set and verify output after {max_retries} attempts"
            )
            return False

    def get_settings(self):
        with self._api_lock:
            self._abort_flag.clear()
            if self.send_frame(self.OP_SYSTEMINFO):
                response = self.receive_frame()
                if response and response["op"] == self.OP_SYSTEMINFO:
                    return self.parse_system_info(response["data"])
        return None

    def set_settings(self, settings):
        with self._api_lock:
            self._abort_flag.clear()
            data = struct.pack(
                "<BHHHB",
                settings["backlight"],
                int(settings["over_power_protection"] * 10),
                settings["over_temperature_protection"],
                settings["key_sound"],
                settings["reverse_protection"],
            )
            if self.send_frame(self.OP_SYSTEMINFO, data):
                response = self.receive_frame()
                if response and response["op"] == self.OP_SYSTEMINFO:
                    return True
        return False

    def parse_device_info(self, data):
        return {
            "dev_type": data[0:15].split(b"\x00")[0].decode("utf-8"),
            "hdw_ver": (data[17] << 8 | data[16]) / 10,
            "app_ver": (data[19] << 8 | data[18]) / 10,
            "boot_ver": (data[21] << 8 | data[20]) / 10,
            "year": (data[37] << 8 | data[36]),
            "month": data[38],
            "day": data[39],
        }

    def parse_basic_info(self, data):
        if len(data) < 16:
            logger.error(f"Insufficient data for basic info: {len(data)} bytes")
            return None
        return {
            "vin": (data[1] << 8 | data[0]) / 1000,
            "vout": (data[3] << 8 | data[2]) / 1000,
            "iout": (data[5] << 8 | data[4]) / 1000,
            "vo_max": (data[7] << 8 | data[6]) / 1000,
            "temp1": (data[9] << 8 | data[8]) / 10,
            "temp2": (data[11] << 8 | data[10]) / 10,
            "dc_5v": (data[13] << 8 | data[12]) / 1000,
            "out_mode": data[14],
            "work_st": data[15],
        }

    def parse_basic_set(self, data):
        if len(data) == 1:
            # The device is sending a status byte
            status = data[0]
            logger.info(f"Set output status: {status}")
            return {"status": status}
        elif len(data) >= 10:
            try:
                return {
                    "index": data[0],
                    "state": data[1],
                    "vo_set": (data[3] << 8 | data[2]) / 1000,
                    "io_set": (data[5] << 8 | data[4]) / 1000,
                    "ovp_set": (data[7] << 8 | data[6]) / 1000,
                    "ocp_set": (data[9] << 8 | data[8]) / 1000,
                }
            except IndexError as e:
                logger.error(f"Error parsing basic set data: {e}")
                return None
        else:
            logger.error(f"Insufficient data for basic set: {len(data)} bytes")
            return None

    def parse_system_info(self, data):
        return {
            "backlight": data[0],
            "over_power_protection": (data[2] << 8 | data[1]) / 10,
            "over_temperature_protection": (data[4] << 8 | data[3]),
            "key_sound": data[5],
            "reverse_protection": bool(data[6] & 0x01),
            "power_on_state": bool(data[6] & 0x02),
        }


if __name__ == "__main__":
    # Test the implementation
    dp100 = DP100()
    try:
        if dp100.connect():
            print("Device Info:", dp100.get_device_info())
            print("Basic Info:", dp100.get_basic_info())
            print("Settings:", dp100.get_settings())

            # Test setting output
            test_voltage = 5.0  # 5V
            test_current = 1.0  # 1A
            print(f"Setting output to {test_voltage}V, {test_current}A")
            result = dp100.set_output(test_voltage, test_current)
            print("Set output result:", result)

            time.sleep(1)  # Wait for the change to take effect

            print("Updated Basic Info:", dp100.get_basic_info())
        else:
            print("Failed to connect to the device")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        dp100.disconnect()
