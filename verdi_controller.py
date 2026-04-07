from __future__ import annotations

import re
import time
from typing import Optional

from verdi_protocol import VerdiConnection


FAULT_DESCRIPTIONS: dict[int, str] = {
    1: "Laser head interlock fault",
    2: "External interlock fault",
    3: "Power supply cover interlock fault",
    4: "LBO temperature fault",
    5: "LBO not locked at set temperature",
    6: "Vanadate temperature fault",
    7: "Etalon temperature fault",
    8: "Diode 1 temperature fault",
    9: "Diode 2 temperature fault",
    10: "Baseplate temperature fault",
    11: "Heatsink 1 temperature fault",
    12: "Heatsink 2 temperature fault",
    16: "Diode 1 over-current fault",
    17: "Diode 2 over-current fault",
    18: "Over-current fault",
    19: "Diode 1 under-voltage fault",
    20: "Diode 2 under-voltage fault",
    21: "Diode 1 over-voltage fault",
    22: "Diode 2 over-voltage fault",
    25: "Diode 1 EEPROM fault",
    26: "Diode 2 EEPROM fault",
    27: "Laser head EEPROM fault",
    28: "Power supply EEPROM fault",
    29: "Power supply / head mismatch fault",
    31: "Shutter state mismatch",
    40: "Head / diode mismatch fault",
    47: "Vanadate 2 temperature fault",
}


class VerdiController:
    """
    Fachliche Logik für den Verdi.

    Diese Klasse kennt:
    - welche Kommandos sinnvoll sind
    - wie Antworten interpretiert werden
    - wie daraus lesbare Zustände werden

    Sie kennt aber bewusst noch keine GUI.
    """

    def __init__(self, connection: VerdiConnection) -> None:
        self.connection = connection

    # ------------------------------------------------------------------
    # Allgemeine Hilfsfunktionen
    # ------------------------------------------------------------------

    def _strip_prompt_and_echo(self, response: Optional[str], echoed_command: str) -> Optional[str]:
        """
        Entfernt robusteweise:
        - eventuelle 'Verdi>'-Prompts
        - das echo des gesendeten Kommandos

        Beispiel:
            'Verdi> ?K1'  -> '1'
            '?P5.000'     -> '5.000'
            'System OK'   -> 'System OK'
        """
        if response is None:
            return None

        text = response.strip()

        # Mehrfach mögliche Prompts entfernen
        while text.startswith("Verdi>"):
            text = text[len("Verdi>"):].strip()

        # Echo entfernen, falls vorhanden
        if text.upper().startswith(echoed_command.upper()):
            text = text[len(echoed_command):].strip()

        return text

    def _query_text(self, command: str) -> Optional[str]:
        raw = self.connection.send_command(command)
        return self._strip_prompt_and_echo(raw, command)

    def _query_float(self, command: str) -> Optional[float]:
        text = self._query_text(command)
        if text is None:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _query_int(self, command: str) -> Optional[int]:
        text = self._query_text(command)
        if text is None:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Lesen von Zuständen
    # ------------------------------------------------------------------

    def get_keyswitch_enabled(self) -> Optional[bool]:
        """
        ?K:
            0 -> keyswitch OFF
            1 -> keyswitch ON
        """
        value = self._query_int("?K")
        if value is None:
            return None
        if value == 1:
            return True
        if value == 0:
            return False
        return None

    def get_fault_codes(self) -> tuple[Optional[list[int]], str]:
        """
        ?F:
            - None, "No response..."   -> keine Antwort / unplausible Antwort
            - [], "System OK"          -> keine Faults
            - [..], raw_text           -> Faultliste
        """
        text = self._query_text("?F")
        if text is None:
            return None, "No response from laser"

        cleaned = text.strip()

        if "SYSTEM OK" in cleaned.upper():
            return [], "System OK"

        codes: list[int] = []
        for part in re.split(r"[,&\s]+", cleaned):
            if not part:
                continue
            if part.isdigit():
                codes.append(int(part))

        # Wichtig:
        # Wenn weder "System OK" noch gültige Zahlen erkannt wurden,
        # war die Antwort nicht sauber interpretierbar.
        if not codes:
            return None, f"Unrecognized fault response: {cleaned}"

        return codes, cleaned

    def describe_fault_codes(self, codes: list[int]) -> list[str]:
        if not codes:
            return ["System OK"]

        lines: list[str] = []
        for code in codes:
            description = FAULT_DESCRIPTIONS.get(code, "Unknown fault")
            lines.append(f"{code}: {description}")
        return lines

    def get_laser_state_code(self) -> Optional[int]:
        """
        ?L:
            0 -> OFF (standby)
            1 -> ON
            2 -> OFF because of fault
        """
        return self._query_int("?L")

    def get_laser_state_text(self) -> str:
        code = self.get_laser_state_code()
        mapping = {
            0: "OFF (Standby)",
            1: "ON",
            2: "OFF (Fault)",
        }
        return mapping.get(code, "Unknown")

    def get_shutter_state(self) -> Optional[bool]:
        """
        ?SHT:
            0 -> shutter closed
            1 -> shutter open
        """
        value = self._query_int("?SHT")
        if value is None:
            return None
        if value == 1:
            return True
        if value == 0:
            return False
        return None

    def get_set_power_w(self) -> Optional[float]:
        """
        ?SP -> gesetzter Leistungssollwert in W
        """
        return self._query_float("?SP")

    def get_output_power_w(self) -> Optional[float]:
        """
        ?P -> gemessene Ausgangsleistung in W
        """
        return self._query_float("?P")

    def get_lbo_set_temp_c(self) -> Optional[float]:
        return self._query_float("?LBOST")

    def get_lbo_temp_c(self) -> Optional[float]:
        return self._query_float("?LBOT")

    def get_lbo_temperatures(self) -> tuple[Optional[float], Optional[float]]:
        return self.get_lbo_set_temp_c(), self.get_lbo_temp_c()

    def get_lbo_heater_status_code(self) -> Optional[int]:
        """
        ?LBOH:
            0 -> COOL DOWN
            1 -> HEATING
        """
        return self._query_int("?LBOH")

    def get_lbo_heater_status_text(self) -> str:
        code = self.get_lbo_heater_status_code()
        mapping = {
            0: "COOL DOWN",
            1: "HEATING",
        }
        return mapping.get(code, "Unknown")

    def get_lbo_servo_status_code(self) -> Optional[int]:
        """
        ?LBOSS:
            0 -> OPEN
            1 -> LOCKED
            2 -> SEEKING
            3 -> FAULT
            4 -> OPTIMIZING
            5 -> CPEAKING
            6 -> CPEAKING2
        """
        return self._query_int("?LBOSS")

    def get_lbo_servo_status_text(self) -> str:
        code = self.get_lbo_servo_status_code()
        mapping = {
            0: "OPEN",
            1: "LOCKED",
            2: "SEEKING",
            3: "FAULT",
            4: "OPTIMIZING",
            5: "CPEAKING",
            6: "CPEAKING2",
        }
        return mapping.get(code, "Unknown")

    def read_basic_status(self) -> dict[str, object]:
        """
        Kompakte Sammelabfrage für die GUI / den Worker.
        """
        fault_codes, fault_text = self.get_fault_codes()
        lbo_set, lbo_meas = self.get_lbo_temperatures()

        fault_descriptions: list[str] = []
        if fault_codes:
            fault_descriptions = self.describe_fault_codes(fault_codes)

        return {
            "keyswitch_enabled": self.get_keyswitch_enabled(),
            "fault_codes": fault_codes,
            "fault_text": fault_text,
            "fault_descriptions": fault_descriptions,
            "laser_state_code": self.get_laser_state_code(),
            "laser_state_text": self.get_laser_state_text(),
            "shutter_open": self.get_shutter_state(),
            "set_power_w": self.get_set_power_w(),
            "output_power_w": self.get_output_power_w(),
            "lbo_heater_status_code": self.get_lbo_heater_status_code(),
            "lbo_heater_status_text": self.get_lbo_heater_status_text(),
            "lbo_servo_status_code": self.get_lbo_servo_status_code(),
            "lbo_servo_status_text": self.get_lbo_servo_status_text(),
            "lbo_set_temp_c": lbo_set,
            "lbo_temp_c": lbo_meas,
        }

    # ------------------------------------------------------------------
    # Schreiben von Zuständen
    # ------------------------------------------------------------------

    def set_laser_on(self, on: bool) -> bool:
        """
        L=1 / L=0 senden und anschließend grob zurückprüfen.
        """
        command = f"L={1 if on else 0}"
        self.connection.send_command(command)

        state = self.get_laser_state_code()
        if state is None:
            return False

        if on:
            return state == 1
        return state == 0

    def set_shutter_open(self, open_: bool) -> bool:
        """
        S=1 / S=0 senden.

        Wichtig:
        Der echte Status wird im normalen Polling über ?SHT gelesen.
        Wir versuchen hier nur eine sanfte Kurzprüfung, ohne bei
        verzögerter Rückmeldung sofort "Fehler" zu melden.
        """
        command = f"S={1 if open_ else 0}"
        response = self.connection.send_command(command)

        # Wenn gar keine Antwort auf das Kommando kam -> echter Fehler
        if response is None:
            return False

        # Kurze, weiche Nachprüfung:
        # Falls ?SHT schnell verfügbar ist, super.
        # Falls nicht, werten wir das Kommando trotzdem nicht sofort als Fehler.
        for _ in range(3):
            time.sleep(0.2)
            state = self.get_shutter_state()
            if state is not None:
                return state == open_

        # Wenn der Readback noch nicht sauber da ist:
        # Kommando wurde immerhin gesendet, die reguläre Statusanzeige
        # im Polling entscheidet dann über den echten Zustand.
        return True

    def set_power_w(self, watts: float) -> bool:
        """
        P=nn.nnnn senden.

        Rückgabewert:
            True  -> Kommando wenigstens abgeschickt, Sollwert plausibel lesbar
            False -> keine vernünftige Rückmeldung
        """
        safe_value = max(0.0, float(watts))
        self.connection.send_command(f"P={safe_value:.4f}")

        reported_set_power = self.get_set_power_w()
        if reported_set_power is None:
            return False

        return abs(reported_set_power - safe_value) < 1e-3