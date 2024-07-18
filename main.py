import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QGroupBox,
    QGridLayout,
    QTabWidget,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QMessageBox,
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QIcon
from dp100 import DP100
import logging
import time

logging.basicConfig(level=logging.DEBUG)
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
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon("icon.png"))

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

        # Tabs
        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # Output control tab
        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        tabs.addTab(output_tab, "Output Control")

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
        output_layout.addWidget(readings_group)

        # Output control
        control_group = QGroupBox("Output Control")
        control_layout = QGridLayout()
        self.set_voltage_input = QDoubleSpinBox()
        self.set_voltage_input.setRange(0, 30)
        self.set_voltage_input.setDecimals(3)
        self.set_voltage_input.setSuffix(" V")
        self.set_current_input = QDoubleSpinBox()
        self.set_current_input.setRange(0, 5)
        self.set_current_input.setDecimals(3)
        self.set_current_input.setSuffix(" A")
        self.set_output_button = QPushButton("Set Output")
        self.set_output_button.clicked.connect(self.set_output)
        control_layout.addWidget(QLabel("Voltage:"), 0, 0)
        control_layout.addWidget(self.set_voltage_input, 0, 1)
        control_layout.addWidget(QLabel("Current:"), 1, 0)
        control_layout.addWidget(self.set_current_input, 1, 1)
        control_layout.addWidget(self.set_output_button, 2, 0, 1, 2)
        control_group.setLayout(control_layout)
        output_layout.addWidget(control_group)

        # Settings tab
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        tabs.addTab(settings_tab, "Settings")

        # System settings
        system_settings_group = QGroupBox("System Settings")
        system_settings_layout = QGridLayout()
        self.backlight_spinbox = QSpinBox()
        self.backlight_spinbox.setRange(0, 4)
        self.volume_spinbox = QSpinBox()
        self.volume_spinbox.setRange(0, 4)
        self.opp_spinbox = QDoubleSpinBox()
        self.opp_spinbox.setRange(0, 105)
        self.opp_spinbox.setSuffix(" W")
        self.otp_spinbox = QSpinBox()
        self.otp_spinbox.setRange(50, 80)
        self.otp_spinbox.setSuffix(" °C")
        self.reverse_protect_checkbox = QCheckBox("Reverse Polarity Protection")
        self.auto_output_checkbox = QCheckBox("Auto Output on Power On")
        self.save_settings_button = QPushButton("Save Settings")
        self.save_settings_button.clicked.connect(self.save_settings)
        system_settings_layout.addWidget(QLabel("Backlight:"), 0, 0)
        system_settings_layout.addWidget(self.backlight_spinbox, 0, 1)
        system_settings_layout.addWidget(QLabel("Volume:"), 1, 0)
        system_settings_layout.addWidget(self.volume_spinbox, 1, 1)
        system_settings_layout.addWidget(QLabel("OPP:"), 2, 0)
        system_settings_layout.addWidget(self.opp_spinbox, 2, 1)
        system_settings_layout.addWidget(QLabel("OTP:"), 3, 0)
        system_settings_layout.addWidget(self.otp_spinbox, 3, 1)
        system_settings_layout.addWidget(self.reverse_protect_checkbox, 4, 0, 1, 2)
        system_settings_layout.addWidget(self.auto_output_checkbox, 5, 0, 1, 2)
        system_settings_layout.addWidget(self.save_settings_button, 6, 0, 1, 2)
        system_settings_group.setLayout(system_settings_layout)
        settings_layout.addWidget(system_settings_group)

        # Device info
        self.device_info_label = QLabel()
        settings_layout.addWidget(self.device_info_label)

        # Status
        self.status_label = QLabel("Status: N/A")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.status_label)

    def connect_on_start(self):
        if self.dp100.connect():
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: green;")
            self.update_device_info()
        else:
            self.connection_status.setText("Connection Failed")
            self.connection_status.setStyleSheet("color: red;")

    def toggle_connection(self):
        if self.dp100.device:
            self.dp100.disconnect()
            self.connect_button.setText("Connect")
            self.connection_status.setText("Not Connected")
            self.connection_status.setStyleSheet("color: red;")
        else:
            if self.dp100.connect():
                self.connect_button.setText("Disconnect")
                self.connection_status.setText("Connected")
                self.connection_status.setStyleSheet("color: green;")
                self.update_device_info()
                self.update_settings()
            else:
                self.connection_status.setText("Connection Failed")
                self.connection_status.setStyleSheet("color: red;")
                QMessageBox.critical(
                    self, "Connection Error", "Failed to connect to the device."
                )

    def update_info(self):
        if self.dp100.device:
            info = self.dp100.get_basic_info()
            if info:
                self.vin_label.setText(f"Input Voltage: {info['vin']:.2f} V")
                self.voltage_label.setText(f"Output Voltage: {info['vout']:.3f} V")
                self.current_label.setText(f"Output Current: {info['iout']:.3f} A")
                self.power_label.setText(f"Power: {info['vout'] * info['iout']:.2f} W")
                self.temp_label.setText(
                    f"Temperature: {info['temp1']:.1f}°C / {info['temp2']:.1f}°C"
                )
                self.dc_5v_label.setText(f"5V DC: {info['dc_5v']:.3f} V")

                status_str = f"Status: {info['work_st']:08b}\n"
                status_str += f"Output: {'ON' if info['work_st'] & 0x01 else 'OFF'}\n"
                status_str += f"Mode: {'CC' if info['work_st'] & 0x02 else 'CV'}\n"
                status_str += (
                    f"OVP: {'Triggered' if info['work_st'] & 0x04 else 'Normal'}\n"
                )
                status_str += (
                    f"OCP: {'Triggered' if info['work_st'] & 0x08 else 'Normal'}\n"
                )
                status_str += (
                    f"OPP: {'Triggered' if info['work_st'] & 0x10 else 'Normal'}\n"
                )
                status_str += (
                    f"OTP: {'Triggered' if info['work_st'] & 0x20 else 'Normal'}"
                )
                self.status_label.setText(status_str)

    def set_output(self):
        if self.dp100.device:
            try:
                voltage = self.set_voltage_input.value()
                current = self.set_current_input.value()

                self.watchdog_timer = QTimer(self)
                self.watchdog_timer.setSingleShot(True)
                self.watchdog_timer.timeout.connect(self.watchdog_timeout)
                self.watchdog_timer.start(10000)  # 10 second timeout

                success = self.dp100.set_output(voltage, current)

                self.watchdog_timer.stop()

                if success:
                    logger.info(f"Output set successfully: {voltage}V, {current}A")
                    QMessageBox.information(
                        self, "Success", f"Output set to {voltage}V, {current}A"
                    )
                else:
                    logger.warning("Failed to set output")
                    QMessageBox.warning(
                        self,
                        "Error",
                        "Failed to set output. Please check the logs for more details.",
                    )
            except Exception as e:
                self.watchdog_timer.stop()
                logger.error(f"Error setting output: {e}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Error",
                    f"An error occurred while setting output: {str(e)}\n\nPlease check the logs for more details.",
                )

    def watchdog_timeout(self):
        logger.error("Watchdog timer expired, operation took too long")
        self.dp100.abort_operation()
        QMessageBox.critical(
            self, "Error", "Operation timed out. The device may be unresponsive."
        )

    def update_device_info(self):
        info = self.dp100.get_device_info()
        if info:
            info_str = f"Device: {info['dev_type']}\n"
            info_str += f"Hardware: {info['hdw_ver']}\n"
            info_str += f"Software: {info['app_ver']}\n"
            info_str += f"Bootloader: {info['boot_ver']}\n"
            info_str += f"Date: {info['year']}-{info['month']:02d}-{info['day']:02d}"
            self.device_info_label.setText(info_str)

    def update_settings(self):
        if self.dp100.device:
            settings = self.dp100.get_settings()
            if settings:
                self.backlight_spinbox.setValue(settings["backlight"])
                self.volume_spinbox.setValue(settings["key_sound"])
                self.opp_spinbox.setValue(settings["over_power_protection"])
                self.otp_spinbox.setValue(settings["over_temperature_protection"])
                self.reverse_protect_checkbox.setChecked(settings["reverse_protection"])
                self.auto_output_checkbox.setChecked(settings["power_on_state"] == 1)

    def save_settings(self):
        if self.dp100.device:
            try:
                settings = {
                    "backlight": self.backlight_spinbox.value(),
                    "key_sound": self.volume_spinbox.value(),
                    "over_power_protection": self.opp_spinbox.value(),
                    "over_temperature_protection": self.otp_spinbox.value(),
                    "reverse_protection": self.reverse_protect_checkbox.isChecked(),
                    "power_on_state": 1 if self.auto_output_checkbox.isChecked() else 0,
                }
                success = self.dp100.set_settings(settings)
                if success:
                    logger.info("Settings saved successfully")
                    QMessageBox.information(
                        self, "Success", "Settings saved successfully"
                    )
                else:
                    logger.warning("Failed to save settings")
                    QMessageBox.warning(
                        self, "Error", "Failed to save settings. Please try again."
                    )
            except Exception as e:
                logger.error(f"Error saving settings: {e}")
                QMessageBox.critical(
                    self, "Error", f"An error occurred while saving settings: {str(e)}"
                )
        else:
            QMessageBox.warning(
                self, "Not Connected", "Please connect to the device first."
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for a modern look
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
