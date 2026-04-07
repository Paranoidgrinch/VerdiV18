from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from worker import LaserWorker


DEFAULT_HOST = "192.168.0.7"
DEFAULT_PORT = 103


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Verdi V18 Controller")
        self.resize(860, 760)

        self.worker: Optional[LaserWorker] = None
        self._latest_status: dict = {}

        self._build_ui()
        self._set_controls_enabled(False)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)

        # --------------------------------------------------------------
        # Connection group
        # --------------------------------------------------------------
        connection_group = QtWidgets.QGroupBox("Connection")
        connection_layout = QtWidgets.QGridLayout(connection_group)

        self.host_edit = QtWidgets.QLineEdit(DEFAULT_HOST)
        self.port_edit = QtWidgets.QLineEdit(str(DEFAULT_PORT))
        self.port_edit.setValidator(QtGui.QIntValidator(1, 65535))

        self.start_button = QtWidgets.QPushButton("Connect / Start")
        self.stop_button = QtWidgets.QPushButton("Disconnect")
        self.stop_button.setEnabled(False)

        self.start_button.clicked.connect(self.start_worker)
        self.stop_button.clicked.connect(self.stop_worker)

        connection_layout.addWidget(QtWidgets.QLabel("Host:"), 0, 0)
        connection_layout.addWidget(self.host_edit, 0, 1)
        connection_layout.addWidget(QtWidgets.QLabel("Port:"), 0, 2)
        connection_layout.addWidget(self.port_edit, 0, 3)
        connection_layout.addWidget(self.start_button, 1, 0, 1, 2)
        connection_layout.addWidget(self.stop_button, 1, 2, 1, 2)

        self.connection_label = QtWidgets.QLabel("Not connected")
        self.connection_label.setStyleSheet("font-weight: bold; color: red;")

        self.readiness_label = QtWidgets.QLabel("Not ready")
        self.readiness_label.setStyleSheet("font-weight: bold; color: gray;")

        # --------------------------------------------------------------
        # Status group
        # --------------------------------------------------------------
        status_group = QtWidgets.QGroupBox("Laser status")
        status_layout = QtWidgets.QGridLayout(status_group)

        (
            self.keyswitch_light,
            self.keyswitch_value_label,
        ) = self._create_status_row("Keyswitch")
        (
            self.faults_light,
            self.faults_value_label,
        ) = self._create_status_row("Faults / Interlocks")
        (
            self.laser_light,
            self.laser_value_label,
        ) = self._create_status_row("Laser state")
        (
            self.shutter_light,
            self.shutter_value_label,
        ) = self._create_status_row("Shutter")
        (
            self.lbo_heater_light,
            self.lbo_heater_value_label,
        ) = self._create_status_row("LBO heater")
        (
            self.lbo_servo_light,
            self.lbo_servo_value_label,
        ) = self._create_status_row("LBO servo")
        (
            self.lbo_temp_light,
            self.lbo_temp_value_label,
        ) = self._create_status_row("LBO temperatures")

        status_layout.addWidget(self.keyswitch_light, 0, 0)
        status_layout.addWidget(self.keyswitch_value_label, 0, 1)

        status_layout.addWidget(self.faults_light, 1, 0)
        status_layout.addWidget(self.faults_value_label, 1, 1)

        status_layout.addWidget(self.laser_light, 2, 0)
        status_layout.addWidget(self.laser_value_label, 2, 1)

        status_layout.addWidget(self.shutter_light, 3, 0)
        status_layout.addWidget(self.shutter_value_label, 3, 1)

        status_layout.addWidget(self.lbo_heater_light, 4, 0)
        status_layout.addWidget(self.lbo_heater_value_label, 4, 1)

        status_layout.addWidget(self.lbo_servo_light, 5, 0)
        status_layout.addWidget(self.lbo_servo_value_label, 5, 1)

        status_layout.addWidget(self.lbo_temp_light, 6, 0)
        status_layout.addWidget(self.lbo_temp_value_label, 6, 1)

        # --------------------------------------------------------------
        # Controls group
        # --------------------------------------------------------------
        controls_group = QtWidgets.QGroupBox("Controls")
        controls_layout = QtWidgets.QGridLayout(controls_group)

        self.laser_checkbox = QtWidgets.QCheckBox("Laser ON")
        self.shutter_checkbox = QtWidgets.QCheckBox("Request Shutter OPEN")

        self.laser_checkbox.stateChanged.connect(self.on_laser_checkbox_changed)
        self.shutter_checkbox.stateChanged.connect(self.on_shutter_checkbox_changed)

        self.power_spinbox = QtWidgets.QDoubleSpinBox()
        self.power_spinbox.setRange(0.0, 18.0)
        self.power_spinbox.setDecimals(4)
        self.power_spinbox.setSingleStep(0.1)
        self.power_spinbox.setSuffix(" W")

        self.set_power_button = QtWidgets.QPushButton("Set power")
        self.set_power_button.clicked.connect(self.on_set_power_clicked)

        self.reported_set_power_label = QtWidgets.QLabel("--- W")
        self.measured_output_power_label = QtWidgets.QLabel("--- W")

        controls_layout.addWidget(self.laser_checkbox, 0, 0)
        controls_layout.addWidget(self.shutter_checkbox, 0, 1)

        controls_layout.addWidget(QtWidgets.QLabel("Requested power:"), 1, 0)
        controls_layout.addWidget(self.power_spinbox, 1, 1)
        controls_layout.addWidget(self.set_power_button, 1, 2)

        controls_layout.addWidget(QtWidgets.QLabel("Reported set power (?SP):"), 2, 0)
        controls_layout.addWidget(self.reported_set_power_label, 2, 1)

        controls_layout.addWidget(QtWidgets.QLabel("Measured output power (?P):"), 3, 0)
        controls_layout.addWidget(self.measured_output_power_label, 3, 1)

        # --------------------------------------------------------------
        # Log
        # --------------------------------------------------------------
        self.log_display = QtWidgets.QTextEdit()
        self.log_display.setReadOnly(True)

        # --------------------------------------------------------------
        # Assemble main layout
        # --------------------------------------------------------------
        main_layout.addWidget(connection_group)
        main_layout.addWidget(QtWidgets.QLabel("Connection state:"))
        main_layout.addWidget(self.connection_label)
        main_layout.addWidget(QtWidgets.QLabel("Startup / readiness:"))
        main_layout.addWidget(self.readiness_label)
        main_layout.addWidget(status_group)
        main_layout.addWidget(controls_group)
        main_layout.addWidget(QtWidgets.QLabel("Log"))
        main_layout.addWidget(self.log_display)

    def _create_status_row(self, title: str) -> tuple[QtWidgets.QLabel, QtWidgets.QLabel]:
        light = QtWidgets.QLabel()
        light.setFixedSize(18, 18)
        light.setStyleSheet("background-color: gray; border-radius: 9px;")

        label = QtWidgets.QLabel(f"{title}: unknown")
        label.setWordWrap(True)

        return light, label

    def _set_light_color(self, light: QtWidgets.QLabel, color: str) -> None:
        light.setStyleSheet(f"background-color: {color}; border-radius: 9px;")

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.laser_checkbox.setEnabled(enabled)
        self.shutter_checkbox.setEnabled(enabled)
        self.power_spinbox.setEnabled(enabled)
        self.set_power_button.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Worker control
    # ------------------------------------------------------------------

    def start_worker(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return

        host = self.host_edit.text().strip() or DEFAULT_HOST

        try:
            port = int(self.port_edit.text().strip())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid port", "Please enter a valid port.")
            return

        self.worker = LaserWorker(host=host, port=port, timeout_s=1.0)

        self.worker.connectionStateChanged.connect(self.on_connection_state_changed)
        self.worker.readinessChanged.connect(self.on_readiness_changed)
        self.worker.statusUpdated.connect(self.on_status_updated)
        self.worker.logMessage.connect(self.log)

        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.connection_label.setText("Connecting...")
        self.connection_label.setStyleSheet("font-weight: bold; color: black;")
        self.readiness_label.setText("Checking startup conditions...")
        self.readiness_label.setStyleSheet("font-weight: bold; color: orange;")
        self._set_controls_enabled(False)

    def stop_worker(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait()
            self.worker = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        self.connection_label.setText("Disconnected")
        self.connection_label.setStyleSheet("font-weight: bold; color: red;")
        self.readiness_label.setText("Not ready")
        self.readiness_label.setStyleSheet("font-weight: bold; color: gray;")

        self._set_controls_enabled(False)
        self._reset_status_display()

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def on_connection_state_changed(self, connected: bool, message: str) -> None:
        self.connection_label.setText(message)

        if connected:
            self.connection_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.connection_label.setStyleSheet("font-weight: bold; color: red;")
            self._set_controls_enabled(False)
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def on_readiness_changed(self, ready: bool, message: str) -> None:
        self.readiness_label.setText(message)

        if ready:
            self.readiness_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.readiness_label.setStyleSheet("font-weight: bold; color: orange;")

        self._set_controls_enabled(ready)

    def on_status_updated(self, status: dict) -> None:
        self._latest_status.update(status)
        self._update_status_display()

    # ------------------------------------------------------------------
    # UI -> Worker
    # ------------------------------------------------------------------

    def on_laser_checkbox_changed(self, state: int) -> None:
        if self.worker is None:
            return
        self.worker.request_laser_on(state == QtCore.Qt.Checked)

    def on_shutter_checkbox_changed(self, state: int) -> None:
        if self.worker is None:
            return
        self.worker.request_shutter_open(state == QtCore.Qt.Checked)

    def on_set_power_clicked(self) -> None:
        if self.worker is None:
            return
        self.worker.request_set_power(self.power_spinbox.value())

    # ------------------------------------------------------------------
    # Display update
    # ------------------------------------------------------------------

    def _update_status_display(self) -> None:
        status = self._latest_status

        # Keyswitch
        keyswitch = status.get("keyswitch_enabled")
        if keyswitch is True:
            self._set_light_color(self.keyswitch_light, "green")
            self.keyswitch_value_label.setText("Keyswitch: ON")
        elif keyswitch is False:
            self._set_light_color(self.keyswitch_light, "red")
            self.keyswitch_value_label.setText("Keyswitch: OFF")
        else:
            self._set_light_color(self.keyswitch_light, "gray")
            self.keyswitch_value_label.setText("Keyswitch: unknown")

        # Faults
        fault_codes = status.get("fault_codes")
        fault_text = status.get("fault_text")
        fault_descriptions = status.get("fault_descriptions", [])

        if fault_codes is None:
            self._set_light_color(self.faults_light, "gray")
            self.faults_value_label.setText(f"Faults / Interlocks: {fault_text}")
        elif len(fault_codes) == 0:
            self._set_light_color(self.faults_light, "green")
            self.faults_value_label.setText("Faults / Interlocks: System OK")
        else:
            self._set_light_color(self.faults_light, "red")
            pretty_faults = " | ".join(fault_descriptions) if fault_descriptions else fault_text
            self.faults_value_label.setText(f"Faults / Interlocks: {pretty_faults}")

        # Laser state
        laser_state_code = status.get("laser_state_code")
        laser_state_text = status.get("laser_state_text", "Unknown")

        if laser_state_code == 1:
            self._set_light_color(self.laser_light, "green")
        elif laser_state_code == 2:
            self._set_light_color(self.laser_light, "red")
        elif laser_state_code == 0:
            self._set_light_color(self.laser_light, "gray")
        else:
            self._set_light_color(self.laser_light, "gray")

        self.laser_value_label.setText(f"Laser state: {laser_state_text}")

        # Checkbox mit echtem Status synchronisieren, aber ohne Rücksignal
        if laser_state_code in (0, 1, 2):
            blocker = QtCore.QSignalBlocker(self.laser_checkbox)
            self.laser_checkbox.setChecked(laser_state_code == 1)
            del blocker

        # Shutter
        shutter_open = status.get("shutter_open")
        if shutter_open is True:
            self._set_light_color(self.shutter_light, "green")
            self.shutter_value_label.setText("Shutter: OPEN")
        elif shutter_open is False:
            self._set_light_color(self.shutter_light, "gray")
            self.shutter_value_label.setText("Shutter: CLOSED")
        else:
            self._set_light_color(self.shutter_light, "gray")
            self.shutter_value_label.setText("Shutter: unknown")

        if shutter_open is not None:
            blocker = QtCore.QSignalBlocker(self.shutter_checkbox)
            self.shutter_checkbox.setChecked(shutter_open)
            del blocker

        # LBO heater
        lbo_heater_text = status.get("lbo_heater_status_text", "Unknown")
        if lbo_heater_text == "HEATING":
            self._set_light_color(self.lbo_heater_light, "orange")
        elif lbo_heater_text == "COOL DOWN":
            self._set_light_color(self.lbo_heater_light, "green")
        else:
            self._set_light_color(self.lbo_heater_light, "gray")
        self.lbo_heater_value_label.setText(f"LBO heater: {lbo_heater_text}")

        # LBO servo
        lbo_servo_text = status.get("lbo_servo_status_text", "Unknown")
        if lbo_servo_text == "LOCKED":
            self._set_light_color(self.lbo_servo_light, "green")
        elif lbo_servo_text == "FAULT":
            self._set_light_color(self.lbo_servo_light, "red")
        elif lbo_servo_text == "Unknown":
            self._set_light_color(self.lbo_servo_light, "gray")
        else:
            self._set_light_color(self.lbo_servo_light, "orange")
        self.lbo_servo_value_label.setText(f"LBO servo: {lbo_servo_text}")

        # LBO temperatures
        lbo_set_temp = status.get("lbo_set_temp_c")
        lbo_temp = status.get("lbo_temp_c")

        if lbo_set_temp is not None and lbo_temp is not None:
            diff = lbo_temp - lbo_set_temp
            self._set_light_color(self.lbo_temp_light, "green" if abs(diff) <= 5.0 else "orange")
            self.lbo_temp_value_label.setText(
                f"LBO temperatures: set = {lbo_set_temp:.2f} °C, "
                f"measured = {lbo_temp:.2f} °C, ΔT = {diff:+.2f} °C"
            )
        else:
            self._set_light_color(self.lbo_temp_light, "gray")
            self.lbo_temp_value_label.setText("LBO temperatures: unknown")

        # Power
        set_power = status.get("set_power_w")
        output_power = status.get("output_power_w")

        if set_power is None:
            self.reported_set_power_label.setText("--- W")
        else:
            self.reported_set_power_label.setText(f"{set_power:.4f} W")

        if output_power is None:
            self.measured_output_power_label.setText("--- W")
        else:
            self.measured_output_power_label.setText(f"{output_power:.4f} W")

    def _reset_status_display(self) -> None:
        self._latest_status.clear()

        for light in (
            self.keyswitch_light,
            self.faults_light,
            self.laser_light,
            self.shutter_light,
            self.lbo_heater_light,
            self.lbo_servo_light,
            self.lbo_temp_light,
        ):
            self._set_light_color(light, "gray")

        self.keyswitch_value_label.setText("Keyswitch: unknown")
        self.faults_value_label.setText("Faults / Interlocks: unknown")
        self.laser_value_label.setText("Laser state: unknown")
        self.shutter_value_label.setText("Shutter: unknown")
        self.lbo_heater_value_label.setText("LBO heater: unknown")
        self.lbo_servo_value_label.setText("LBO servo: unknown")
        self.lbo_temp_value_label.setText("LBO temperatures: unknown")

        self.reported_set_power_label.setText("--- W")
        self.measured_output_power_label.setText("--- W")

        blocker1 = QtCore.QSignalBlocker(self.laser_checkbox)
        blocker2 = QtCore.QSignalBlocker(self.shutter_checkbox)
        self.laser_checkbox.setChecked(False)
        self.shutter_checkbox.setChecked(False)
        del blocker1
        del blocker2

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.stop_worker()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())