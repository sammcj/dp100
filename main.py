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
    QComboBox,
    QTabWidget,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QMessageBox,
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon
from dp100 import DP100
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def watchdog_timeout(self):
        logger.error("Watchdog timer expired, operation took too long")
        self.dp100.abort_operation()
        QMessageBox.critical(
            self, "Error", "Operation timed out. The device may be unresponsive."
        )

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

        # Preset tab
        preset_tab = QWidget()
        preset_layout = QVBoxLayout(preset_tab)
        tabs.addTab(preset_tab, "Presets")

        # Preset selection
        preset_select_layout = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([f"Preset {i}" for i in range(10)])
        self.load_preset_button = QPushButton("Load Preset")
        self.load_preset_button.clicked.connect(self.load_preset)
        preset_select_layout.addWidget(self.preset_combo)
        preset_select_layout.addWidget(self.load_preset_button)
        preset_layout.addLayout(preset_select_layout)

        # Preset settings
        preset_settings_group = QGroupBox("Preset Settings")
        preset_settings_layout = QGridLayout()
        self.preset_voltage = QDoubleSpinBox()
        self.preset_voltage.setRange(0, 30)
        self.preset_voltage.setDecimals(3)
        self.preset_voltage.setSuffix(" V")
        self.preset_current = QDoubleSpinBox()
        self.preset_current.setRange(0, 5)
        self.preset_current.setDecimals(3)
        self.preset_current.setSuffix(" A")
        self.preset_ovp = QDoubleSpinBox()
        self.preset_ovp.setRange(0, 30)
        self.preset_ovp.setDecimals(3)
        self.preset_ovp.setSuffix(" V")
        self.preset_ocp = QDoubleSpinBox()
        self.preset_ocp.setRange(0, 5)
        self.preset_ocp.setDecimals(3)
        self.preset_ocp.setSuffix(" A")
        self.save_preset_button = QPushButton("Save Preset")
        self.save_preset_button.clicked.connect(self.save_preset)
        preset_settings_layout.addWidget(QLabel("Voltage:"), 0, 0)
        preset_settings_layout.addWidget(self.preset_voltage, 0, 1)
        preset_settings_layout.addWidget(QLabel("Current:"), 1, 0)
        preset_settings_layout.addWidget(self.preset_current, 1, 1)
        preset_settings_layout.addWidget(QLabel("OVP:"), 2, 0)
        preset_settings_layout.addWidget(self.preset_ovp, 2, 1)
        preset_settings_layout.addWidget(QLabel("OCP:"), 3, 0)
        preset_settings_layout.addWidget(self.preset_ocp, 3, 1)
        preset_settings_layout.addWidget(self.save_preset_button, 4, 0, 1, 2)
        preset_settings_group.setLayout(preset_settings_layout)
        preset_layout.addWidget(preset_settings_group)

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
                self.update_device_info()
                self.update_settings()
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.connection_status.setText("Connection Failed")
                self.connection_status.setStyleSheet("color: red;")
                QMessageBox.critical(self, "Connection Error", str(e))

    def update_info(self):
        if self.dp100.device:
            try:
                info = self.dp100.get_basic_info()
                if info:
                    self.vin_label.setText(f"Input Voltage: {info['vin']:.2f} V")
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
                voltage = self.set_voltage_input.value()
                current = self.set_current_input.value()

                self.watchdog_timer = QTimer(self)
                self.watchdog_timer.setSingleShot(True)
                self.watchdog_timer.timeout.connect(self.watchdog_timeout)
                self.watchdog_timer.start(15000)  # 15 second timeout

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
                        self, "Error", "Failed to set output. Please try again."
                    )
            except Exception as e:
                self.watchdog_timer.stop()
                logger.error(f"Error setting output: {e}")
                QMessageBox.critical(
                    self, "Error", f"An error occurred while setting output: {str(e)}"
                )

    def watchdog_timeout(self):
        logger.error("Watchdog timer expired, operation took too long")
        QMessageBox.critical(
            self, "Error", "Operation timed out. The device may be unresponsive."
        )
        # You might want to implement a way to cancel the ongoing operation here
        # For example, you could set a flag in the DP100 class to abort the current operation

    def update_device_info(self):
        if self.dp100.device:
            try:
                info = self.dp100.get_device_info()
                if info:
                    info_str = f"Device: {info['device_name']}\n"
                    info_str += f"Hardware: {info['hardware_version']}\n"
                    info_str += f"Software: {info['software_version']}\n"
                    info_str += f"Serial: {info['serial_number']}"
                    self.device_info_label.setText(info_str)
                else:
                    logger.warning("Failed to get device info")
            except Exception as e:
                logger.error(f"Error updating device info: {e}")

    def update_output_state(self):
        if self.dp100.device:
            try:
                state = self.dp100.get_output_state()
                if state:
                    status = "ON" if state["output_on"] else "OFF"
                    self.status_label.setText(
                        f"Output: {status}, Voltage: {state['voltage']:.3f}V, Current: {state['current']:.3f}A"
                    )
                else:
                    self.status_label.setText("Failed to get output state")
            except Exception as e:
                logger.error(f"Error updating output state: {e}")
                self.status_label.setText(f"Error updating output state: {str(e)}")

    def load_preset(self):
        if self.dp100.device:
            try:
                preset_index = self.preset_combo.currentIndex()
                preset = self.dp100.get_preset(preset_index)
                if preset:
                    self.preset_voltage.setValue(preset["v_set"])
                    self.preset_current.setValue(preset["i_set"])
                    self.preset_ovp.setValue(preset["ovp"])
                    self.preset_ocp.setValue(preset["ocp"])
                    logger.info(f"Loaded preset {preset_index}")
                else:
                    logger.warning(f"Failed to load preset {preset_index}")
            except Exception as e:
                logger.error(f"Error loading preset: {e}")

    def save_preset(self):
        if self.dp100.device:
            try:
                preset_index = self.preset_combo.currentIndex()
                v_set = self.preset_voltage.value()
                i_set = self.preset_current.value()
                ovp = self.preset_ovp.value()
                ocp = self.preset_ocp.value()
                success = self.dp100.set_preset(preset_index, v_set, i_set, ovp, ocp)
                if success:
                    logger.info(f"Saved preset {preset_index}")
                else:
                    logger.warning(f"Failed to save preset {preset_index}")
            except Exception as e:
                logger.error(f"Error saving preset: {e}")

    def update_settings(self):
        if self.dp100.device:
            try:
                settings = self.dp100.get_settings()
                if settings:
                    self.backlight_spinbox.setValue(settings["backlight"])
                    self.volume_spinbox.setValue(settings["key_sound"])
                    self.opp_spinbox.setValue(settings["over_power_protection"])
                    self.otp_spinbox.setValue(settings["over_temperature_protection"])
                    self.reverse_protect_checkbox.setChecked(
                        settings["reverse_protection"]
                    )
                    self.auto_output_checkbox.setChecked(
                        settings["power_on_state"] == 1
                    )
                else:
                    logger.warning("Failed to get settings")
            except Exception as e:
                logger.error(f"Error updating settings: {e}")

    def save_settings(self):
        if self.dp100.device:
            try:
                backlight = self.backlight_spinbox.value()
                volume = self.volume_spinbox.value()
                opp = self.opp_spinbox.value()
                otp = self.otp_spinbox.value()
                reverse_protect = self.reverse_protect_checkbox.isChecked()
                auto_output = self.auto_output_checkbox.isChecked()
                success = self.dp100.set_settings(
                    backlight=backlight,
                    volume=volume,
                    opp=opp,
                    otp=otp,
                    reverse_protect=reverse_protect,
                    auto_output=auto_output,
                )
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

    def update_device_info(self):
        if self.dp100.device:
            try:
                info = self.dp100.get_device_info()
                if info:
                    info_str = f"Device Name: {info['device_name']}\n"
                    info_str += f"Hardware Version: {info['hardware_version']}\n"
                    info_str += f"Application Version: {info['application_version']}\n"
                    info_str += f"Serial Number: {info['device_SN']}\n"
                    info_str += f"Status: {info['device_status']}"
                    self.device_info_label.setText(info_str)
                    logger.info("Device info updated")
                else:
                    logger.warning("Failed to get device info")
            except Exception as e:
                logger.error(f"Error updating device info: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for a modern look
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
