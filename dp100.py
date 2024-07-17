import hid
import struct
import logging

logging.basicConfig(
    level=logging.DEBUG
)  # Set to INFO for reduced logging, or DEBUG to have raw data printed to the console
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

    def connect(self):
        self.device = hid.device()
        self.device.open(DP100_USB_INFO["vendor_id"], DP100_USB_INFO["product_id"])

    def disconnect(self):
        if self.device:
            self.device.close()

    def send_frame(self, function_type, data):
        # self.device.set_nonblocking(0) # Yet to be tested
        frame = struct.pack("<BBBB", 251, function_type, 0, len(data)) + data
        checksum = crc16(frame)
        frame += struct.pack("<H", checksum)
        logger.debug(f"Sending frame: {frame.hex()}")
        self.device.write(frame)  # type: ignore

    def receive_frame(self):
        response = self.device.read(64)  # type: ignore
        response_bytes = bytes(response)  # Convert list of integers to bytes
        logger.debug(f"Received raw data: {response_bytes.hex()}")
        if len(response) < 6:
            return None
        data_len = response[3]
        data = bytes(response[4 : 4 + data_len])
        logger.debug(f"Extracted data: {data.hex()}")
        return {"function_type": response[1], "data": data}

    def get_basic_info(self):
        self.send_frame(0x30, b"")
        response = self.receive_frame()
        if response and response["function_type"] == 0x30:
            data = response["data"]
            logger.debug(f"Basic info data: {data.hex()}")
            if len(data) == 16:
                # Unpack the 16 bytes of data
                unpacked = struct.unpack("<HHHHHHHH", data)
                return {
                    "vin": unpacked[0],  # This is already in units of 0.01V
                    "vout": unpacked[1] / 1000,  # Divide by 1000 to get volts
                    "iout": unpacked[2] / 1000,  # Divide by 1000 to get amps
                    "power": unpacked[3] / 100,  # Divide by 100 to get watts
                    "temp1": unpacked[4] / 10,  # Divide by 10 to get degrees Celsius
                    "temp2": unpacked[5] / 10,  # Divide by 10 to get degrees Celsius
                    "dc_5v": unpacked[6] / 1000,  # Divide by 1000 to get volts
                    "status": unpacked[7],
                }
            else:
                logger.warning(f"Unexpected data length: {len(data)}")
                return None
        return None

    def set_output(self, voltage, current):
        # TODO: Set write protection to 0
        # TODO: - might need to pause reading while we set the output

        # Set the output voltage and current
        data = struct.pack(
            "<BHHHH", 0x20, 1, int(voltage * 1000), int(current * 1000), 0xFFFF
        )
        self.send_frame(0x35, data)
        response = self.receive_frame()
        return response and response["data"][0] == 1

    # Add more methods as needed
