# Verdi V18 Controller

Remote control and monitoring for a Coherent Verdi V18, the 18 W, 532 nm CW laser used for photodetachment
at the laser-assisted AMS beamline at CologneAMS. A small PyQt5 application connects to the laser's serial
interface through an RS-232-to-Ethernet gateway.

## Features

- laser on/off, shutter open/close, output-power setpoint
- status: laser state, set and measured power, key switch, shutter
- LBO crystal: set and actual temperature, heater and servo status
- fault codes with their meaning
- polling in a background thread, so the window does not block on the serial link

## Usage

```bash
python -m venv .venv
.venv/bin/pip install PyQt5
.venv/bin/python main.py
```

Enter the address of the gateway (default `192.168.0.7:103`, see `DEFAULT_HOST` and `DEFAULT_PORT` in
`main.py`) and press *Connect / Start*.

## Files

| File | Content |
| --- | --- |
| `main.py` | window with connection, controls and status |
| `worker.py` | background thread that polls the laser and sends commands |
| `verdi_controller.py` | laser commands and interpretation of the replies |
| `verdi_protocol.py` | line-based TCP connection to the serial interface |

Part of the control software around [FLAVIA](https://github.com/Paranoidgrinch/FLAVIA-alpha-1.1-Fully-integrated-Laser-Anion-Variables-for-AMS-).

## License

GPL-3.0, see [LICENSE](LICENSE).
