import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QGroupBox,
    QGridLayout,
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QIcon
from dp100 import DP100
import logging

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dp100 = DP100()
        self.init_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_info)
        self.update_timer.start(1000)  # Update every second
        QTimer.singleShot(0, self.connect_on_start)  # Connect on start

    def init_ui(self):
        self.setWindowTitle("DP100 Power Supply Controller")
        self.setGeometry(100, 100, 600, 400)
        self.setWindowIcon(QIcon("icon.png"))  # Add an icon file to your project

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Connection status and button
        connection_layout = QHBoxLayout()
        self.connection_status = QLabel("Not Connected")
        self.connection_status.setStyleSheet("color: red;")
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)
        connection_layout.addWidget(self.connection_status)
        connection_layout.addWidget(self.connect_button)
        main_layout.addLayout(connection_layout)

        # Output readings
        readings_group = QGroupBox("Output Readings")
        readings_layout = QGridLayout()
        self.vin_label = QLabel("Input Voltage: N/A")
        self.voltage_label = QLabel("Output Voltage: N/A")
        self.current_label = QLabel("Output Current: N/A")
        self.power_label = QLabel("Power: N/A")
        self.temp_label = QLabel("Temperature: N/A")
        self.dc_5v_label = QLabel("5V DC: N/A")
        readings_layout.addWidget(self.vin_label, 0, 0)
        readings_layout.addWidget(self.voltage_label, 1, 0)
        readings_layout.addWidget(self.current_label, 2, 0)
        readings_layout.addWidget(self.power_label, 0, 1)
        readings_layout.addWidget(self.temp_label, 1, 1)
        readings_layout.addWidget(self.dc_5v_label, 2, 1)
        readings_group.setLayout(readings_layout)
        main_layout.addWidget(readings_group)

        # Output control
        control_group = QGroupBox("Output Control")
        control_layout = QGridLayout()
        self.set_voltage_input = QLineEdit()
        self.set_voltage_input.setPlaceholderText("Set Voltage (V)")
        self.set_current_input = QLineEdit()
        self.set_current_input.setPlaceholderText("Set Current (A)")
        self.set_output_button = QPushButton("Set Output")
        self.set_output_button.clicked.connect(self.set_output)
        control_layout.addWidget(QLabel("Voltage:"), 0, 0)
        control_layout.addWidget(self.set_voltage_input, 0, 1)
        control_layout.addWidget(QLabel("Current:"), 1, 0)
        control_layout.addWidget(self.set_current_input, 1, 1)
        control_layout.addWidget(self.set_output_button, 2, 0, 1, 2)
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # Status
        self.status_label = QLabel("Status: N/A")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.status_label)

    def connect_on_start(self):
        self.toggle_connection()

    def toggle_connection(self):
        if self.dp100.device:
            self.dp100.disconnect()
            self.connect_button.setText("Connect")
            self.connection_status.setText("Not Connected")
            self.connection_status.setStyleSheet("color: red;")
        else:
            try:
                self.dp100.connect()
                self.connect_button.setText("Disconnect")
                self.connection_status.setText("Connected")
                self.connection_status.setStyleSheet("color: green;")
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.connection_status.setText("Connection Failed")
                self.connection_status.setStyleSheet("color: red;")

    def update_info(self):
        if self.dp100.device:
            try:
                info = self.dp100.get_basic_info()
                if info:
                    logger.debug(f"Received info: {info}")
                    self.vin_label.setText(f"Input Voltage: {info['vin'] / 100:.2f} V")
                    self.voltage_label.setText(f"Output Voltage: {info['vout']:.3f} V")
                    self.current_label.setText(f"Output Current: {info['iout']:.3f} A")
                    self.power_label.setText(f"Power: {info['power']:.2f} W")
                    self.temp_label.setText(
                        f"Temperature: {info['temp1']:.1f}°C / {info['temp2']:.1f}°C"
                    )
                    self.dc_5v_label.setText(f"5V DC: {info['dc_5v']:.3f} V")

                    # Interpret status bits
                    status = info["status"]
                    status_str = f"Status: {status:016b}\n"
                    status_str += f"Output: {'ON' if status & 0x0001 else 'OFF'}\n"
                    status_str += f"Mode: {'CC' if status & 0x0002 else 'CV'}\n"
                    status_str += (
                        f"OVP: {'Triggered' if status & 0x0004 else 'Normal'}\n"
                    )
                    status_str += (
                        f"OCP: {'Triggered' if status & 0x0008 else 'Normal'}\n"
                    )
                    status_str += (
                        f"OPP: {'Triggered' if status & 0x0010 else 'Normal'}\n"
                    )
                    status_str += f"OTP: {'Triggered' if status & 0x0020 else 'Normal'}"

                    self.status_label.setText(status_str)
                else:
                    logger.warning("Failed to get basic info")
            except Exception as e:
                logger.error(f"Error updating info: {e}")

    def set_output(self):
        if self.dp100.device:
            try:
                voltage = float(self.set_voltage_input.text())
                current = float(self.set_current_input.text())
                success = self.dp100.set_output(voltage, current)
                if success:
                    logger.info("Output set successfully")
                else:
                    logger.warning("Failed to set output")
            except ValueError:
                logger.error("Invalid input")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for a modern look
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
