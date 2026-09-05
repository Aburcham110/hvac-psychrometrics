# HVAC Psychrometrics (Educational)

Python **stdlib-only** I-P approximations: from dry-bulb + RH or wet-bulb → dew point, humidity ratio, enthalpy.

> **Educational only.** Not a substitute for a calibrated psychrometer or OEM psych apps.

## Quick start

```bash
cd hvac-psychrometrics
python3 psychrometrics.py --db 75 --rh 50
python3 psychrometrics.py --db 80 --wb 67 --target-sh 10
python3 psychrometrics.py -i
```
