from __future__ import annotations

import socket
from typing import Optional


class VerdiConnection:
    """
    Dünne TCP/IP-Hülle für einen Coherent Verdi.

    Wichtig:
    - sendet ASCII-Kommandos mit CRLF
    - liest bis zur ersten vollständigen Antwortzeile
    - macht bewusst noch KEIN fachliches Parsing
    """

    def __init__(self, host: str, port: int = 103, timeout: float = 1.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None

    @property
    def is_connected(self) -> bool:
        return self.sock is not None

    def connect(self) -> None:
        """
        Baut eine neue TCP-Verbindung auf.

        Wirft bei Fehlern eine Exception nach oben, damit die aufrufende
        Ebene sauber entscheiden kann, wie damit umzugehen ist.
        """
        self.close()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((self.host, self.port))
        self.sock = sock

    def close(self) -> None:
        """Schließt die Verbindung, falls vorhanden."""
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def send_command(self, command: str) -> Optional[str]:
        """
        Sendet genau ein Kommando und gibt die bereinigte Antwort zurück.

        Rückgabe:
            - str  -> bereinigte Antwort ohne CR/LF
            - None -> keine Antwort oder Kommunikationsfehler

        Fachliches Parsen passiert absichtlich nicht hier, sondern in
        verdi_controller.py.
        """
        if self.sock is None:
            return None

        try:
            payload = (command + "\r\n").encode("ascii")
            self.sock.sendall(payload)

            response = b""
            while True:
                try:
                    chunk = self.sock.recv(1024)
                except socket.timeout:
                    break

                if not chunk:
                    break

                response += chunk

                if b"\r\n" in response:
                    break

            if not response:
                return None

            return self._clean_response(response)

        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def _clean_response(raw: bytes) -> str:
        """
        Entfernt CR/LF und äußere Leerzeichen.
        """
        return raw.decode("ascii", errors="ignore").replace("\r", "").replace("\n", "").strip()