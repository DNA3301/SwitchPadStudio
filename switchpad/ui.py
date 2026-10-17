"""Native tkinter Windows desktop interface. The mapping engine never touches Tk."""
from __future__ import annotations
from datetime import datetime
import logging
import copy
import json
import os
from pathlib import Path
import platform
import queue
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser

from .engine import PadEngine
from . import diagnostics
from .mapping import BUTTONS, PadState, state_text
from . import settings as storage

LOG = logging.getLogger(__name__)

BG = "#0d1320"
PANEL = "#151e2d"
PANEL_2 = "#1d2a3c"
BORDER = "#2b3b51"
MUTED = "#9aadc1"
TEXT = "#e5edf6"
ACCENT = "#3dd6bd"
ACCENT_HOVER = "#65e8d1"
ERROR = "#ff8e9a"
WARN = "#ffd081"
BUTTON_OFF = "#304158"
AUTO_LABEL = "Automatico — primo controller disponibile"
TRIGGER_MODES = {"Assi 0 → 1": "axis", "Assi -1 → +1": "signed",
                 "Assi +1 → -1": "inverted_signed", "Asse condiviso (LT+ / RT-)": "combined",
                 "Pulsanti digitali": "buttons"}


class SwitchPadApp:
    def __init__(self, root: tk.Tk, *, initial_settings=None, persist=True, tray=True):
        self.root = root
        self.settings = storage.sanitize(initial_settings) if initial_settings is not None else storage.load()
        self.persist = persist
        self.engine = PadEngine(self.settings)
        self.command_queue = queue.Queue()
        self.devices_by_text = {}
        self.last_devices_key = None
        self.save_timer = None
        self.tray = None
        self.really_quitting = False
        self._last_status = None
        self._last_driver = None
        self._profile_guid = None
        self._loading_profile = False
        self._learn = None

        root.title("SwitchPad Studio 4.0 — Controller universali per Windows")
        root.geometry("980x730")
        root.minsize(830, 655)
        root.configure(bg=BG)
        try:
            root.iconphoto(True, self._tk_icon())
        except Exception:
            pass

        self._make_styles()
        self._build_ui()
        if tray:
            self._init_tray()
        self.engine.start()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(160, self._refresh)

    @staticmethod
    def _tk_icon() -> tk.PhotoImage:
        image = tk.PhotoImage(width=32, height=32)
        image.put(BG, to=(0, 0, 32, 32))
        image.put(ACCENT, to=(4, 12, 28, 21))
        image.put(ACCENT, to=(8, 8, 24, 24))
        image.put(PANEL, to=(12, 13, 20, 20))
        return image

    def _make_styles(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=[0, 8, 0, 0])
        s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                    font=("Segoe UI", 10, "bold"), padding=[19, 12], borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", PANEL_2)],
              foreground=[("selected", ACCENT)])
        s.configure("TCombobox", padding=8, fieldbackground=PANEL_2, background=PANEL_2,
                    foreground=TEXT, arrowcolor=ACCENT)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL_2)],
              foreground=[("readonly", TEXT)])
        s.configure("Horizontal.TScale", background=PANEL, troughcolor=BUTTON_OFF)
        s.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        s.map("TCheckbutton", foreground=[("disabled", MUTED)])
        s.configure("Horizontal.TProgressbar", troughcolor=PANEL_2,
                    background=ACCENT, borderwidth=0, thickness=10)
        s.configure("TSpinbox", foreground=TEXT, fieldbackground=PANEL_2, background=PANEL_2)
        s.configure("TScrollbar", background=PANEL_2, troughcolor=BG)
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", PANEL_2)

    def _label(self, parent, text, size=10, color=TEXT, bold=False, **kw):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kw)

    def _card(self, parent, **pack):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER,
                         highlightcolor=BORDER, highlightthickness=1, padx=18, pady=15)
        frame.pack(**pack)
        return frame

    def _button(self, parent, label: str, callback, primary=False, width=None):
        btn = tk.Button(parent, text=label, command=callback,
                        bg=ACCENT if primary else PANEL_2,
                        activebackground=ACCENT_HOVER if primary else BUTTON_OFF,
                        fg=BG if primary else TEXT, activeforeground=BG if primary else TEXT,
                        font=("Segoe UI", 10, "bold"), relief="flat", borderwidth=0,
                        cursor="hand2", padx=15, pady=9, takefocus=True)
        if width:
            btn.configure(width=width)
        return btn

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG, padx=23, pady=16)
        header.pack(fill="x")
        left = tk.Frame(header, bg=BG)
        left.pack(side="left")
        self._label(left, "SWITCHPAD", size=19, color=ACCENT, bold=True).pack(side="left")
        self._label(left, " STUDIO", size=19, bold=True).pack(side="left")
        self._label(left, "   v4.0  •  Universal XInput bridge", size=10, color=MUTED).pack(side="left", pady=(5, 0))
        self.badge = tk.Label(header, text="INIZIALIZZAZIONE", bg=PANEL_2, fg=WARN,
                              font=("Segoe UI", 10, "bold"), padx=14, pady=9)
        self.badge.pack(side="right")
        intro = tk.Frame(self.root, bg=BG, padx=24)
        intro.pack(fill="x")
        self._label(intro, "Lascia l'app aperta: gli input del pad diventano quelli di un controller Xbox.",
                    size=10, color=MUTED).pack(anchor="w")

        footer = tk.Frame(self.root, bg=BG, padx=24, pady=9)
        footer.pack(side="bottom", fill="x")
        self.footer_status = self._label(footer, "Inizializzazione SDL...", color=MUTED)
        self.footer_status.pack(side="left")
        self._label(footer, "120 Hz  •  Windows 10/11", color=MUTED).pack(side="right")

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(expand=True, fill="both", padx=23, pady=(10, 8))
        self.home = tk.Frame(self.tabs, bg=BG)
        self.options = tk.Frame(self.tabs, bg=BG)
        self.check = tk.Frame(self.tabs, bg=BG)
        self.tabs.add(self.home, text="  CONTROLLO  ")
        self.tabs.add(self.options, text="  PROFILI E TASTI  ")
        self.tabs.add(self.check, text="  DIAGNOSTICA  ")
        self._home_tab()
        self._options_tab()
        self._diagnostics_tab()
        self.root.bind_all("<MouseWheel>", self._wheel_options, add="+")

    def _home_tab(self):
        c = self._card(self.home, fill="x", pady=(4, 11))
        self._label(c, "CONTROLLER FISICO", size=11, bold=True).pack(anchor="w")
        combo_row = tk.Frame(c, bg=PANEL)
        combo_row.pack(fill="x", pady=(9, 5))
        self.device_var = tk.StringVar(value=AUTO_LABEL)
        self.combo = ttk.Combobox(combo_row, textvariable=self.device_var,
                                  state="readonly", width=70)
        self.combo.pack(side="left", fill="x", expand=True, padx=(0, 9))
        self.combo.bind("<<ComboboxSelected>>", self._on_pick)
        self._button(combo_row, "Rileva", self.engine.refresh_devices).pack(side="right")
        self.source_label = self._label(c, "Attendo il controller...", color=MUTED)
        self.source_label.pack(anchor="w", pady=(3, 0))
        actions = tk.Frame(c, bg=PANEL)
        actions.pack(fill="x", pady=(10, 1))
        self.on_btn = self._button(actions, "ATTIVA EMULAZIONE", lambda: self._enable(True), primary=True)
        self.on_btn.pack(side="left", padx=(0, 8))
        self._button(actions, "DISATTIVA", lambda: self._enable(False)).pack(side="left", padx=(0, 8))
        self._button(actions, "Bluetooth", diagnostics.open_bluetooth).pack(side="left", padx=(0, 8))
        self._button(actions, "Test Windows", diagnostics.open_joy).pack(side="left")

        live = self._card(self.home, fill="both", expand=True)
        row = tk.Frame(live, bg=PANEL)
        row.pack(fill="x")
        self._label(row, "USCITA XBOX • ANTEPRIMA", size=11, bold=True).pack(side="left")
        self.fps_label = self._label(row, "— Hz", color=MUTED)
        self.fps_label.pack(side="right")
        self.canvas = tk.Canvas(live, bg=PANEL, highlightthickness=0, height=200)
        self.canvas.pack(fill="both", expand=True, pady=(5, 4))
        for cx, cy, name in ((130, 96, "SINISTRA"), (352, 96, "DESTRA")):
            self.canvas.create_oval(cx - 60, cy - 60, cx + 60, cy + 60,
                                    fill=PANEL_2, outline=BORDER, width=2)
            self.canvas.create_line(cx - 60, cy, cx + 60, cy, fill=BORDER, width=1)
            self.canvas.create_line(cx, cy - 60, cx, cy + 60, fill=BORDER, width=1)
            self.canvas.create_text(cx, 184, text=name, fill=MUTED, font=("Segoe UI", 9, "bold"))
        self.sticks = []
        for cx, cy in ((130, 96), (352, 96)):
            self.sticks.append(self.canvas.create_oval(cx - 12, cy - 12, cx + 12, cy + 12,
                                                       fill=ACCENT, outline=""))
        self.button_items = {}
        btn_poses = {"Y": (616, 54), "X": (579, 91), "B": (653, 91), "A": (616, 128),
                     "LB": (535, 30), "RB": (697, 30), "BACK": (546, 163),
                     "START": (686, 163)}
        for label, (x, y) in btn_poses.items():
            r = 18 if label in {"A", "B", "X", "Y"} else 15
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill=BUTTON_OFF, outline=BORDER)
            self.canvas.create_text(x, y, text=label, font=("Segoe UI", 8, "bold"), fill=TEXT)
            self.button_items[label] = item
        self.triggers = tk.Frame(live, bg=PANEL)
        self.triggers.pack(fill="x", pady=(3, 4))
        self._label(self.triggers, "L2 / ZL / LT", color=MUTED).pack(side="left", padx=(0, 8))
        self.lt_bar = ttk.Progressbar(self.triggers, maximum=100)
        self.lt_bar.pack(side="left", fill="x", expand=True)
        self._label(self.triggers, "R2 / ZR / RT", color=MUTED).pack(side="left", padx=(20, 8))
        self.rt_bar = ttk.Progressbar(self.triggers, maximum=100)
        self.rt_bar.pack(side="left", fill="x", expand=True)
        self.live_input = self._label(live, "Premi un tasto del pad per verificarne la lettura.",
                                      color=MUTED, size=9, wraplength=840, justify="left")
        self.live_input.pack(anchor="w", pady=(7, 0))
        hint = tk.Frame(live, bg=PANEL)
        hint.pack(fill="x", pady=(7, 0))
        self._label(hint, "• Se qui i tasti reagiscono ma il gioco no, verifica il driver Xbox nella scheda Diagnostica.",
                    size=9, color=MUTED).pack(anchor="w")

    def _options_tab(self):
        holder = tk.Frame(self.options, bg=BG)
        holder.pack(fill="both", expand=True)
        scroll = tk.Canvas(holder, bg=BG, highlightthickness=0, borderwidth=0)
        vbar = ttk.Scrollbar(holder, orient="vertical", command=scroll.yview)
        scroll.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
        interior = tk.Frame(scroll, bg=BG)
        window = scroll.create_window((0, 0), window=interior, anchor="nw")
        interior.bind("<Configure>", lambda event: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda event: scroll.itemconfigure(window, width=event.width))
        self.option_scroll = scroll
        outer = self._card(interior, fill="x", pady=(4, 8))
        self._label(outer, "CONFIGURAZIONE EMULAZIONE", size=12, bold=True).pack(anchor="w")
        self._label(outer, "Le modifiche diventano attive senza riavviare l'app.",
                    color=MUTED).pack(anchor="w", pady=(4, 14))
        self.profile_label = self._label(outer, "Profilo: predefinito (collega un pad per salvarne uno dedicato)", color=ACCENT)
        self.profile_label.pack(anchor="w", pady=(0, 8))
        profile_row = tk.Frame(outer, bg=PANEL); profile_row.pack(fill="x", pady=(0, 12))
        self._button(profile_row, "Esporta profilo", self._export_profile).pack(side="left", padx=(0, 8))
        self._button(profile_row, "Importa profilo", self._import_profile).pack(side="left")
        layout_row = tk.Frame(outer, bg=PANEL)
        layout_row.pack(fill="x", pady=5)
        self._label(layout_row, "Tasti ABXY", size=10).pack(side="left", padx=(0, 30))
        self.layout_var = tk.StringVar(value="Nintendo (stesse lettere)" if self.settings["nintendo_letters"]
                                        else "Xbox (stessa posizione)")
        layout_choice = ttk.Combobox(layout_row, textvariable=self.layout_var, state="readonly",
                                     values=["Xbox (stessa posizione)", "Nintendo (stesse lettere)"], width=34)
        layout_choice.pack(side="left")
        layout_choice.bind("<<ComboboxSelected>>", lambda _: self._update_setting(
            "nintendo_letters", self.layout_var.get().startswith("Nintendo")))
        self._label(outer, "Xbox: il tasto B fisico di Switch corrisponde ad A di Xbox. Nintendo: A rimane A.",
                    size=9, color=MUTED).pack(anchor="w", pady=(0, 12))
        zone = tk.Frame(outer, bg=PANEL)
        zone.pack(fill="x")
        self._label(zone, "Deadzone analogici", size=10).pack(side="left")
        self.deadzone_value = tk.StringVar(value=f"{self.settings['deadzone']:.0%}")
        self._label(zone, "", size=10, color=ACCENT).pack(side="right")
        self.deadzone_text = tk.Label(zone, textvariable=self.deadzone_value, bg=PANEL, fg=ACCENT,
                                      font=("Segoe UI", 11, "bold"))
        self.deadzone_text.pack(side="right")
        self.deadzone_var = tk.DoubleVar(value=self.settings["deadzone"])
        ttk.Scale(outer, from_=0.0, to=0.35, variable=self.deadzone_var,
                  command=self._deadzone_changed).pack(fill="x", pady=(4, 12))

        check_row = tk.Frame(outer, bg=PANEL)
        check_row.pack(fill="x", pady=4)
        self.vars = {}
        for key, label in (("rumble", "Vibrazione (se supportata)"),
                           ("tray_on_close", "Riduci nell'area di notifica alla chiusura")):
            v = tk.BooleanVar(value=self.settings[key]); self.vars[key] = v
            ttk.Checkbutton(check_row, text=label, variable=v,
                            command=lambda k=key, val=v: self._update_setting(k, val.get())).pack(
                                side="left", padx=(0, 28))
        self.vars["force_raw"] = tk.BooleanVar(value=self.settings["force_raw"])
        ttk.Checkbutton(outer, text="Usa lettura RAW anche se SDL riconosce il pad (profilo manuale)",
                        variable=self.vars["force_raw"], command=lambda: self._update_setting(
                            "force_raw", self.vars["force_raw"].get())).pack(anchor="w", pady=(10, 4))
        self._label(outer, "Inverti direzione degli assi (facoltativo)", color=MUTED).pack(
            anchor="w", pady=(14, 5))
        flips = tk.Frame(outer, bg=PANEL); flips.pack(fill="x")
        for key, label in (("invert_lx", "SX X"), ("invert_ly", "SX Y"),
                           ("invert_rx", "DX X"), ("invert_ry", "DX Y")):
            v = tk.BooleanVar(value=self.settings[key]); self.vars[key] = v
            ttk.Checkbutton(flips, text=label, variable=v,
                            command=lambda k=key, val=v: self._update_setting(k, val.get())).pack(
                                side="left", padx=(0, 30))

        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x", pady=(19, 12))
        remap_grid = tk.Frame(outer, bg=PANEL); remap_grid.pack(fill="x", pady=(8, 10))
        self._label(outer, "Rimappa i tasti logici (sorgente → uscita Xbox); funziona anche in modalità SDL.",
                    color=MUTED, size=9).pack(anchor="w")
        self.remap_vars = {}
        for i, key in enumerate(BUTTONS):
            cell = tk.Frame(remap_grid, bg=PANEL); cell.grid(row=i // 4, column=i % 4, sticky="w", padx=(0, 12), pady=3)
            self._label(cell, key, size=9).pack(side="left")
            var = tk.StringVar(value=self.settings["button_remap"].get(key, key))
            self.remap_vars[key] = var
            choice = ttk.Combobox(cell, textvariable=var, values=[*BUTTONS, "DISABLED"], width=12, state="readonly")
            choice.pack(side="left", padx=(4, 0))
            choice.bind("<<ComboboxSelected>>", lambda _, k=key, v=var: self._remap_button(k, v.get()))
        self._label(outer, "CONFIGURAZIONE RAW • PAD GENERICI O PROFILO MANUALE", size=11, bold=True).pack(anchor="w")
        self._label(outer, "-1 = disattivato. Usa Rileva per assegnare un comando. Salva per abilitare l'uscita RAW.",
                    color=MUTED, size=9).pack(anchor="w", pady=(5, 8))
        trigrow = tk.Frame(outer, bg=PANEL); trigrow.pack(fill="x", pady=(0, 8))
        self._label(trigrow, "Trigger", size=9).pack(side="left", padx=(0, 12))
        self.raw_trigger_mode = tk.StringVar(value="Assi 0 → 1")
        ttk.Combobox(trigrow, textvariable=self.raw_trigger_mode, state="readonly",
                     values=list(TRIGGER_MODES), width=31).pack(side="left")
        self._label(trigrow, "D-pad hat (-1 = nessuno)", size=9).pack(side="left", padx=(12, 4))
        self.raw_hat = tk.StringVar(value=str(self.settings["raw"]["hat"]))
        ttk.Spinbox(trigrow, from_=-1, to=15, width=3, textvariable=self.raw_hat).pack(side="left")
        self.raw_fields = {}
        rgrid = tk.Frame(outer, bg=PANEL); rgrid.pack(anchor="w", fill="x")
        keys = [("axes", "lx", "Asse SX X"), ("axes", "ly", "Asse SX Y"),
                ("axes", "rx", "Asse DX X"), ("axes", "ry", "Asse DX Y"),
                ("buttons", "A", "A"), ("buttons", "B", "B"),
                ("buttons", "X", "X"), ("buttons", "Y", "Y"),
                ("buttons", "LB", "L / LB"), ("buttons", "RB", "R / RB"),
                ("buttons", "LT", "ZL / LT"), ("buttons", "RT", "ZR / RT"),
                ("buttons", "BACK", "SELECT"), ("buttons", "START", "START"),
                ("buttons", "LS", "CLICK SX"), ("buttons", "RS", "CLICK DX"),
                ("buttons", "GUIDE", "HOME"),
                ("buttons", "DPAD_UP", "DPad SU"), ("buttons", "DPAD_DOWN", "DPad GIÙ"),
                ("buttons", "DPAD_LEFT", "DPad SX"), ("buttons", "DPAD_RIGHT", "DPad DX"),
                ("trigger_axes", "lt", "Asse LT"), ("trigger_axes", "rt", "Asse RT"),
                ("dpad_axes", "x", "DPad asse X"), ("dpad_axes", "y", "DPad asse Y")]
        for i, (group, key, label) in enumerate(keys):
            column = i % 3
            row = i // 3
            cell = tk.Frame(rgrid, bg=PANEL); cell.grid(row=row, column=column, padx=(0, 18), pady=3, sticky="w")
            self._label(cell, label, size=9, color=MUTED).pack(side="left", padx=(0, 5))
            sv = tk.StringVar(value=str(self.settings["raw"][group][key]))
            self.raw_fields[(group, key)] = sv
            ttk.Spinbox(cell, from_=-1, to=127, width=4, textvariable=sv).pack(side="left")
            tk.Button(cell, text="Rileva", command=lambda g=group, k=key: self._start_learn(g, k),
                      bg=PANEL_2, fg=TEXT, relief="flat", font=("Segoe UI", 8)).pack(side="left", padx=(4, 0))
        bottom = tk.Frame(outer, bg=PANEL); bottom.pack(fill="x", pady=(12, 0))
        self._button(bottom, "SALVA MAPPATURA RAW", self._save_raw, primary=True).pack(side="left")
        self._button(bottom, "Ripristina impostazioni", self._reset_settings).pack(side="right")
        calibration = tk.Frame(outer, bg=PANEL); calibration.pack(fill="x", pady=(10, 0))
        self._button(calibration, "Calibra centro stick a riposo", self._calibrate).pack(side="left")
        self._button(calibration, "Preset Switch Pro RAW", self._switch_preset).pack(side="left", padx=(8, 0))
        self._label(outer, "Asse condiviso: assegna lo stesso indice a LT e RT; non distingue pressioni simultanee.",
                    color=MUTED, size=9).pack(anchor="w", pady=(8, 0))
        self.learn_text = self._label(outer, "Rilevamento: premi Rileva accanto al comando da assegnare.", color=ACCENT, wraplength=800)
        self.learn_text.pack(anchor="w", pady=(8, 0))
        self.raw_debug_text = self._label(outer, "Indici RAW: seleziona un dispositivo non mappato per vedere i suoi pulsanti.",
                                          color=MUTED, size=9, wraplength=820, justify="left")
        self.raw_debug_text.pack(anchor="w", pady=(12, 4))

    def _diagnostics_tab(self):
        c = self._card(self.check, fill="both", expand=True, pady=(4, 0))
        self._label(c, "STATO DEL SISTEMA", size=12, bold=True).pack(anchor="w")
        self._label(c, "Per i giochi XInput, Windows deve vedere anche il controller Xbox virtuale.",
                    color=MUTED, wraplength=800, justify="left").pack(anchor="w", pady=(4, 15))
        self.diag_var = tk.StringVar(value="Rilevamento in corso...")
        tk.Label(c, textvariable=self.diag_var, bg=PANEL_2, fg=TEXT,
                 font=("Consolas", 10), anchor="w", justify="left",
                 padx=16, pady=14, wraplength=800).pack(fill="x")
        quick = tk.Frame(c, bg=PANEL); quick.pack(fill="x", pady=(16, 8))
        self._button(quick, "Aggiorna test XInput", self._run_diagnostics, primary=True).pack(
            side="left", padx=(0, 10))
        self._button(quick, "Apri joy.cpl", diagnostics.open_joy).pack(side="left", padx=(0, 10))
        self._button(quick, "Esporta log", self._export_report).pack(side="left")
        self._label(c, "DRIVER NECESSARIO", size=11, bold=True).pack(anchor="w", pady=(17, 5))
        self._label(c, "ViGEmBus crea il dispositivo Xbox per Windows. È un driver legacy non più mantenuto; "
                    "va installato separatamente dal repository ufficiale e non viene modificato automaticamente.",
                    color=MUTED, wraplength=835, justify="left").pack(anchor="w", pady=(0, 9))
        links = tk.Frame(c, bg=PANEL); links.pack(fill="x", pady=(0, 6))
        self._button(links, "Release ufficiale ViGEmBus", lambda: webbrowser.open(diagnostics.DRIVER_RELEASES_URL)).pack(
            side="left", padx=(0, 10))
        self._button(links, "Avvertenze fine supporto", lambda: webbrowser.open(diagnostics.DRIVER_EOL_URL)).pack(
            side="left", padx=(0, 10))
        self._button(links, "Guida HidHide", lambda: webbrowser.open(diagnostics.HIDHIDE_URL)).pack(side="left")
        self._label(c, "EVITA IL DOPPIO INPUT", size=11, bold=True).pack(anchor="w", pady=(16, 5))
        self._label(c, "Non avviare BetterJoy / DS4Windows insieme a questa app per lo stesso pad. "
                    "Se il gioco riceve doppi input, disabilita Steam Input per quel gioco; "
                    "se necessario usa HidHide per nascondere SOLO il pad fisico ai giochi "
                    "e autorizzare questa app a leggerlo.",
                    color=MUTED, wraplength=835, justify="left").pack(anchor="w")
        self._label(c, "AVVIO CON WINDOWS", size=11, bold=True).pack(anchor="w", pady=(18, 5))
        autostart = tk.Frame(c, bg=PANEL); autostart.pack(anchor="w")
        self.startup_var = tk.BooleanVar(value=diagnostics.startup_registered())
        cb = ttk.Checkbutton(autostart, text="Avvia automaticamente con Windows (solo .exe)",
                             variable=self.startup_var, command=self._toggle_startup)
        cb.pack(anchor="w")
        if not getattr(sys, "frozen", False):
            cb.configure(state="disabled")
        self.root.after(1100, self._run_diagnostics)

    def _wheel_options(self, event):
        if hasattr(self, "option_scroll") and self.tabs.select() == str(self.options):
            x, y = self.root.winfo_pointerxy()
            left = self.option_scroll.winfo_rootx()
            top = self.option_scroll.winfo_rooty()
            if left <= x <= left + self.option_scroll.winfo_width() and top <= y <= top + self.option_scroll.winfo_height():
                self.option_scroll.yview_scroll(-int(event.delta / 120), "units")

    def _update_setting(self, key, value):
        if self._loading_profile:
            return
        if self._profile_guid and key in storage.PROFILE_KEYS:
            self.settings["profiles"][self._profile_guid][key] = value
        else:
            self.settings[key] = value
        self.engine.update_settings(self.settings)
        self._schedule_save()

    def _config(self):
        return storage.effective(self.settings, self._profile_guid or "")

    def _load_controls(self, cfg):
        self._loading_profile = True
        try:
            self.layout_var.set("Nintendo (stesse lettere)" if cfg["nintendo_letters"] else "Xbox (stessa posizione)")
            self.deadzone_var.set(cfg["deadzone"])
            self.deadzone_value.set(f"{cfg['deadzone']:.0%}")
            for key, var in self.vars.items():
                var.set(cfg[key])
            for (group, key), var in self.raw_fields.items():
                var.set(str(cfg["raw"][group][key]))
            self.raw_hat.set(str(cfg["raw"]["hat"]))
            self.raw_trigger_mode.set(next(k for k, v in TRIGGER_MODES.items() if v == cfg["raw"]["trigger_mode"]))
            for key, var in self.remap_vars.items():
                var.set(cfg["button_remap"].get(key, key))
        finally:
            self._loading_profile = False

    def _remap_button(self, key, target):
        remap = copy.deepcopy(self._config()["button_remap"])
        remap[key] = target
        self._update_setting("button_remap", remap)

    def _export_profile(self):
        dest = filedialog.asksaveasfilename(title="Esporta profilo controller", defaultextension=".json",
                                           initialfile="SwitchPad-profilo.json", filetypes=[("Profilo JSON", "*.json")])
        if not dest:
            return
        try:
            cfg = self._config()
            data = {"schema": "switchpad-profile-v1", "profile": {k: cfg[k] for k in storage.PROFILE_KEYS}}
            Path(dest).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as ex:
            messagebox.showerror("Esportazione", str(ex))

    def _import_profile(self):
        if not self._profile_guid:
            messagebox.showinfo("Profilo", "Collega e seleziona il controller a cui applicare il profilo.")
            return
        source = filedialog.askopenfilename(title="Importa profilo controller", filetypes=[("Profilo JSON", "*.json")])
        if not source:
            return
        try:
            if Path(source).stat().st_size > 256_000:
                raise ValueError("Il profilo supera il limite di 256 KB.")
            data = json.loads(Path(source).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema") != "switchpad-profile-v1" or not isinstance(data.get("profile"), dict):
                raise ValueError("Formato del profilo non riconosciuto.")
            cfg = storage.sanitize(data["profile"])
            cfg["raw_confirmed"] = False
            self.settings["profiles"][self._profile_guid] = {k: cfg[k] for k in storage.PROFILE_KEYS}
            self._load_controls(cfg)
            self.engine.update_settings(self.settings)
            self._schedule_save()
            messagebox.showinfo("Profilo importato", "Profilo applicato. Per la lettura RAW verifica gli indici e premi Salva mappatura RAW.")
        except (OSError, ValueError, RecursionError) as ex:
            messagebox.showerror("Importazione", str(ex))

    def _start_learn(self, group, key):
        st = self.engine.get_state()
        if not st.selected or st.selected.guid != self._profile_guid:
            messagebox.showinfo("Rilevamento", "Collega e seleziona prima un controller.")
            return
        self._finish_learn()
        self._learn = {"group": group, "key": key, "axes": st.raw_axes, "buttons": st.raw_buttons,
                       "guid": st.selected.guid, "deadline": time.monotonic() + 10,
                       "enabled": self.settings["enabled"]}
        self._update_setting("enabled", False)
        self.learn_text.configure(text=f"{key}: premi il tasto o muovi un solo asse entro 10 secondi. Uscita in pausa.")

    def _finish_learn(self, text=None):
        if self._learn:
            enabled = self._learn["enabled"]
            self._learn = None
            self._update_setting("enabled", enabled)
        if text:
            self.learn_text.configure(text=text)

    def _poll_learn(self, st):
        task = self._learn
        if not task:
            return
        if not st.selected or st.selected.guid != task["guid"] or time.monotonic() > task["deadline"]:
            self._finish_learn("Rilevamento terminato senza assegnazione. Ripremi Rileva per riprovare.")
            return
        group, key = task["group"], task["key"]
        candidate = None
        if group == "buttons":
            candidate = next((i for i, value in enumerate(st.raw_buttons)
                              if value and (i >= len(task["buttons"]) or not task["buttons"][i])), None)
            if candidate is None and key.startswith("DPAD_"):
                hat = next((i for i, value in enumerate(st.raw_hats) if value != (0, 0)), None)
                if hat is not None:
                    self.raw_hat.set(str(hat))
                    # One hat supplies all four directions; avoid duplicate button assignments.
                    for direction in ("DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"):
                        self.raw_fields[("buttons", direction)].set("-1")
                    self._finish_learn(f"D-pad rilevato come hat {hat}. Premi Salva mappatura RAW.")
                    return
        else:
            deltas = [(abs(value - task["axes"][i]), i) for i, value in enumerate(st.raw_axes) if i < len(task["axes"])]
            if deltas and max(deltas)[0] >= 0.55:
                candidate = max(deltas)[1]
        if candidate is not None:
            self.raw_fields[(group, key)].set(str(candidate))
            self._finish_learn(f"{key} assegnato all'indice {candidate}. Verifica il tipo di trigger e premi Salva mappatura RAW.")

    def _calibrate(self):
        st = self.engine.get_state()
        if not st.selected or st.selected.guid != self._profile_guid:
            messagebox.showinfo("Calibrazione", "Collega e seleziona prima un controller.")
            return
        raw = copy.deepcopy(self._config()["raw"])
        try:
            centers = {}
            for key in raw["axes"]:
                index = int(self.raw_fields[("axes", key)].get())
                value = st.raw_axes[index] if 0 <= index < len(st.raw_axes) else 0.0
                if abs(value) > .75:
                    raise ValueError("Rilascia gli stick al centro prima della calibrazione.")
                centers[key] = value
            raw["axis_centers"] = centers
            self._update_setting("raw", raw)
            self.learn_text.configure(text="Centri acquisiti. Calibrazione attiva nella lettura RAW; salva gli indici se li hai modificati.")
        except ValueError as ex:
            messagebox.showerror("Calibrazione", str(ex))

    def _switch_preset(self):
        cfg = self._config()
        cfg["raw"] = copy.deepcopy(storage.DEFAULT_RAW)
        self._load_controls(cfg)
        self.learn_text.configure(text="Preset Switch Pro caricato nei campi. Verifica gli indici e salva per applicarlo.")

    def _deadzone_changed(self, raw):
        val = round(float(raw), 2)
        self.deadzone_value.set(f"{val:.0%}")
        self._update_setting("deadzone", val)

    def _schedule_save(self):
        if not self.persist:
            return
        if self.save_timer is not None:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(300, self._save_settings)

    def _save_settings(self):
        self.save_timer = None
        if not self.persist:
            return
        try:
            storage.save(self.settings)
        except OSError as ex:
            LOG.exception("Settings could not be saved")
            messagebox.showwarning("Impostazioni", f"Impossibile salvare la configurazione:\n{ex}")

    def _on_pick(self, _event=None):
        selected = self.device_var.get()
        if selected not in self.devices_by_text:
            self._update_setting("auto_select", True)
            return
        dev = self.devices_by_text[selected]
        self.settings["auto_select"] = False
        self.settings["preferred_guid"] = dev.guid
        self.settings["preferred_instance"] = dev.instance_id
        self.engine.update_settings(self.settings)
        self._schedule_save()

    def _enable(self, val):
        self._update_setting("enabled", val)
        self.root.after(150, self._run_diagnostics)

    def _save_raw(self):
        selected = self.engine.get_state().selected
        if not selected or selected.guid != self._profile_guid:
            messagebox.showinfo("Mappatura RAW", "Collega e seleziona il controller prima di salvare il suo profilo RAW.")
            return
        try:
            raw = copy.deepcopy(self._config()["raw"])
            for (group, key), text in self.raw_fields.items():
                num = int(text.get())
                if not -1 <= num <= 127:
                    raise ValueError(f"{key}: indice fuori intervallo (-1...127)")
                raw[group][key] = num
            raw["hat"] = int(self.raw_hat.get())
            if not -1 <= raw["hat"] <= 15:
                raise ValueError("Hat: indice fuori intervallo (-1...15)")
            raw["trigger_mode"] = TRIGGER_MODES[self.raw_trigger_mode.get()]
            self._update_setting("raw", raw)
            self._update_setting("raw_confirmed", True)
            messagebox.showinfo("Mappatura RAW", "Mappatura salvata e applicata al controller RAW.")
        except ValueError as ex:
            messagebox.showerror("Indice non valido", str(ex))

    def _reset_settings(self):
        if not messagebox.askyesno("Ripristino", "Ripristinare tutti i valori predefiniti?"):
            return
        self.settings = storage.sanitize({})
        self._profile_guid = None
        self.last_devices_key = None
        self._load_controls(self.settings)
        self.engine.update_settings(self.settings)
        self._save_settings()
        messagebox.showinfo("Ripristinato", "Impostazioni ripristinate e applicate.")

    def _toggle_startup(self):
        try:
            diagnostics.set_startup(self.startup_var.get())
        except (OSError, RuntimeError) as ex:
            messagebox.showerror("Avvio Windows", str(ex))
            self.startup_var.set(diagnostics.startup_registered())

    def _run_diagnostics(self):
        state = self.engine.get_state()
        hint = diagnostics.driver_present()
        slots = diagnostics.xinput_slots()
        devname = state.selected.name if state.selected else "nessuno"
        vdriver = ("SI (rilevato nel registro)" if hint else
                   "NO (non rilevato)" if hint is False else "non determinato")
        lines = [f"Pad fisico : {devname}",
                 f"Input SDL  : {state.sdl_version or 'non inizializzato'}",
                 f"Xbox virt. : {'ATTIVO' if state.virtual_active else 'NON ATTIVO'}",
                 f"ViGEmBus   : {vdriver}",
                 f"Slot XInput: {', '.join(str(x['slot']) for x in slots) if slots else 'nessuno'}"]
        if state.last_error:
            lines += ["", "Ultimo errore:", state.last_error[:360]]
        self.diag_var.set("\n".join(lines))
        self._last_driver = hint

    def _export_report(self):
        default = f"SWITCHPAD_DIAGNOSTICA_{datetime.now():%Y%m%d_%H%M%S}.txt"
        dest = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=default,
                                            title="Salva la diagnostica", filetypes=[("File testo", "*.txt")])
        if not dest:
            return
        st = self.engine.get_state()
        diagnostics_text = self.diag_var.get()
        lines = ["SwitchPad Studio 4.0 — Diagnostica", f"Data: {datetime.now().isoformat(timespec='seconds')}",
                 f"Sistema: {platform.platform()}", f"Python: {sys.version}", diagnostics_text,
                 "", "Dispositivi:"]
        for d in st.devices:
            lines.append(f"- {d.title}, GUID={d.guid}, SDL={d.mapped}")
        lines += ["", "Ultimi input:", state_text(st.source), "", "Ultimi log:"]
        try:
            log_path = storage.config_root() / "logs" / "session.log"
            data = log_path.read_text(encoding="utf-8", errors="replace")
            lines.append(data[-16000:])
        except OSError:
            lines.append("Nessun log disponibile")
        try:
            Path(dest).write_text("\n".join(lines) + "\n", encoding="utf-8")
            messagebox.showinfo("Diagnostica", f"Report salvato:\n{dest}")
        except OSError as ex:
            messagebox.showerror("Salvataggio fallito", str(ex))

    def _refresh(self):
        if self.really_quitting:
            return
        while not self.command_queue.empty():
            try: command = self.command_queue.get_nowait()
            except queue.Empty: break
            if command == "show":
                self.root.deiconify(); self.root.lift()
            elif command == "quit":
                self._quit()
            elif command == "enable": self._enable(True)
            elif command == "disable": self._enable(False)
        if self.really_quitting:
            return
        st = self.engine.get_state()
        status = (st.status, st.mode, self.settings.get("enabled"))
        if status != self._last_status:
            if st.mode == "active":
                self.badge.configure(text="● XINPUT ATTIVO", fg=ACCENT)
            elif st.mode in ("error", "missing_driver"):
                self.badge.configure(text="● ATTENZIONE", fg=ERROR)
            elif st.mode == "ready":
                self.badge.configure(text="● IN PAUSA", fg=WARN)
            else:
                self.badge.configure(text="● RICERCA PAD", fg=WARN)
            self.footer_status.configure(text=st.status, fg=ERROR if st.mode in ("error", "missing_driver") else MUTED)
            self.on_btn.configure(text="EMULAZIONE ATTIVA" if self.settings["enabled"] else "ATTIVA EMULAZIONE")
            self._last_status = status
        devices_key = tuple((d.instance_id, d.guid, d.title) for d in st.devices)
        if devices_key != self.last_devices_key:
            self.last_devices_key = devices_key
            auto = AUTO_LABEL
            self.devices_by_text = {f"{d.title} • ID {d.instance_id}": d for d in st.devices}
            self.combo.configure(values=[auto, *self.devices_by_text.keys()])
            if self.settings.get("auto_select", True):
                self.device_var.set(auto)
            else:
                chosen = next((name for name, dev in self.devices_by_text.items()
                               if dev.guid == self.settings.get("preferred_guid")
                               and dev.instance_id == self.settings.get("preferred_instance")), None)
                if chosen is None:
                    chosen = next((name for name, dev in self.devices_by_text.items()
                                   if dev.guid == self.settings.get("preferred_guid")
                                   and st.selected and dev.instance_id == st.selected.instance_id), None)
                self.device_var.set(chosen or auto)
        if st.selected:
            if self._profile_guid != st.selected.guid:
                self._finish_learn()
                self._profile_guid = st.selected.guid
                if self._profile_guid not in self.settings["profiles"]:
                    cfg = {k: copy.deepcopy(self.settings[k]) for k in storage.PROFILE_KEYS}
                    if not st.selected.recommended and st.selected.guid != self.settings.get("preferred_guid"):
                        cfg["raw_confirmed"] = False
                    if not cfg["raw_confirmed"]:
                        cfg["raw"] = copy.deepcopy(storage.UNASSIGNED_RAW)
                    self.settings["profiles"][self._profile_guid] = cfg
                    self.engine.update_settings(self.settings)
                    self._schedule_save()
                self._load_controls(self._config())
                self.profile_label.configure(text=f"Profilo: {st.selected.name} • {st.selected.guid}")
            mode = "SDL / mappatura standard" if st.selected.mapped and not self._config()["force_raw"] else "RAW / mappatura manuale"
            self.source_label.configure(text=f"{st.selected.name}  •  {mode}", fg=ACCENT)
        else:
            self.source_label.configure(text="Pad non connesso. Puoi anche selezionare un dispositivo generico.", fg=MUTED)
        self.fps_label.configure(text=f"{st.fps:.0f} Hz" if st.fps else "— Hz")
        self._draw_state(st.translated)
        if hasattr(self, "raw_debug_text"):
            self.raw_debug_text.configure(text=st.raw_debug or "Indici RAW: disponibili quando selezioni un controller senza mappatura SDL.")
        self._poll_learn(st)
        self.root.after(110, self._refresh)

    def _draw_state(self, state: PadState):
        # User sees RAW physical readings even when emulation/driver is disabled.
        for item, cx, cy, x, y in ((self.sticks[0], 130, 96, state.lx, state.ly),
                                   (self.sticks[1], 352, 96, state.rx, state.ry)):
            # Y+ is UP, canvas Y+ is DOWN.
            px, py = cx + 46 * x, cy - 46 * y
            self.canvas.coords(item, px-12, py-12, px+12, py+12)
        for name, oval in self.button_items.items():
            self.canvas.itemconfig(oval, fill=ACCENT if name in state.buttons else BUTTON_OFF)
        self.lt_bar["value"] = round(state.lt * 100)
        self.rt_bar["value"] = round(state.rt * 100)
        self.live_input.configure(text=state_text(state))

    def _make_tray_icon(self):
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (64, 64), BG)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((9, 20, 55, 47), radius=10, fill=ACCENT)
            d.line((19, 33, 31, 33), width=4, fill=BG)
            d.line((25, 27, 25, 39), width=4, fill=BG)
            d.ellipse((39, 28, 46, 35), fill=BG)
            return img
        except ImportError:
            return None

    def _init_tray(self):
        try:
            import pystray
            icon_image = self._make_tray_icon()
            if icon_image is None:
                return
            menu = pystray.Menu(
                pystray.MenuItem("Apri SwitchPad Studio", lambda icon, item: self.command_queue.put("show"), default=True),
                pystray.MenuItem("Attiva emulazione", lambda icon, item: self.command_queue.put("enable")),
                pystray.MenuItem("Disattiva emulazione", lambda icon, item: self.command_queue.put("disable")),
                pystray.MenuItem("Chiudi completamente", lambda icon, item: self.command_queue.put("quit")),
            )
            self.tray = pystray.Icon("SwitchPadStudio", icon_image, "SwitchPad Studio", menu)
            self.tray.run_detached()
        except Exception as ex:
            LOG.warning("Tray unavailable: %s", ex)
            self.tray = None

    def _on_close(self):
        if self.settings.get("tray_on_close") and self.tray is not None:
            self.root.withdraw()
        elif messagebox.askyesno("Uscire da SwitchPad Studio?",
                                 "Terminando l'app il controller Xbox virtuale scompare e il pad potrebbe non funzionare nel gioco.\n\nUscire?"):
            self._quit()

    def _quit(self):
        if self.really_quitting:
            return
        self.really_quitting = True
        if self.save_timer is not None:
            try: self.root.after_cancel(self.save_timer)
            except Exception: pass
        if self.persist:
            try:
                storage.save(self.settings)
            except OSError:
                LOG.warning("Unable to persist config on quit")
        self.engine.stop()
        if self.tray:
            try: self.tray.stop()
            except Exception: pass
        self.root.destroy()
