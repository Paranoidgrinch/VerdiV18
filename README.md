# Verdi V18 Controller

Remote control and monitoring for a **Coherent Verdi V18** — the 18 W, 532 nm continuous-wave laser used for
photodetachment in the laser-assisted AMS beamline at CologneAMS. A small PyQt5 application talks to the
laser over TCP/IP (RS-232-over-Ethernet gateway) and keeps its status visible while the experiment runs.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-PyQt5-41CD52?style=flat-square&logo=qt&logoColor=white)
[![License](https://img.shields.io/badge/license-GPL--3.0-394B59?style=flat-square)](LICENSE)

## Features

- Laser on/off, shutter open/close and output-power setpoint
- Live status: laser state, set and measured output power, key switch, shutter
- LBO crystal: set and actual temperature, heater and servo status
- Fault codes, translated into readable messages
- Polling in a background thread, so the interface never blocks on the serial link

## Getting started

```bash
python -m venv .venv
.venv/bin/pip install PyQt5
.venv/bin/python main.py
```

Enter the address of the serial-to-Ethernet gateway (default `192.168.0.7:103`, see `DEFAULT_HOST` /
`DEFAULT_PORT` in `main.py`) and press **Connect / Start**.

## Structure

| File | Role |
| --- | --- |
| `main.py` | PyQt5 window: connection, controls, status display |
| `worker.py` | background thread that polls the laser and forwards commands |
| `verdi_controller.py` | laser logic: which commands exist and how replies become readable states |
| `verdi_protocol.py` | line-based TCP connection to the laser's serial interface |

Part of the CologneAMS control stack around [FLAVIA](https://github.com/Paranoidgrinch/FLAVIA-alpha-1.1-Fully-integrated-Laser-Anion-Variables-for-AMS-).

## License

GPL-3.0 — see [LICENSE](LICENSE).
