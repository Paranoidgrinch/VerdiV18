from __future__ import annotations

import threading
import time
from typing import Optional

from PyQt5 import QtCore

from verdi_protocol import VerdiConnection
from verdi_controller import VerdiController


class LaserWorker(QtCore.QThread):
    """
    Einziger Thread, der mit dem Laser spricht.

    Aufgaben:
    - Verbindung aufbauen
    - Startup-Bedingungen überwachen:
        * Keyswitch muss ON sein
        * Faults müssen weg sein
        * Sonderfall Fault 5: auf LBO-Lock warten
    - danach:
        * Benutzerkommandos seriell ausführen
        * Status regelmäßig pollen

    Wichtig:
    Die GUI fasst den Socket nie direkt an.
    """

    connectionStateChanged = QtCore.pyqtSignal(bool, str)
    readinessChanged = QtCore.pyqtSignal(bool, str)
    statusUpdated = QtCore.pyqtSignal(dict)
    logMessage = QtCore.pyqtSignal(str)

    def __init__(
        self,
        host: str,
        port: int,
        timeout_s: float = 1.0,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)

        self.host = host
        self.port = port
        self.timeout_s = timeout_s

        self._running = False
        self._lock = threading.Lock()

        self._connection: Optional[VerdiConnection] = None
        self._controller: Optional[VerdiController] = None

        self._pending_laser_command: Optional[bool] = None
        self._pending_shutter_command: Optional[bool] = None
        self._pending_power_w: Optional[float] = None

        # Um readinessChanged nicht ständig identisch zu emittieren
        self._last_ready_tuple: Optional[tuple[bool, str]] = None

        #safety feature
        self._ready_streak = 0
        self._required_ready_streak = 3

    # ------------------------------------------------------------------
    # Öffentliche, threadsichere GUI-Aufrufe
    # ------------------------------------------------------------------

    def stop(self) -> None:
        self._running = False

    def request_laser_on(self, on: bool) -> None:
        with self._lock:
            self._pending_laser_command = bool(on)

    def request_shutter_open(self, open_: bool) -> None:
        with self._lock:
            self._pending_shutter_command = bool(open_)

    def request_set_power(self, watts: float) -> None:
        with self._lock:
            self._pending_power_w = max(0.0, float(watts))

    # ------------------------------------------------------------------
    # Thread-Hauptschleife
    # ------------------------------------------------------------------

    def run(self) -> None:
        self._running = True

        try:
            self._connection = VerdiConnection(
                host=self.host,
                port=self.port,
                timeout=self.timeout_s,
            )
            self._controller = VerdiController(self._connection)

            self._connection.connect()
            self.connectionStateChanged.emit(True, f"Connected to {self.host}:{self.port}")
            self.logMessage.emit(f"Connected to laser at {self.host}:{self.port}")

        except Exception as exc:
            self.connectionStateChanged.emit(False, f"Connection failed: {exc}")
            self.logMessage.emit(f"Connection failed: {exc}")
            self._safe_close()
            return

        ready_for_operation = False
        last_status_poll = 0.0

        while self._running:
            if self._controller is None:
                break

            # ----------------------------------------------------------
            # Phase 1: Startup-Bedingungen überwachen
            # ----------------------------------------------------------
            if not ready_for_operation:
                status = self._controller.read_basic_status()
                self.statusUpdated.emit(status)

                candidate_ready, message = self._evaluate_readiness(status)

                if candidate_ready:
                    self._ready_streak += 1
                else:
                    self._ready_streak = 0

                really_ready = self._ready_streak >= self._required_ready_streak
                display_message = "Ready for operation" if really_ready else message

                self._emit_readiness_if_changed(really_ready, display_message)

                if really_ready:
                    self.logMessage.emit("Startup conditions satisfied. Controls enabled.")
                    ready_for_operation = True
                else:
                    time.sleep(1.0)
                    continue

            # ----------------------------------------------------------
            # Phase 2: Benutzerkommandos seriell abarbeiten
            # ----------------------------------------------------------
            self._apply_pending_commands()

            # ----------------------------------------------------------
            # Phase 3: Regelmäßiges Status-Polling
            # ----------------------------------------------------------
            now = time.time()
            if now - last_status_poll >= 1.0:
                status = self._controller.read_basic_status()
                self.statusUpdated.emit(status)

                previous_ready = ready_for_operation

                still_ready, message = self._evaluate_readiness(status)
                self._emit_readiness_if_changed(still_ready, message)

                if previous_ready and not still_ready:
                    self.logMessage.emit(f"Readiness lost: {message}")

                ready_for_operation = still_ready
                last_status_poll = now

            time.sleep(0.1)

        self._safe_close()
        self.connectionStateChanged.emit(False, "Disconnected")
        self.logMessage.emit("Disconnected from laser.")

    # ------------------------------------------------------------------
    # Readiness / Startup
    # ------------------------------------------------------------------

    def _evaluate_readiness(self, status: dict) -> tuple[bool, str]:
        """
        Entscheidet, ob die GUI freigegeben werden darf.

        Regeln:
        - Keyswitch muss ON sein
        - Faults müssen leer sein
        - Falls nur Fault 5 aktiv ist: Wartephase für LBO-Lock
        """
        keyswitch = status.get("keyswitch_enabled")
        fault_codes = status.get("fault_codes")
        lbo_set_temp = status.get("lbo_set_temp_c")
        lbo_temp = status.get("lbo_temp_c")

        if keyswitch is not True:
            return False, "Waiting for keyswitch"

        if fault_codes is None:
            return False, "No response from laser"

        if len(fault_codes) == 0:
            return True, "Ready for operation"

        if set(fault_codes) == {5}:
            if lbo_set_temp is not None and lbo_temp is not None:
                diff = lbo_temp - lbo_set_temp
                return False, f"LBO warming up (ΔT = {diff:+.2f} °C)"
            return False, "LBO warming up"

        if self._controller is None:
            return False, "Controller not available"

        fault_text = "; ".join(self._controller.describe_fault_codes(fault_codes))
        return False, f"Blocking faults present: {fault_text}"

    def _emit_readiness_if_changed(self, ready: bool, message: str) -> None:
        current = (ready, message)
        if current != self._last_ready_tuple:
            self.readinessChanged.emit(ready, message)
            self._last_ready_tuple = current

    # ------------------------------------------------------------------
    # Kommandos
    # ------------------------------------------------------------------

    def _apply_pending_commands(self) -> None:
        if self._controller is None:
            return

        with self._lock:
            pending_laser = self._pending_laser_command
            pending_shutter = self._pending_shutter_command
            pending_power_w = self._pending_power_w

            # Wichtig: Einzelkommandos sofort leeren,
            # damit nichts dauerhaft "gehalten" wird.
            self._pending_laser_command = None
            self._pending_shutter_command = None
            self._pending_power_w = None

        # Laser ON/OFF: genau einmal senden
        if pending_laser is not None:
            ok = self._controller.set_laser_on(pending_laser)
            if ok:
                state_text = "ON" if pending_laser else "OFF"
                self.logMessage.emit(f"Laser command sent: {state_text}")
            else:
                self.logMessage.emit("Failed to send laser command")

        # Shutter OPEN/CLOSED: genau einmal senden
        if pending_shutter is not None:
            ok = self._controller.set_shutter_open(pending_shutter)
            if ok:
                state_text = "OPEN" if pending_shutter else "CLOSED"
                self.logMessage.emit(f"Shutter command sent: {state_text}")
            else:
                self.logMessage.emit("Failed to send shutter command")

        # Power nur bei explizitem Set-Klick
        if pending_power_w is not None:
            ok = self._controller.set_power_w(pending_power_w)
            if ok:
                self.logMessage.emit(f"Requested power set to {pending_power_w:.4f} W")
            else:
                self.logMessage.emit("Failed to set requested power")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _safe_close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._controller = None