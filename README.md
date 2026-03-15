# 🧹 Message Cleaner

> 🍴 This is a **personally maintained fork** of the original Message Cleaner project, actively updated and improved.  
> Original project made by the [Random Python](https://discord.gg/wJEfpyd2fk) Discord community.

**Message Cleaner** is a powerful, customizable Discord bot manager that automatically deletes messages older than a specified time in selected channels. Built with a modern GUI, system tray support, and an auto-updater — it's the easiest way to keep your Discord server clean and organized.

![GUI Preview](https://media.discordapp.net/attachments/1388905295480361063/1388905894057611507/message-cleaner-gui-preview.PNG?ex=6862aee9&is=68615d69&hm=85699c9be0e2e1893e2e2c649393b52f83fb7d9cfb21ee131e541d3c8ea08af0&=&format=webp&quality=lossless)

---

## 📦 Features

| Feature | Description |
|---|---|
| 🖥️ **GUI Interface** | No command line or code editing required |
| 🔄 **Auto Cleanup** | Deletes old messages on a configurable timed interval |
| 🗂️ **Multi-Channel Support** | Target multiple channels at once |
| ⚙️ **Configurable Settings** | Easily set your token, interval, message age, and channels |
| 📜 **Log Viewer** | View and delete log files directly from the app |
| 🚨 **Update Checker** | Get notified automatically when a new version is available |
| 🧊 **Minimize to Tray** | Runs quietly in the background without cluttering your taskbar |

---

## 📥 Download

> 🖱️ **Just run the `.exe` — no installation needed!**

👉 Get the latest release from the [Releases page](https://github.com/TheServer-lab/Discord-Message-Cleaner-New/releases)

For developers or advanced users, you can also clone and run the source code directly using **Python 3.10+** (see [Developer Setup](#-developer-setup) below).

---

## ⚙️ Usage (Executable)

1. **Run** the `.exe` file
2. **Enter your settings:**
   - Your bot's Discord token
   - Channel IDs *(comma-separated)*
   - Message age threshold *(in minutes)*
   - Check interval *(in seconds)*
3. Click **Save & Start**
4. Monitor real-time logs in the app, or minimize to the system tray

**Config and log files are saved to:**
```
C:\Users\<YourName>\Documents\Random Python\Message Cleaner\
```

---

## 🛡️ Security & Token Notice

> ⚠️ **Please read before use.**

- The `update_checker` bot token is bundled in the executable solely to fetch version info via Discord. It is restricted to a **single read-only channel** and cannot be misused.
- In the source code version, this token is **fully redacted** for transparency and security.
- Your own bot token (used for message cleanup) is stored **only in your local config file** and is never transmitted or shared.

---

## 👨‍💻 Developer Setup

Clone this fork and install dependencies:

```bash
git clone https://github.com/TheServer-lab/Discord-Message-Cleaner-New.git
cd Discord-Message-Cleaner-New
pip install -r requirements.txt
python message_cleaner_gui.py
```

### Building the Executable

To compile a standalone `.exe` using PyInstaller:

```bash
pyinstaller --onefile --noconsole \
  --icon=Cleaner_icon-icons.com_53211.ico \
  --add-data "Cleaner_icon-icons.com_53211.ico;." \
  message_cleaner_gui.py
```

---

## 📜 License

Message Cleaner is released under a **custom license**. In summary:

- ✅ You **may** use, modify, and distribute the code
- ❌ You **must not** use it for malicious or illegal purposes
- 📣 You **must** give credit and notify users of any unofficial changes

See [`LICENSE.txt`](./LICENSE.txt) for full terms.

---

## ✨ Credits

Originally made with ❤️ by the **Random Python** Discord community.  
This fork is personally maintained by [@TheServer-lab](https://github.com/TheServer-lab).

Join us for help, suggestions, updates, and fun projects:

👉 **[discord.gg/wJEfpyd2fk](https://discord.gg/wJEfpyd2fk)**
