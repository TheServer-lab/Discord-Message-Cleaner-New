"""
Message Cleaner — Discord Bot Manager
Maintained by TheServer-lab | github.com/TheServer-lab/Discord-Message-Cleaner-New
Original project by Random Python Discord
"""

import asyncio
import datetime
import json
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import discord
from discord.ext import commands, tasks
from PIL import Image
import pystray
from pystray import MenuItem as item

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

APP_VERSION = "0.3"
APP_NAME = "Message Cleaner"
DISCORD_INVITE = "https://discord.gg/wJEfpyd2fk"
UPDATE_THREAD_URL = "https://discord.com/channels/1295360135463567511/1388437655787929685"
UPDATE_CHANNEL_ID = 1388447215017529404
UPDATE_MESSAGE_ID = 1388447503833235506

CONFIG_DIR = Path.home() / "Documents" / "Random Python" / "Message Cleaner"
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_DIR = CONFIG_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Colours — Discord-inspired dark theme
C_BG        = "#1e1f22"
C_SURFACE   = "#2b2d31"
C_PANEL     = "#313338"
C_BORDER    = "#3f4147"
C_ACCENT    = "#5865f2"
C_ACCENT_H  = "#4752c4"
C_DANGER    = "#ed4245"
C_WARNING   = "#fee75c"
C_SUCCESS   = "#57f287"
C_TEXT      = "#e0e0e0"
C_MUTED     = "#949ba4"
C_ENTRY     = "#1e1f22"

FONT_UI     = ("Segoe UI", 10)
FONT_LABEL  = ("Segoe UI", 9)
FONT_MONO   = ("Consolas", 10)
FONT_TITLE  = ("Segoe UI Semibold", 13)

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

def _setup_logging() -> logging.Logger:
    log_filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.log")
    log_path = LOG_DIR / log_filename
    logger = logging.getLogger("MessageCleaner")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    logger.addHandler(fh)
    return logger

logger = _setup_logging()

def resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative)


# ─────────────────────────────────────────────
# Config Manager
# ─────────────────────────────────────────────

class ConfigManager:
    DEFAULTS = {
        "token": "",
        "channel_ids": [],
        "delete_older_than_minutes": 60,
        "check_interval_seconds": 1800,
    }

    def load(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {**self.DEFAULTS, **data}
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load config: %s", exc)
        return dict(self.DEFAULTS)

    def save(self, config: dict) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        logger.info("Config saved.")


# ─────────────────────────────────────────────
# Update Checker
# ─────────────────────────────────────────────

class UpdateChecker:
    """Fetches the latest version from the Discord update channel."""

    def __init__(self, token: str, on_update_available, on_up_to_date, on_error):
        self._token = token
        self._on_update = on_update_available
        self._on_ok = on_up_to_date
        self._on_error = on_error

    def check(self) -> None:
        if not self._token or self._token == "[REDACTED]":
            self._on_error("Update token not configured.")
            return
        threading.Thread(target=self._run, daemon=True, name="UpdateChecker").start()

    def _run(self) -> None:
        try:
            asyncio.run(self._fetch())
        except Exception as exc:
            self._on_error(str(exc))

    async def _fetch(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = True

        checker = self

        class _Client(discord.Client):
            async def on_ready(self):
                try:
                    channel = await self.fetch_channel(UPDATE_CHANNEL_ID)
                    message = await channel.fetch_message(UPDATE_MESSAGE_ID)
                    lines = message.content.splitlines()
                    version_line = next(
                        (l for l in lines if l.lower().startswith("current version:")), None
                    )
                    if not version_line:
                        checker._on_error("Version info not found in update message.")
                        return
                    latest = version_line.split(":", 1)[1].strip()
                    changelog = "\n".join(
                        l for l in lines
                        if l.lower().startswith("update info:") or l.startswith("-")
                    )
                    if latest > APP_VERSION:
                        checker._on_update(latest, UPDATE_THREAD_URL, changelog)
                    else:
                        checker._on_ok(APP_VERSION)
                except Exception as exc:
                    checker._on_error(str(exc))
                finally:
                    await self.close()

        client = _Client(intents=intents)
        await client.start(checker._token)


# ─────────────────────────────────────────────
# Bot Manager
# ─────────────────────────────────────────────

class BotManager:
    """Manages the lifecycle of the Discord cleaning bot on its own thread/loop."""

    def __init__(self, log_fn):
        self._log = log_fn
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bot: commands.Bot | None = None
        self._stop_event = threading.Event()

    # ── Public API ──────────────────────────────

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, config: dict) -> None:
        if self.running:
            self._log("⚠️  Bot is already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, args=(config,), daemon=True, name="BotThread"
        )
        self._thread.start()

    def stop(self) -> None:
        if not self.running:
            self._log("⚠️  Bot is not running.")
            return
        self._log("🛑 Stopping bot…")
        self._stop_event.set()
        if self._loop and self._bot:
            asyncio.run_coroutine_threadsafe(self._bot.close(), self._loop)

    def restart(self, config: dict) -> None:
        self.stop()
        # Wait briefly for the old thread to exit
        if self._thread:
            self._thread.join(timeout=5)
        self.start(config)

    # ── Internal ────────────────────────────────

    def _run(self, config: dict) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._bot_main(config))
        except Exception as exc:
            self._log(f"💥 Bot error: {exc}")
            logger.exception("Bot crashed")
        finally:
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                self._loop.close()
            except Exception:
                pass
            self._log("🔴 Bot stopped.")

    async def _bot_main(self, config: dict) -> None:
        token    = config["token"]
        ch_ids   = config["channel_ids"]
        max_age  = config["delete_older_than_minutes"]
        interval = config["check_interval_seconds"]

        intents = discord.Intents.default()
        intents.messages = True
        intents.guilds = True
        intents.message_content = True

        bot = commands.Bot(command_prefix="!", intents=intents)
        self._bot = bot
        log = self._log

        @bot.event
        async def on_ready():
            log(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
            log(f"📋 Watching {len(ch_ids)} channel(s) | age >{max_age}m | interval {interval}s")
            clean_task.start()

        @bot.event
        async def on_disconnect():
            log("⚡ Bot disconnected. Attempting reconnect…")

        @tasks.loop(seconds=interval)
        async def clean_task():
            now = datetime.datetime.now(datetime.timezone.utc)
            threshold = now - datetime.timedelta(minutes=max_age)
            deleted_total = 0

            for ch_id in ch_ids:
                channel = bot.get_channel(ch_id)
                if not isinstance(channel, discord.TextChannel):
                    log(f"⚠️  Channel {ch_id} not found or not a text channel — skipping.")
                    continue

                log(f"🔍 Scanning #{channel.name} …")
                deleted = 0
                try:
                    async for msg in channel.history(limit=500, oldest_first=True):
                        if self._stop_event.is_set():
                            return
                        if msg.created_at < threshold:
                            try:
                                await msg.delete()
                                deleted += 1
                                deleted_total += 1
                                await asyncio.sleep(1.1)  # stay well under rate limit
                            except discord.Forbidden:
                                log(f"🚫 Missing permissions in #{channel.name}")
                                break
                            except discord.HTTPException as exc:
                                log(f"❌ HTTP error deleting message: {exc.status} {exc.text}")
                except discord.Forbidden:
                    log(f"🚫 Cannot read history in #{channel.name}")
                except discord.HTTPException as exc:
                    log(f"⚠️  HTTP error scanning #{channel.name}: {exc.status}")

                if deleted:
                    log(f"🗑️  #{channel.name}: deleted {deleted} message(s)")

            if deleted_total == 0:
                log("✔  Scan complete — nothing to delete.")
            else:
                log(f"✅ Cycle done — {deleted_total} message(s) removed.")

        @clean_task.before_loop
        async def before_clean():
            await bot.wait_until_ready()

        try:
            await bot.start(token)
        except discord.LoginFailure:
            log("❌ Invalid bot token. Please check your settings.")
        except discord.PrivilegedIntentsRequired:
            log("❌ Bot requires privileged intents. Enable them in the Discord Developer Portal.")


# ─────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────

class App:
    def __init__(self):
        self.config_mgr = ConfigManager()
        self.bot_mgr = BotManager(log_fn=self._log)
        self._tray: pystray.Icon | None = None

        self._build_window()
        self._load_ui_config()
        self._check_updates_silently()

    # ── Window ───────────────────────────────────

    def _build_window(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME}  v{APP_VERSION}")
        self.root.geometry("760x640")
        self.root.minsize(640, 560)
        self.root.configure(bg=C_BG)

        try:
            ico = resource_path("Cleaner_icon-icons.com_53211.ico")
            self.root.iconbitmap(ico)
        except Exception:
            pass

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_header()
        self._build_config_panel()
        self._build_button_bar()
        self._build_log_panel()
        self._build_status_bar()

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C_SURFACE, pady=12)
        hdr.pack(fill="x")

        tk.Label(
            hdr, text=f"🧹  {APP_NAME}",
            bg=C_SURFACE, fg=C_TEXT,
            font=FONT_TITLE
        ).pack(side="left", padx=18)

        tk.Label(
            hdr, text=f"v{APP_VERSION}",
            bg=C_SURFACE, fg=C_MUTED,
            font=FONT_LABEL
        ).pack(side="left")

        # Status pill
        self._status_var = tk.StringVar(value="Stopped")
        self._status_label = tk.Label(
            hdr, textvariable=self._status_var,
            bg=C_DANGER, fg="white",
            font=("Segoe UI Semibold", 9),
            padx=10, pady=3, relief="flat"
        )
        self._status_label.pack(side="right", padx=18)

    def _build_config_panel(self):
        outer = tk.Frame(self.root, bg=C_BG, padx=18, pady=12)
        outer.pack(fill="x")

        panel = tk.Frame(outer, bg=C_SURFACE, pady=14, padx=16, relief="flat")
        panel.pack(fill="x")

        tk.Label(panel, text="Configuration", bg=C_SURFACE, fg=C_MUTED,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, columnspan=4,
                 sticky="w", pady=(0, 8))

        fields = [
            ("Bot Token", "token_entry", 0, 0, 60, True),
            ("Channel IDs  (comma-separated)", "channel_entry", 0, 2, 30, False),
            ("Delete older than (minutes)", "age_entry", 1, 0, 10, False),
            ("Check interval (seconds)", "interval_entry", 1, 2, 10, False),
        ]

        for label, attr, row, col, width, show_star in fields:
            lbl_col = col
            ent_col = col + 1
            r = row + 1
            tk.Label(panel, text=label, bg=C_SURFACE, fg=C_TEXT,
                     font=FONT_LABEL).grid(row=r, column=lbl_col, sticky="w", padx=(0, 6), pady=4)
            show = "*" if show_star else ""
            entry = tk.Entry(panel, width=width, bg=C_ENTRY, fg=C_TEXT,
                             insertbackground=C_TEXT, relief="flat",
                             font=FONT_UI, show=show,
                             highlightthickness=1, highlightbackground=C_BORDER,
                             highlightcolor=C_ACCENT)
            entry.grid(row=r, column=ent_col, sticky="ew", padx=(0, 16), pady=4)
            setattr(self, attr, entry)

        # Show/hide token
        self._show_token = False
        tk.Button(
            panel, text="👁", bg=C_SURFACE, fg=C_MUTED,
            relief="flat", cursor="hand2", font=("Segoe UI", 9),
            command=self._toggle_token_visibility
        ).grid(row=2, column=1, sticky="e", padx=(0, 16))

        panel.columnconfigure(1, weight=2)
        panel.columnconfigure(3, weight=1)

    def _toggle_token_visibility(self):
        self._show_token = not self._show_token
        self.token_entry.config(show="" if self._show_token else "*")

    def _build_button_bar(self):
        bar = tk.Frame(self.root, bg=C_BG, padx=18, pady=4)
        bar.pack(fill="x")

        buttons = [
            ("▶  Save & Start", self._save_and_start, C_ACCENT, "white"),
            ("■  Stop",         self.bot_mgr.stop,    C_DANGER, "white"),
            ("↺  Restart",      self._restart,         C_WARNING, "#1e1f22"),
        ]
        for text, cmd, bg, fg in buttons:
            tk.Button(
                bar, text=text, command=cmd,
                bg=bg, fg=fg, activebackground=bg,
                relief="flat", cursor="hand2",
                font=("Segoe UI Semibold", 9),
                padx=14, pady=6
            ).pack(side="left", padx=(0, 6))

        # Right-side utility buttons
        utils = [
            ("📁 Logs",      self._open_logs_folder),
            ("🗑 Clear Logs", self._delete_logs),
            ("ℹ️ About",      self._show_about),
        ]
        for text, cmd in utils:
            tk.Button(
                bar, text=text, command=cmd,
                bg=C_PANEL, fg=C_TEXT, activebackground=C_BORDER,
                relief="flat", cursor="hand2",
                font=FONT_LABEL, padx=10, pady=6
            ).pack(side="right", padx=(4, 0))

    def _build_log_panel(self):
        frame = tk.Frame(self.root, bg=C_BG, padx=18, pady=6)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Live Log", bg=C_BG, fg=C_MUTED,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w")

        self.log_box = scrolledtext.ScrolledText(
            frame, state="disabled", wrap="word",
            bg=C_PANEL, fg=C_TEXT,
            font=FONT_MONO,
            relief="flat",
            highlightthickness=1, highlightbackground=C_BORDER,
            selectbackground=C_ACCENT,
        )
        self.log_box.pack(fill="both", expand=True, pady=(4, 0))

        # Colour tags for log lines
        self.log_box.tag_config("ok",      foreground=C_SUCCESS)
        self.log_box.tag_config("error",   foreground=C_DANGER)
        self.log_box.tag_config("warn",    foreground=C_WARNING)
        self.log_box.tag_config("muted",   foreground=C_MUTED)
        self.log_box.tag_config("default", foreground=C_TEXT)

        # Redirect stdout → log box
        sys.stdout = _StdoutRedirector(self._log)

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=C_SURFACE, pady=5)
        bar.pack(fill="x", side="bottom")

        self._status_bar_var = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self._status_bar_var, bg=C_SURFACE,
                 fg=C_MUTED, font=FONT_LABEL).pack(side="left", padx=12)

        tk.Button(
            bar, text="Join Discord",
            command=lambda: webbrowser.open(DISCORD_INVITE),
            bg=C_SURFACE, fg=C_ACCENT,
            relief="flat", cursor="hand2",
            font=FONT_LABEL
        ).pack(side="right", padx=12)

    # ── Config helpers ───────────────────────────

    def _load_ui_config(self):
        cfg = self.config_mgr.load()
        self.token_entry.insert(0, cfg.get("token", ""))
        self.channel_entry.insert(0, ",".join(map(str, cfg.get("channel_ids", []))))
        self.age_entry.insert(0, str(cfg.get("delete_older_than_minutes", 60)))
        self.interval_entry.insert(0, str(cfg.get("check_interval_seconds", 1800)))

    def _read_ui_config(self) -> dict | None:
        """Validate and return config from the UI fields, or None on error."""
        token = self.token_entry.get().strip()
        raw_channels = self.channel_entry.get().strip()

        if not token:
            messagebox.showerror("Missing Token", "Please enter your bot token.")
            return None

        try:
            channel_ids = [int(c.strip()) for c in raw_channels.split(",") if c.strip()]
        except ValueError:
            messagebox.showerror("Invalid Channels", "Channel IDs must be numbers separated by commas.")
            return None

        if not channel_ids:
            messagebox.showerror("Missing Channels", "Please enter at least one channel ID.")
            return None

        try:
            age = int(self.age_entry.get())
            interval = int(self.interval_entry.get())
            assert age > 0 and interval > 0
        except (ValueError, AssertionError):
            messagebox.showerror("Invalid Values", "Age and interval must be positive integers.")
            return None

        return {
            "token": token,
            "channel_ids": channel_ids,
            "delete_older_than_minutes": age,
            "check_interval_seconds": interval,
        }

    def _save_and_start(self):
        cfg = self._read_ui_config()
        if cfg is None:
            return
        try:
            self.config_mgr.save(cfg)
            self._log("💾 Config saved.")
        except OSError as exc:
            self._log(f"❌ Could not save config: {exc}")
        self._set_status("Running", C_SUCCESS)
        self.bot_mgr.start(cfg)

    def _restart(self):
        cfg = self._read_ui_config()
        if cfg is None:
            return
        self._set_status("Restarting…", C_WARNING)
        threading.Thread(
            target=lambda: (self.bot_mgr.restart(cfg), self._set_status("Running", C_SUCCESS)),
            daemon=True
        ).start()

    # ── Status / logging ─────────────────────────

    def _set_status(self, text: str, colour: str):
        self._status_var.set(text)
        self._status_label.config(bg=colour)
        self._status_bar_var.set(text)

    def _log(self, message: str):
        """Thread-safe log to the GUI box."""
        self.root.after(0, self._append_log, message)

    def _append_log(self, message: str):
        self.log_box.configure(state="normal")
        tag = "default"
        lower = message.lower()
        if any(k in lower for k in ("✅", "💾", "✔", "🗑️")):
            tag = "ok"
        elif any(k in lower for k in ("❌", "💥", "🚫")):
            tag = "error"
        elif any(k in lower for k in ("⚠️", "⚡", "🔴")):
            tag = "warn"
        elif any(k in lower for k in ("🔍", "📋", "📂")):
            tag = "muted"

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.insert(tk.END, f"[{ts}]  {message}\n", tag)
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")
        logger.info(message)

    # ── Utilities ────────────────────────────────

    def _open_logs_folder(self):
        try:
            os.startfile(LOG_DIR)
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", str(LOG_DIR)])

    def _delete_logs(self):
        if not messagebox.askyesno("Delete Logs", "Delete all log files? This cannot be undone."):
            return
        removed = 0
        for f in LOG_DIR.glob("*.log"):
            try:
                f.unlink()
                removed += 1
            except OSError as exc:
                self._log(f"⚠️  Could not delete {f.name}: {exc}")
        self._log(f"🗑️  Deleted {removed} log file(s).")

    def _show_about(self):
        win = tk.Toplevel(self.root)
        win.title("About")
        win.geometry("360x280")
        win.resizable(False, False)
        win.configure(bg=C_SURFACE)
        win.grab_set()

        tk.Label(
            win, text="🧹", bg=C_SURFACE, font=("Segoe UI", 36)
        ).pack(pady=(18, 4))

        tk.Label(
            win, text=f"{APP_NAME}  v{APP_VERSION}",
            bg=C_SURFACE, fg=C_TEXT,
            font=("Segoe UI Semibold", 13)
        ).pack()

        tk.Label(
            win,
            text="Maintained by TheServer-lab\nOriginal project by Random Python Discord",
            bg=C_SURFACE, fg=C_MUTED, font=FONT_LABEL, justify="center"
        ).pack(pady=8)

        for text, cmd, bg in [
            ("Join Discord",      lambda: webbrowser.open(DISCORD_INVITE), C_ACCENT),
            ("Check for Updates", self._check_updates_silently,            C_PANEL),
            ("View on GitHub",    lambda: webbrowser.open(
                "https://github.com/TheServer-lab/Discord-Message-Cleaner-New"), C_PANEL),
            ("Close",             win.destroy,                              C_PANEL),
        ]:
            tk.Button(
                win, text=text, command=cmd,
                bg=bg, fg="white", relief="flat",
                cursor="hand2", font=FONT_LABEL,
                padx=12, pady=5
            ).pack(pady=3, ipadx=20)

    # ── Update checker ───────────────────────────

    def _check_updates_silently(self):
        cfg = self.config_mgr.load()
        token = cfg.get("update_bot_token", "[REDACTED]")
        UpdateChecker(
            token=token,
            on_update_available=self._on_update_found,
            on_up_to_date=lambda v: self._log(f"✔  You're on the latest version ({v})."),
            on_error=lambda e: self._log(f"⚠️  Update check skipped: {e}"),
        ).check()

    def _on_update_found(self, version: str, url: str, changelog: str):
        self.root.after(0, self._prompt_update, version, url, changelog)

    def _prompt_update(self, version: str, url: str, changelog: str):
        msg = f"Version {version} is available!\n\nChangelog:\n{changelog or 'No notes provided.'}\n\nOpen download page?"
        if messagebox.askyesno("Update Available", msg):
            webbrowser.open(url)

    # ── Tray ─────────────────────────────────────

    def _setup_tray(self):
        try:
            ico_path = resource_path("Cleaner_icon-icons.com_53211.ico")
            image = Image.open(ico_path)
        except Exception:
            image = Image.new("RGB", (64, 64), color=C_ACCENT)

        menu = pystray.Menu(
            item("Show",        self._tray_show),
            item("Start Bot",   lambda: self._save_and_start()),
            item("Stop Bot",    lambda: self.bot_mgr.stop()),
            pystray.Menu.SEPARATOR,
            item("Quit",        self._quit),
        )
        self._tray = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        threading.Thread(target=self._tray.run, daemon=True, name="TrayThread").start()

    def _tray_show(self):
        self.root.after(0, self.root.deiconify)

    def _on_close(self):
        if messagebox.askyesno("Minimize?", "Minimize to system tray instead of quitting?"):
            self.root.withdraw()
            self._setup_tray()
        else:
            self._quit()

    def _quit(self):
        self.bot_mgr.stop()
        if self._tray:
            self._tray.stop()
        self.root.destroy()

    # ── Run ──────────────────────────────────────

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────
# Stdout Redirector
# ─────────────────────────────────────────────

class _StdoutRedirector:
    def __init__(self, log_fn):
        self._log = log_fn

    def write(self, text: str):
        text = text.strip()
        if text:
            self._log(text)

    def flush(self):
        pass


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    App().run()
