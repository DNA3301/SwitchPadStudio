"""Non-persistent packaging check; never forwards physical input."""
import json
import sys
import tkinter as tk
from pathlib import Path

from .ui import SwitchPadApp


def verify_install(destination: Path):
    root = tk.Tk()
    root.withdraw()
    app = SwitchPadApp(root, initial_settings={"enabled": False, "tray_on_close": False}, persist=False, tray=False)
    errors = []
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))

    def finish():
        try:
            st = app.engine.get_state()
            result = {"python": ".".join(map(str, sys.version_info[:3])), "sdl": st.sdl_version,
                      "tabs": len(app.tabs.tabs()), "virtual_active": st.virtual_active,
                      "identity_bridge": bool(app.engine._identity and app.engine._identity.dll),
                      "errors": errors + ([st.last_error] if st.mode == "error" else [])}
            result["pass"] = bool(result["sdl"] and result["identity_bridge"] and result["tabs"] == 3
                                  and not result["virtual_active"] and not result["errors"])
            destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        finally:
            app._quit()
    root.after(1800, finish)
    root.mainloop()
