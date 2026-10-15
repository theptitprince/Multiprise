<div align="center">

# Multiprise — UDP stream splitter

**One port listened to, several programs served.**

![Version](https://img.shields.io/badge/version-3.5-2ea44f)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)
![tkinter](https://img.shields.io/badge/interface-tkinter-3776AB?logo=python&logoColor=white)
![NMEA 0183](https://img.shields.io/badge/stream-NMEA%200183%20%2F%20UDP-0a7ea4)
![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)

</div>

[Français](README.md) · **English**

> The program's interface is in French; its labels are quoted below in French (on screen they are written without accents).

---

> [!NOTE]
> **Multiprise must be alone on the input port**: the programs that used to listen on the
> gateway's port move to an outlet (4101, 4201…). **Closing the window does not quit**
> if `pystray` and `pillow` are installed: distribution carries on from the notification area, and
> only *Quitter* (Quit) stops it. On first launch, allow Python (`pythonw.exe`) or
> `Multiprise.exe` through the Windows firewall for private networks, otherwise the sockets hear
> nothing from the boat's network.

Multiprise receives a UDP stream — typically the NMEA 0183 frames that the
boat's gateway broadcasts on the network — and copies every datagram, byte
for byte, to as many destinations as you want. It shows live what comes in
and what goes out, socket by socket and destination by destination: a
silent destination is spotted immediately.

**Who it is for.** Anyone who needs several programs on the same PC to read
the same UDP stream: navigation software, polar generator
([Allure](https://github.com/theptitprince/Allure)), logger, AIS
display… On Windows, two programs cannot cleanly listen on the same UDP
port: the second one to bind to it steals the stream from the first, or
fails, and the frames reach only one of the two. Multiprise borrows the
principle of the electrical power strip (*multiprise* in French): it alone
is plugged into the wall socket (the real port, 4001 for example), and each
program plugs into one of its outlets (4101, 4201…).

```
NMEA (réseau bord) --> [4001] MULTIPRISE --> 127.0.0.1:4101     Allure
                                         --> 127.0.0.1:4201     autre outil
                                         --> 192.168.1.50:4001  autre PC
```

Current version: 3.5 — the release history is in
[CHANGELOG.md](CHANGELOG.md) (in French).

## Contents

- [1. Installation](#1-installation)
- [2. The files](#2-the-files)
- [3. Launching](#3-launching)
- [4. Getting started](#4-getting-started)
- [5. How it works](#5-how-it-works)
- [6. The interface](#6-the-interface)
- [7. What the program creates next to itself](#7-what-the-program-creates-next-to-itself)
- [8. Building an executable](#8-building-an-executable)
- [9. Troubleshooting](#9-troubleshooting)
- [10. License](#10-license)

---

## 1. Installation

### Python

You need **Python 3.8 or later**, with **tkinter**.

Install Python from <https://www.python.org/downloads/> and **check two
boxes** in the installer:

- `Add Python to PATH` (on the first screen)
- `tcl/tk and IDLE` (on the "Optional Features" screen)

Without the second one, the application cannot open: tkinter is what draws
the whole interface.

### The simplest way: `installer_dependances.bat`

Double-click **`installer_dependances.bat`**. It checks that Python (3.8 or
later) and tkinter are present — they cannot be installed with `pip`, and it
tells you what to do if they are missing — puts `pip` back in place if it
has disappeared, then installs `pystray` and `pillow` if they are absent
(this step needs an internet connection).

### By hand

To check Python, open PowerShell and type:

```powershell
python --version
python -m tkinter
```

The first command must print a version number, the second must open a
small test window — close it. Then, optionally:

```powershell
python -m pip install "pystray>=0.19" "pillow>=8.2"
```

Multiprise needs no library to distribute the streams. These two bring the
comfort of a tool that runs all the time:

| Library | What it brings | Without it |
|---|---|---|
| `pystray` + `pillow` | the close button tucks the window away next to the clock: distribution carries on, and the icon keeps an *Ouvrir* (Open) / *Quitter* menu | the close button closes the program, and cuts the stream of every program served; *Démarrer réduit* (start minimized) only minimizes to the taskbar |
| `pillow` | the icon of the window and of the taskbar, and that of `Multiprise.exe` | default icon |

With a `pystray` older than 0.19, the notification area does not work: the
close button quits (`installer_dependances.bat` updates it).

---

## 2. The files

Get the repository, whichever way you prefer:

- the green **Code → Download ZIP** button on the GitHub page, then unzip
  the archive into a folder (for example `C:\Multiprise`);
- or, if you have git:

```powershell
git clone https://github.com/theptitprince/Multiprise.git C:\Multiprise
```

| File | Role |
|---|---|
| `multiprise.py` | the program, in a single file |
| `Multiprise.bat` | launch by double-click, without a console window |
| `installer_dependances.bat` | checks Python and tkinter, installs `pystray` and `pillow` |
| `construire_exe.bat` | builds `Multiprise.exe`, standalone (see "Building an executable") |
| `CHANGELOG.md` | the version history (in French) |
| `LICENSE` | the text of the license (see "License") |
| `NOTICE` | the additional license terms (section 7): the notice to keep |

`multiprise.py` is organized in sections:

| Section | Role |
|---|---|
| `Repeater` | one thread per socket: listens on the port, copies every datagram to the active outputs (those to this PC through their own network socket, to see whether a program is listening to them) |
| `Stats` | the counters of a socket and of each of its outputs, the buffer of the latest frames |
| `App` | the main window: tables, log, notification area, saving of the settings |
| `PriseDialog`, `SortieDialog`, `SerieDialog` | the configuration of a socket, of an output, of a series of outputs |
| `MonitorWindow` | the Flux (stream) window: what passes through a socket, in plain text |
| `OptionsDialog` | the options, the rarely used actions and the *À propos* (about) section (version, origin notice, license) |

Place `multiprise.py` **in its own folder**: it keeps its configuration
there (see "What the program creates next to itself").

---

## 3. Launching

Double-click **`Multiprise.bat`**: it launches Multiprise without a console
window, and tells you what is missing if Python or tkinter is absent. Or
open PowerShell in the program's folder and type:

```powershell
python multiprise.py
```

The window opens and the sockets start listening straight away.

**The Windows firewall.** On first launch, Windows may ask you to allow
Python to communicate — `pythonw.exe`, which `Multiprise.bat` and the
launch at Windows startup use, or `python.exe` if you run the script by hand — or
`Multiprise.exe`: accept, at least for **private networks**. Each of these
programs has its own permission. Without this permission, the sockets hear
nothing of what arrives from the boat's network; only what comes from the
PC itself gets through.

**Closing the window does not quit**, if `pystray` and `pillow` are
installed: Multiprise tucks itself away next to the clock and keeps
distributing. To stop it: right-click the icon → *Quitter*, or *Options* →
*Quitter la multiprise* (Quit Multiprise). This detour is deliberate:
closing the window by mistake must not cut the stream of every program
served. Without these libraries, or if the option is unchecked, the close
button quits.

**Only one copy at a time.** Launching it again while it is already running
displays a message: the open window is in the taskbar, or tucked away next
to the clock. Two copies of Multiprise would fight over the same ports.

**With Windows.** *Options* → *Lancer au démarrage de Windows* (launch at
Windows startup) — see "Options".

---

## 4. Getting started

On first launch, the configuration is already filled in with the common
case, to be adjusted on the spot:

| Socket | Listens on | Outputs |
|---|---|---|
| NMEA 1 | port 4001 | `127.0.0.1:4101` (Allure), `127.0.0.1:4201` (autre outil — "other tool") |
| NMEA 2 | port 4003 | `127.0.0.1:4103` (Allure), `127.0.0.1:4203` (autre outil) |

1. **Free the gateway's port.** The programs that used to listen on the
   gateway's port (4001) must move to an outlet (4101, 4201…): Multiprise
   must be **alone** on the input port. As long as another program holds
   it, the socket stays red with "port déjà utilisé par un autre programme"
   (port already in use by another program); it retries on its own every
   3 seconds and takes the port as soon as it is freed.
2. **Set up the sockets.** Double-click a socket: listening port, then its
   outputs — one per program to serve.
3. **Check.** Green dot *Flux présent* (stream present) on the socket: the
   frames are arriving. In the middle table, each output switches to
   *Diffuse* (sending) and counts what it sends; an output whose program is
   not listening switches to *Injoignable* (unreachable), in red.
4. **Connect the programs.** Each one listens on the port of its output. If
   it filters the frames by sender address, it must accept `127.0.0.1`
   (or not filter, `0.0.0.0`): the sender it sees is now Multiprise, no
   longer the gateway. In Allure: *Paramètres* (Settings) → *Voies
   d'écoute* (listening channels).

---

## 5. How it works

### One socket, several outputs

A socket is a UDP port being listened to — on all of the PC's network
adapters (`0.0.0.0`, the normal case) or on the address of a single one —
and a list of outputs, each an address and a port. Each socket has its own
listening thread; every datagram received is copied to each of its active
outputs.

### Byte for byte

The datagram is copied as is, without decoding or reassembling lines:
NMEA 0183, encapsulated AIS (`!AIVDM`), binary, and even an empty
datagram — what goes in comes out identical. The text is decoded only for
display.

### Alone on the port

Multiprise binds to the input port without the sharing option
(`SO_REUSEADDR`), and exclusively: a program started after it cannot sneak
in and share the port. If another program already holds it, the bind fails
and the socket turns red with the reason. This is intended: a clear error
is better than silent sharing in which one packet in two is lost. The bind
is retried every 3 seconds: at Windows startup, a listening address (Wi-Fi,
DHCP) often appears after Multiprise, and a freed port is taken back
without any intervention.

### The sender changes

The programs served receive the frames from Multiprise: `127.0.0.1` locally,
the PC's address for an output to another machine.

### The destinations

An output can target a program on the same PC (`127.0.0.1`), another PC on
the network (`192.168.1.50:4001`, or its name), or a broadcast address of
the local network (`192.168.1.255`), broadcasting being allowed. IPv4
only. A PC name is resolved separately, without delaying the listening; if
it cannot be found (PC switched off, network not ready yet at Windows
startup), it is retried every 30 seconds.

### A failing output does not disturb the others

A send that fails is counted in *Échecs* (failures) and ignored: shutting
down a client program never cuts the stream of the others, and a PC name
that cannot be found does not slow the socket down.

### Seeing that a program is no longer listening

When no program on the PC is listening on the port of an output, Windows
sends back a refusal, which Multiprise collects: the output switches to
*Injoignable*, then back to *Diffuse* as soon as the program listens again.
Windows limits the number of refusals it reports per second: the output
stays red for 2 seconds after the last one. For an output to another PC,
the absence of a program cannot be seen.

### Loops

An output that sent back to an input port of Multiprise would make the
datagrams go round in circles until the machine was saturated.

- To the input of **its own socket** (`127.0.0.1`, the PC's address or
  name, or a broadcast of its network, on the port being listened to): the
  configuration of a socket refuses it; if it is enabled from the outputs
  table or a hand-edited file, it is never sent and is shown as *Boucle*
  (loop).
- **Between sockets** (A sends back to B, which sends back to A): these
  sockets are not started, and the log says so.
- **A merge is not a loop**: two sockets that feed a third one (GPS and AIS
  to a "Fusion" socket that serves the programs) work normally.

### Bursts

A 1 MB receive buffer per socket absorbs bursts (a busy AIS stream, for
example).

### Every change is applied immediately

Create, edit, check or uncheck: the configuration is saved, listening is
restarted and the counters start again from zero, with a break in the
stream of at most a tenth of a second. There is no such thing as a setting
that is displayed but not applied. **F5** restarts listening without
changing anything.

---

## 6. The interface

Three stacked areas — the sockets, their outputs, the log — separated by
draggable handles; their positions and the size of the window are
remembered from one launch to the next (if the screen of the last session
is no longer connected, the window gets its size back and Windows places
it). In the top bar: *+ Nouvelle prise* (new socket), *Sorties en série*
(series of outputs), *Configurer* (configure), *Flux*, *Options*.

### The sockets table

On the left of each row, a colored dot and a checkbox: a click on the
checkbox puts the socket in or out of service. Then *État* (state),
*Prise* (socket), *Écoute* (listening: address and port), *Débit* (rate:
datagrams per second, averaged over 2 s), *Reçu* (received), *Réémis*
(re-sent: sends, all outputs combined) and *Dernière trame* (last frame).

| State | Dot | Meaning |
|---|---|---|
| Flux présent | green | a frame received less than 3 s ago |
| Aucune trame (no frames) | orange | listening, nothing received for 3 s |
| Démarrage (starting) | orange | listening is being set up (a moment, after each change) |
| Erreur (error) | red | bind impossible or reception interrupted (new attempt every 3 s), or loop between sockets; the message is in the log |
| Hors service (out of service) | gray | checkbox unchecked |
| Non démarrée (not started) | gray | socket without a valid port |

Right-click a socket: *Configurer…*, *Sorties en série…*, *Voir le
flux…* (view the stream), *Activer / désactiver* (enable / disable),
*Supprimer* (delete).

### The outputs table

The outputs of the selected socket, each with **its own counters**:
*État*, *Adresse* (address), *Port*, *Libellé* (label), *Envoyés* (sent),
*Échecs*. The checkbox on the left enables or disables the output without
opening the configuration; a double-click opens the configuration of the
socket, with this output already selected.

| State | Dot | Meaning |
|---|---|---|
| Diffuse | green | the last datagram went out to this destination |
| En attente (waiting) | orange | nothing to send for now: the socket has received nothing |
| Injoignable | red | the last send failed, or a refusal arrived less than 2 s ago: no program on this PC is listening on this port, PC name not found, network absent |
| Boucle | red | the output sends back to the input of its own socket: it is never sent |
| Inactive | gray | checkbox unchecked, or socket out of service or in error |

The state follows the **last** send: an output that starts failing turns
red, and turns green again as soon as its program listens again.

### The log

Time-stamped, it reads like a history: startup, start of listening, arrival
and loss of the stream ("plus aucune trame reçue", meaning no more frames
received, after 10 s of silence, so as not to raise an alert at every pause
of a slow source such as AIS at anchor), errors, setting changes,
configuration problems (sockets on the same port, loops, duplicate outputs).
It keeps the last 3,000 lines and does not move when you change the
selection; scrolled up to read an old line, it stays there. *Effacer*
(clear) empties it.

The **trames de la prise sélectionnée** (frames of the selected socket)
checkbox also copies the frames of the selected socket into it, at most
20 datagrams per half-second: beyond that, a line says how many were not
displayed. To see everything, the Flux window is made for that.

### Sorting

A click on a column heading sorts: ascending, then descending, then back to
the order of the configuration on the third click. Counters and rates sort
as numbers; *État* by severity, problems at the top. While the pointer is
over the table, the rows do not move: a click on a checkbox always hits the
socket you see.

### Configuring a socket

*Nom* (name), *Adresse d'écoute* (listening address; `0.0.0.0` = all of the
PC's adapters, the normal case, or the IPv4 address of a single one),
*Port*, *Prise en service* (socket in service); then its outputs:
*+ Ajouter* (add), *+ En série…* (in series), *Modifier* (edit, or
double-click), *Activer / désactiver*, *Supprimer* (or **Delete**).
*Enregistrer* (save) refuses an invalid port, an invalid address (only
digits, letters, dots and hyphens are accepted — a copied address sometimes
carries an invisible character along with it), a duplicate output, and an
output to the input of the socket itself.

### Series of outputs

To create N distribution ports in one go (4101, 4102, 4103…): *Adresse
commune* (common address), *Port de départ* (starting port; by default,
listening port + 100), *Nombre* (count; up to 200), *Pas* (step), and a
*Libellé* numbered automatically ("Sortie 1", "Sortie 2"…, that is
Output 1, Output 2…). The preview shows, at each keystroke, exactly what
will be created; the ports left out appear in orange with the reason: out
of range, input of the socket (loop), already present. Available from the
top bar (**Ctrl+S**, on the selected socket) or from the configuration of a
socket.

### The Flux window

**Ctrl+M**, the *Flux* button or right-click → *Voir le flux…*: what passes
through a socket, in plain text and live, one window per socket. It follows
its socket: if the socket is renamed or moved to another port, the title
follows; if it is deleted, the window closes; if it is out of service, the
window says so.

- *Pause* / *Reprendre* (resume), *Effacer*, *Enregistrer…* (`.log` or
  `.txt` file);
- *Filtre* (filter): shows only the lines that contain the text typed,
  case-insensitively (`RMC`, `VDM`…);
- *suivre* (follow: automatic scrolling), *heure* (time: time stamp to the
  millisecond), *source* (address of the sender).

The bottom line gives the listening state, the datagrams received and
re-sent, and the send failures if there are any. The window rereads the
buffer of the socket's last 2,000 frames, without ever touching the path of
the frames: an open Flux window can neither slow down nor block the
distribution, even on a fast stream.

### Options

- **La croix range dans la zone de notification** (the close button puts
  the window in the notification area) — see "Launching".
- **Démarrer réduit**: the window is tucked away next to the clock right
  from launch (with `pystray` and `pillow`; without them, it is minimized
  to the taskbar).
- **Lancer au démarrage de Windows**: puts `Multiprise NMEA.bat` in the
  Windows Startup folder
  (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`) — no
  registry entry, a file you can see and delete by hand. It launches Multiprise
  without a console window and accepts paths with accented characters. At
  each launch, it is rewritten to point to the copy launched (script or
  exe, moved folder); deleted by hand, it is not recreated and the checkbox
  gets unchecked. Disabled in Task Manager (*Startup* tab), it stays in
  place and the checkbox stays checked: uncheck it in Multiprise too.
- **Journal : afficher les trames de la prise sélectionnée** (log: show the
  frames of the selected socket) — see "The log".

Two actions: *Relancer l'écoute (F5)* (restart listening) and *Quitter la
multiprise*.

The window is titled *Options et à propos* (options and about): its
**À propos** section gives the version, the origin notice "Multiprise, par
ETDEL — https://github.com/theptitprince/Multiprise" (a click opens the
repository page), the copyright, the license (GPL v3 or later, with the
additional terms of the `NOTICE` file), the absence of warranty, and the
addresses where the license and these terms can be read: `Multiprise.exe`,
copied alone, has neither `LICENSE` nor `NOTICE` next to it. The same
notice is written in the log at each startup (see "License").

### Keyboard shortcuts

| Key | Action |
|---|---|
| **Ctrl+N** | new socket |
| **Ctrl+S** | series of outputs on the selected socket |
| **Ctrl+M** | Flux window of the selected socket |
| **F5** | restart listening |
| **Enter** or double-click | configure the socket |
| **Space** | put the socket in or out of service |
| **Delete** | delete the socket, after confirmation |
| **Esc** | close a secondary window |

---

## 7. What the program creates next to itself

| File | Contents |
|---|---|
| `multiprise_config.json` | sockets, outputs, options, size of the window and position of the dividers. **Copy it to back up your configuration.** Rename it to start again from the initial configuration. |
| `multiprise_config.json.tmp` | temporary file: the configuration is written alongside, flushed to disk, then replaces the old one in a single step — a power cut cannot leave it half-written. |
| `multiprise_config.json.illisible` | only if the configuration could not be read back (see "Troubleshooting"): the original file, set aside before it is replaced (`.illisible2`, `.illisible3`… if a copy already exists). |

Outside the folder, only if the option is checked:
`Multiprise NMEA.bat` in the Windows Startup folder.

The folder must be **writable** (not `Program Files`): otherwise, the
configuration is not saved and the log reports it
("réglages non enregistrés", meaning settings not saved).

---

## 8. Building an executable

A standalone executable avoids having to install Python on the machine that
uses it. Double-click **`construire_exe.bat`**, in the folder of
`multiprise.py`; it:

1. finds the computer's Python (3.8 or later);
2. checks tkinter, and detects `pystray` and `pillow` — bundled if they are
   installed, otherwise the exe has neither notification area nor icon (run
   `installer_dependances.bat` first);
3. installs PyInstaller if it is missing (that is the only download);
4. draws the Multiprise icon;
5. packages, then puts `Multiprise.exe` **next to `multiprise.py`**.

Allow from a few tens of seconds to a few minutes. Result:
`Multiprise.exe`, about 20 MB. It keeps its configuration next to itself:
placed next to `multiprise.py`, it shares the script's configuration (only
one of the two at a time). For another computer, copy it alone into its own
folder.

- **Firewall**: allow `Multiprise.exe` on first launch (private network).
  The firewall authorizes an executable, not a program: a permission given
  to `python.exe` does not apply to it.
- **SmartScreen**: the exe is not signed, Windows may display a warning →
  *More info* → *Run anyway*.
- **Antivirus**: an overzealous antivirus can block PyInstaller; it is the
  most frequent cause of failure.

By hand, the same steps:

```powershell
python -m pip install pyinstaller "pystray>=0.19" "pillow>=8.2"
```

```powershell
python -c "import multiprise; multiprise.write_ico('multiprise.ico')"
```

```powershell
python -m PyInstaller --onefile --windowed --name Multiprise --icon multiprise.ico --exclude-module numpy --hidden-import pystray._win32 --hidden-import PIL._tkinter_finder multiprise.py
```

The result is in `dist\`. The `build\` and `dist\` folders and the
`Multiprise.spec` file can then be deleted.

---

## 9. Troubleshooting

**"port déjà utilisé par un autre programme"** — another program is still
listening on the input port, often the navigation software left set to the
gateway's port. Move it to an outlet: Multiprise takes the port back on its
own within 3 seconds. To find out who holds the port (here 4001), in
PowerShell:

```powershell
Get-Process -Id (Get-NetUDPEndpoint -LocalPort 4001).OwningProcess
```

**"adresse d'écoute inexistante sur cette machine"** (listening address does
not exist on this machine) — the listening address of the socket is not
that of any network adapter of the PC (address changed, adapter unplugged,
Wi-Fi not connected yet). Multiprise retries every 3 seconds; if the
address does not come back, set `0.0.0.0`.

**"port interdit"** (port forbidden) — Windows reserves this port (ranges
reserved by Hyper-V, WSL2 or Docker, visible with
`netsh int ipv4 show excludedportrange protocol=udp`), or another program
holds it exclusively. Choose another port.

**"adresse d'écoute illisible"** (unreadable listening address) — the
address contains an invisible or non-ASCII character, often carried along
when copying it from a document. Retype it.

**The socket stays on "Aucune trame"** — nothing arrives. In order: is the
gateway transmitting, and to this port? Is the PC on the right network?
Does the Windows firewall let the stream in for `pythonw.exe` (or
`python.exe`, or `Multiprise.exe`, depending on what launches Multiprise)?
Is the listening address `0.0.0.0`?

**The output is "Injoignable"** — no program is listening on its port (the
program is closed, or set to another port), its PC name cannot be found, or
the network is absent. Start or set up the program: the output goes back to
*Diffuse* on its own. A PC name that cannot be found is retried every
30 seconds.

**The output is "Diffuse" but the program receives nothing** — the program
filters the frames by sender address: it must accept `127.0.0.1`. For an
output to another PC, that PC's firewall can also block the incoming
traffic without sending anything back. The Flux window of the socket shows
what comes in, and therefore what goes out.

**The log reports a loop, or an output is "Boucle"** — an output sends back
to the input port of a socket on this PC: correct its port. An output to
its own socket is never sent; sockets that send the stream back to each
other are not started.

**"Multiprise NMEA tourne déjà"** (Multiprise NMEA is already running) — the
other copy is in the taskbar or tucked away next to the clock
(`Multiprise.exe` and `multiprise.py` count as one: only one of the two at
a time).

**"No module named tkinter"** — Python was installed without tcl/tk. Run
the installer again, choose *Modify*, and check `tcl/tk and IDLE`.

**"configuration impossible à lire"** (configuration cannot be read) — the
file is locked by another program or protected (permissions): Multiprise
starts with no socket and does not overwrite it. Close whatever is holding
it, then restart.

**"configuration illisible"** (unreadable configuration) — the
configuration file has been damaged or edited by hand with a mistake.
Multiprise does not replace it silently: it sets it aside as
`multiprise_config.json.illisible`, starts with no socket and writes this
in the log. Fix the file set aside and rename it to
`multiprise_config.json` (with Multiprise closed), or recreate your
sockets. A value of an unexpected type (a number instead of a list, for
example) is simply replaced by its default value.

---

## 10. License

Multiprise is **free software**, distributed under the
**GNU General Public License, version 3 or later** (GPL-3.0-or-later).

Copyright © 2026 ETDEL.

In practice, you may use the program freely, including on board and in a
professional setting, study it, modify it and redistribute it — provided
that any redistributed version, modified or not, remains under the same
license, with its source code and the copyright notice. The program is
provided **without any warranty**: it distributes the frames it receives;
it replaces neither your vigilance nor your navigation instruments.

### Additional terms (section 7)

The GPL v3 lets the author add a few terms (section 7). Multiprise's are in the
[`NOTICE`](NOTICE) file, in French and in English:

- **Attribution**: every copy or modified version must keep, visible to the user (an "About"
  window or equivalent) and in its documentation, the notice:

  > Multiprise, par ETDEL — https://github.com/theptitprince/Multiprise

  A modified version may prefix it with "D'après" (or "Based on") and add its own credits,
  but may neither remove nor hide it.
- **Origin**: a modified version must state clearly that it has been modified, and must not
  present itself as the original or as endorsed by ETDEL.

In Multiprise, this notice is shown in the *Options* window (*A propos* section) and in the log at startup.

The full text of the license is in the `LICENSE` file of the repository and
at <https://www.gnu.org/licenses/gpl-3.0.html>. Each source file
(`multiprise.py` and the three `.bat` files) carries a header that points
to `LICENSE` and `NOTICE`.

---

*Multiprise — ETDEL 2026 — GPL-3.0-or-later*
