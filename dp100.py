import hid
import struct
import logging
import threading
import queue
import time

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

DP100_USB_INFO = {"vendor_id": 0x2E3C, "product_id": 0xAF01}


def crc16(data: bytes, poly: int = 0xA001) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ poly if (crc & 0x0001) else crc >> 1
    return crc


class DP100:
    def __init__(self):
        self.device = None
        self._command_queue = queue.Queue()
        self._response_queue = queue.Queue()
        self._thread = None
        self._stop_event = threading.Event()
        self._abort_flag = threading.Event()

    def abort_operation(self):
        self._abort_flag.set()
        # Clear the command queue
        while not self._command_queue.empty():
            try:
                self._command_queue.get_nowait()
            except queue.Empty:
                pass
        # Put a None response in the response queue to unblock any waiting threads
        self._response_queue.put(None)

    def _execute_command(self, command):
        self._abort_flag.clear()
        function_type, data = command
        if self.send_frame(function_type, data):
            start_time = time.time()
            while time.time() - start_time < 5:  # 5 second timeout
                if self._abort_flag.is_set():
                    self._response_queue.put(None)
                    return
                response = self.receive_frame(timeout_ms=100)
                if response:
                    self._response_queue.put(response)
                    return
        self._response_queue.put(None)

    def connect(self):
        if not self.device:
            try:
                self.device = hid.device()
                self.device.open(
                    DP100_USB_INFO["vendor_id"], DP100_USB_INFO["product_id"]
                )
                self.device.set_nonblocking(0)
                logger.info("Connected to DP100 device")
                self._thread = threading.Thread(target=self._communication_thread)
                self._thread.start()
            except Exception as e:
                logger.error(f"Failed to connect to DP100 device: {e}")
                raise

    def disconnect(self):
        if self.device:
            try:
                self._stop_event.set()
                if self._thread:
                    self._thread.join(timeout=5)
                self.device.close()
                self.device = None
                logger.info("Disconnected from DP100 device")
            except Exception as e:
                logger.error(f"Error disconnecting from DP100 device: {e}")

    def _communication_thread(self):
        while not self._stop_event.is_set():
            try:
                command = self._command_queue.get(timeout=0.1)
                self._execute_command(command)
            except queue.Empty:
                pass

    def _execute_command(self, command):
        function_type, data = command
        if self.send_frame(function_type, data):
            response = self.receive_frame()
            self._response_queue.put(response)
        else:
            self._response_queue.put(None)

    def reset_device(self, timeout=5):
        start_time = time.time()
        self.clear_buffer()
        # Assuming 0x00 is the reset command, adjust as per actual documentation
        if not self.send_frame(0x00, b""):
            logger.error("Failed to send reset command")
            return False
        while time.time() - start_time < timeout:
            response = self.receive_frame(timeout_ms=100)
            if response and response["function_type"] == 0x00:
                logger.info("Device reset successful")
                return True
            time.sleep(0.1)
        logger.error("Reset command timed out")
        return False

    def check_device_state(self):
        self.clear_buffer()
        if not self.send_frame(0x30, b""):  # Assuming 0x30 is for getting basic info
            logger.error("Failed to send state check command")
            return False
        response = self.receive_frame()
        if not response or response["function_type"] != 0x30:
            logger.error(f"State check failed: {response}")
            return False
        # Analyze the response to determine if the device is ready
        # You'll need to interpret the meaning of the response data
        state = self.interpret_state(response["data"])
        logger.info(f"Device state: {state}")
        return state == "READY"  # Or whatever indicates a ready state

    def clear_buffer(self):
        while True:
            response = self.device.read(64, timeout_ms=100)
            if not response:
                break
        logger.debug("Buffer cleared")

    def send_frame(self, function_type, data):
        if not self.device:
            logger.error("Device not connected")
            return False

        frame = struct.pack("<BBBB", 251, function_type, 0, len(data)) + data
        checksum = crc16(frame)
        frame += struct.pack("<H", checksum)
        logger.debug(f"Sending frame: {frame.hex()}")
        try:
            bytes_written = self.device.write(frame)
            if bytes_written != len(frame):
                logger.error(
                    f"Failed to write complete frame. Wrote {bytes_written} of {len(frame)} bytes."
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Error sending frame: {e}")
            return False

    def receive_frame(self, timeout_ms=1000):
        if not self.device:
            logger.error("Device not connected")
            return None

        start_time = time.time()
        while (time.time() - start_time) * 1000 < timeout_ms:
            try:
                response = self.device.read(64, timeout_ms=100)
                if response:
                    response_bytes = bytes(response)
                    logger.debug(f"Received raw data: {response_bytes.hex()}")
                    if len(response) < 6:
                        logger.error("Received frame is too short")
                        return None
                    function_type = response[1]
                    data_len = response[3]
                    data = bytes(response[4 : 4 + data_len])
                    logger.debug(f"Extracted data: {data.hex()}")
                    return {"function_type": function_type, "data": data}
            except Exception as e:
                logger.error(f"Error receiving frame: {e}")
                return None
            time.sleep(0.01)  # Short sleep to prevent busy-waiting
        logger.error("Receive frame timed out")
        return None

    def get_basic_info(self):
        if not self.send_frame(0x30, b""):
            logger.error("Failed to send basic info request")
            return None
        response = self.receive_frame()
        if response and response["function_type"] == 0x30:
            data = response["data"]
            if len(data) == 16:
                unpacked = struct.unpack("<HHHHHHHH", data)
                return {
                    "vin": unpacked[0] / 100,
                    "vout": unpacked[1] / 1000,
                    "iout": unpacked[2] / 1000,
                    "power": unpacked[3] / 100,
                    "temp1": unpacked[4] / 10,
                    "temp2": unpacked[5] / 10,
                    "dc_5v": unpacked[6] / 1000,
                    "status": unpacked[7],
                }
        logger.error("Failed to get basic info")
        return None

    def set_output(self, voltage, current, max_retries=3):
        for attempt in range(max_retries):
            logger.info(f"Attempt {attempt + 1} to set output")

            # Check device state
            info = self.get_basic_info()
            if not info:
                logger.error("Failed to get basic info")
                continue

            # Prepare and send set output command
            data = struct.pack(
                "<BHHHH", 0x20, 1, int(voltage * 1000), int(current * 1000), 0xFFFF
            )
            if not self.send_frame(0x35, data):
                logger.error("Failed to send set output frame")
                continue

            # Wait for response
            response = self.receive_frame()
            if not response:
                logger.error("No response received for set output command")
                continue

            if response["function_type"] != 0x35:
                logger.error(f"Unexpected response type: {response['function_type']}")
                continue

            # Verify the output was set correctly
            time.sleep(0.5)  # Wait for the change to take effect
            info = self.get_basic_info()
            if (
                info
                and abs(info["vout"] - voltage) < 0.1
                and abs(info["iout"] - current) < 0.1
            ):
                logger.info(f"Output set successfully: {voltage}V, {current}A")
                return True

            logger.warning("Output verification failed, retrying...")

        logger.error("Failed to set output after multiple attempts")
        return False

    def get_device_info(self):
        if not self.send_frame(0x31, b""):
            return None
        response = self.receive_frame()
        if response and response["function_type"] == 0x31:
            return self.parse_device_info(response["data"])
        return None

    def parse_device_info(self, data):
        if len(data) >= 32:
            return {
                "device_name": data[:8].decode().strip("\x00"),
                "hardware_version": data[8:12].decode().strip("\x00"),
                "software_version": data[12:16].decode().strip("\x00"),
                "serial_number": data[16:32].decode().strip("\x00"),
            }
        return None

    def get_settings(self):
        if not self.send_frame(0x37, b""):
            logger.error("Failed to send get settings request")
            return None
        response = self.receive_frame()
        if response and response["function_type"] == 0x37:
            data = response["data"]
            if len(data) >= 8:
                unpacked = struct.unpack("<BBHHHB", data[:9])
                return {
                    "backlight": unpacked[0],
                    "key_sound": unpacked[1],
                    "over_power_protection": unpacked[2] / 10,
                    "over_temperature_protection": unpacked[3],
                    "reverse_protection": bool(unpacked[4]),
                    "power_on_state": unpacked[5],
                }
        logger.error("Failed to get settings")
        return None

    def set_settings(
        self,
        backlight=None,
        volume=None,
        opp=None,
        otp=None,
        reverse_protect=None,
        auto_output=None,
    ):
        current_settings = self.get_settings()
        if current_settings:
            backlight = (
                backlight if backlight is not None else current_settings["backlight"]
            )
            volume = volume if volume is not None else current_settings["volume"]
            opp = opp if opp is not None else current_settings["opp"]
            otp = otp if otp is not None else current_settings["otp"]
            reverse_protect = (
                reverse_protect
                if reverse_protect is not None
                else current_settings["reverse_protect"]
            )
            auto_output = (
                auto_output
                if auto_output is not None
                else current_settings["auto_output"]
            )

            data = struct.pack(
                "<BBHHHBB",
                backlight,
                volume,
                int(opp * 10),
                otp,
                reverse_protect,
                auto_output,
            )
            if not self.send_frame(0x38, data):
                logger.error("Failed to send settings frame")
                return False
            response = self.receive_frame()
            if (
                not response
                or response["function_type"] != 0x38
                or response["data"][0] != 1
            ):
                logger.error(f"Invalid response when setting settings: {response}")
                return False
            logger.info("Settings successfully updated")
            return True
        logger.error("Failed to get current settings")
        return False


if __name__ == "__main__":
    # Test the implementation
    dp100 = DP100()
    try:
        dp100.connect()
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

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        dp100.disconnect()
