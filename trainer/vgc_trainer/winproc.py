


from __future__ import annotations

import os
import subprocess

NO_WINDOW: dict = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
