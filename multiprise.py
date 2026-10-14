# Multiprise -- repartiteur de flux UDP (NMEA 0183) pour Windows
# Copyright (C) 2026 ETDEL
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le
# modifier selon les termes de la GNU General Public License telle que
# publiee par la Free Software Foundation, soit la version 3 de la licence,
# soit (a votre choix) toute version ulterieure.
#
# Ce programme est distribue dans l'espoir qu'il sera utile, mais SANS
# AUCUNE GARANTIE, sans meme la garantie implicite de QUALITE MARCHANDE ou
# d'ADEQUATION A UN USAGE PARTICULIER. Voir la GNU General Public License
# pour plus de details.
#
# Vous devriez avoir recu une copie de la GNU General Public License avec ce
# programme (fichier LICENSE). Sinon, voir <https://www.gnu.org/licenses/>.
"""
multiprise.py -- "Multiprise NMEA"
==================================
Repartiteur (fanout) de flux UDP : ecoute UN port, et reexpedie CHAQUE
datagramme recu, tel quel, vers AUTANT de destinations que voulu.

Le probleme resolu
------------------
Deux programmes ne peuvent pas ecouter proprement le meme port UDP sur la
meme machine : sous Windows, le second qui se lie au port vole le flux au
premier (ou echoue), et les trames n'arrivent qu'a un seul des deux. La
multiprise reprend le principe de la multiprise electrique : elle seule est
branchee sur la prise murale (le vrai port, 4001 par exemple), et chaque
programme se branche sur une prise fille (4101, 4201...).

    NMEA (reseau bord) --> [4001] MULTIPRISE --> 127.0.0.1:4101  Allure
                                             --> 127.0.0.1:4201  autre outil
                                             --> 192.168.1.50:4001  autre PC

Interface (v3)
--------------
- TABLEAU DES PRISES en haut : etat, nom, adresse ecoutee, debit,
  datagrammes recus et reemis, derniere trame vue.
- TABLEAU DES SORTIES au milieu : les destinations de la prise
  selectionnee, chacune avec SES PROPRES compteurs (envoyes / echecs). Un
  programme du meme PC qui n'ecoute pas (ferme, plante, mal regle) fait
  passer sa sortie au rouge : Windows renvoie un refus, que la multiprise
  recueille (il en limite le nombre par seconde : la sortie reste rouge 2 s
  apres le dernier). Vers un autre PC, l'absence d'un programme ne se voit
  pas.
- JOURNAL en bas : liaisons, pertes de flux, erreurs, modifications de
  reglage -- horodate, et conserve meme quand on change de selection.
- SORTIES EN SERIE : creation de N ports de diffusion d'un coup
  (4101, 4102, 4103...), au lieu de les saisir un par un.
- Les trois zones sont separees par des poignees deplacables : chacun met
  le journal a la hauteur qu'il veut.

Points d'attention
------------------
1. LA MULTIPRISE DOIT ETRE SEULE sur le port d'entree. Si un autre
   programme ecoute encore 4001, la liaison echoue et la ligne passe en
   rouge avec le motif ("port deja utilise...") -- c'est voulu : mieux vaut
   une erreur franche qu'un partage silencieux ou un paquet sur deux se
   perd. La liaison est retentee toutes les 3 s : des que le port se
   libere, la prise le prend.

2. L'EXPEDITEUR VU PAR LES CLIENTS DEVIENT LA MULTIPRISE (127.0.0.1 en
   local). Un client qui filtre par IP source doit accepter 127.0.0.1, ou
   ne pas filtrer (0.0.0.0). Dans Allure : Parametres -> Voies d'ecoute.

3. LE DATAGRAMME EST RECOPIE OCTET POUR OCTET, sans decodage ni
   recomposition de lignes : ce qui entre sort a l'identique, quel que
   soit le contenu (NMEA 0183, AIS encapsule, binaire).

Aucune dependance obligatoire : bibliotheque standard + Tkinter.
    python -m pip install "pystray>=0.19" "pillow>=8.2"
(ou installer_dependances.bat) ajoute la reduction dans la zone de
notification (la croix range l'outil au lieu de le fermer) et l'icone ;
sans ces modules, la croix ferme normalement.

Lancement : double-clic sur Multiprise.bat, ou

    python multiprise.py

construire_exe.bat en fait un Multiprise.exe autonome (PyInstaller), qui
range sa configuration a cote de lui-meme. Le numero de version vit dans
APP_VERSION ; l'historique des livraisons, dans CHANGELOG.md.

Multiprise -- ETDEL 2026
"""

import json
import os
import re
import socket
import sys
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import ttk, messagebox, filedialog

APP_TITLE = "Multiprise NMEA"
APP_VERSION = "3.4"

# En exe autonome (PyInstaller), __file__ designe le dossier TEMPORAIRE ou
# l'exe se deballe a chaque lancement, et qui est efface a la fermeture : la
# configuration y serait perdue a chaque sortie. La reference est alors
# l'executable lui-meme, la configuration nait a cote de Multiprise.exe.
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "multiprise_config.json")

# Verrou d'instance unique, sous Windows : un mutex nomme (voir
# acquire_single_instance). Hors Windows, repli sur un port de bouclage
# (sous la plage dynamique de Windows, 49152-65535).
MUTEX_NAME = "Local\\MultipriseNMEA"
SINGLE_INSTANCE_PORT = 47922

MAX_DATAGRAM = 65535   # taille maximale d'un datagramme UDP
RCVBUF = 1 << 20       # 1 Mo de tampon de reception : encaisse les rafales
MONITOR_DEPTH = 2000   # trames gardees en memoire par prise
JOURNAL_LINES = 3000   # lignes gardees dans le journal


# =========================================================================
# Theme sombre
# =========================================================================

BG_APP = "#12161c"
BG_PANEL = "#1c222a"
BG_NAV = "#232b35"
BG_FIELD = "#161b22"
BG_HOVER = "#2b3542"
FG_LABEL = "#d3dbe4"
FG_DIM = "#8b99a8"
ACCENT = "#2f6fc4"
ACCENT_HOVER = "#3d82dc"
BORDER = "#333d49"
COLOR_OK = "#4caf50"
COLOR_WARN = "#e8a04a"
COLOR_ERR = "#e05e5e"
COLOR_IDLE = "#5a6673"

PAD_X = 18          # marge laterale commune a toutes les sections

# Cases a cocher dessinees en caracteres : Segoe UI les rend correctement
# sous Windows, et cela evite deux images de plus a fabriquer.
COCHE = "\u2611"
NON_COCHE = "\u2610"

FONT = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 9, "bold")
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_MONO = ("Consolas", 9)
FONT_MONO_S = ("Consolas", 8)
FONT_SMALL = ("Segoe UI", 8)


def setup_style(root):
    """Habillage sombre des widgets ttk.

    Le theme 'clam' est impose : c'est le seul theme ttk portable dont les
    couleurs de fond soient reellement reglables. Avec le theme natif de
    Windows, les tableaux resteraient blancs quoi qu'on demande, et on se
    retrouverait avec deux ilots eblouissants au milieu d'une interface
    sombre."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Treeview", background=BG_PANEL, fieldbackground=BG_PANEL,
                    foreground=FG_LABEL, rowheight=28, borderwidth=0, font=FONT)
    style.configure("Treeview.Heading", background=BG_NAV, foreground=FG_DIM,
                    relief="flat", borderwidth=0, font=FONT_BOLD, padding=(8, 6))
    style.map("Treeview.Heading", background=[("active", BG_HOVER)],
              foreground=[("active", FG_LABEL)])
    style.map("Treeview", background=[("selected", ACCENT)],
              foreground=[("selected", "#ffffff")])
    for name in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(name, background=BG_NAV, troughcolor=BG_APP,
                        bordercolor=BG_APP, arrowcolor=FG_DIM,
                        darkcolor=BG_NAV, lightcolor=BG_NAV, relief="flat")
        style.map(name, background=[("active", BG_HOVER)])
    style.configure("TSeparator", background=BORDER)
    style.configure("TPanedwindow", background=BG_APP)
    style.configure("Sash", sashthickness=6, gripcount=0)
    return style


# =========================================================================
# Configuration
# =========================================================================

def default_config():
    """Configuration de premier lancement -- deja remplie avec le cas
    courant (deux flux NMEA, deux consommateurs), a ajuster sur place."""
    return {
        "prises": [
            {"nom": "NMEA 1", "ecoute_ip": "0.0.0.0", "port": 4001, "actif": True,
             "sorties": [
                 {"nom": "Allure", "ip": "127.0.0.1", "port": 4101, "actif": True},
                 {"nom": "Autre outil", "ip": "127.0.0.1", "port": 4201, "actif": True}]},
            {"nom": "NMEA 2", "ecoute_ip": "0.0.0.0", "port": 4003, "actif": True,
             "sorties": [
                 {"nom": "Allure", "ip": "127.0.0.1", "port": 4103, "actif": True},
                 {"nom": "Autre outil", "ip": "127.0.0.1", "port": 4203, "actif": True}]},
        ],
        "close_to_tray": True,
        "start_minimized": False,
        "autostart": False,
        "journal_trames": False,
        "geometry": "",
        "sashes": [],
        "app_version": APP_VERSION,
    }


def load_config():
    """Lit la configuration. Fichier absent : configuration de depart. La
    multiprise doit toujours demarrer : une valeur de type inattendu
    (fichier retouche a la main) est remplacee par sa valeur par defaut,
    champ par champ.

    Un fichier PRESENT mais illisible (JSON casse) n'est jamais remplace en
    silence : il est mis de cote sous multiprise_config.json.illisible
    AVANT que le premier enregistrement ne l'ecrase, la multiprise demarre
    sans prise, et le journal le dit (cle "_alerte", lue par App)."""
    try:
        # utf-8-sig : accepte aussi le BOM qu'ajoutent certains editeurs
        # (Bloc-notes ancien, PowerShell 5.1) et que json refuse.
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as fh:
            texte = fh.read()
    except FileNotFoundError:
        return default_config()
    except OSError as e:
        # Fichier present mais pas lisible maintenant (droits, verrou d'un
        # autre programme) : il n'est pas abime, on ne le touche pas.
        cfg = default_config()
        cfg["prises"] = []
        cfg["_alerte"] = (f"configuration impossible a lire ({e}) : la multiprise "
                          "demarre sans prise et ne l'enregistrera pas")
        cfg["_ne_pas_enregistrer"] = True
        return cfg
    try:
        raw = json.loads(texte)
        if not isinstance(raw, dict):
            raise ValueError("le fichier ne contient pas un objet JSON")
    except ValueError as e:
        cfg = default_config()
        cfg["prises"] = []
        try:
            # Une copie mise de cote plus tot n'est pas ecrasee.
            cote = CONFIG_PATH + ".illisible"
            n = 2
            while os.path.exists(cote):
                cote = f"{CONFIG_PATH}.illisible{n}"
                n += 1
            os.replace(CONFIG_PATH, cote)
            cfg["_alerte"] = (f"configuration illisible ({e}) : mise de cote sous "
                              f"{os.path.basename(cote)}, la multiprise demarre sans prise")
        except OSError as e2:
            # Impossible de la mettre de cote : on ne l'ecrasera pas non plus.
            cfg["_alerte"] = (f"configuration illisible ({e}), non mise de cote "
                              f"({e2}) : elle ne sera pas enregistree")
            cfg["_ne_pas_enregistrer"] = True
        return cfg

    cfg = default_config()
    cfg["close_to_tray"] = _as_bool(raw.get("close_to_tray"), True)
    cfg["start_minimized"] = _as_bool(raw.get("start_minimized"), False)
    cfg["autostart"] = _as_bool(raw.get("autostart"), False)
    cfg["journal_trames"] = _as_bool(raw.get("journal_trames"), False)
    geo = raw.get("geometry")
    cfg["geometry"] = geo if isinstance(geo, str) else ""
    # Entiers JSON seulement : int() sur null, "x" ou Infinity leverait.
    cfg["sashes"] = [s for s in _as_list(raw.get("sashes"))
                     if isinstance(s, int) and not isinstance(s, bool)]

    prises = []
    for p in _as_list(raw.get("prises")):
        if not isinstance(p, dict):
            continue
        sorties = []
        for s in _as_list(p.get("sorties")):
            if not isinstance(s, dict):
                continue
            sorties.append({"nom": _as_str(s.get("nom"), ""),
                            "ip": _as_str(s.get("ip"), "127.0.0.1"),
                            "port": _as_port(s.get("port"), 0),
                            "actif": _as_bool(s.get("actif"), True)})
        prises.append({"nom": _as_str(p.get("nom"), "Prise"),
                       "ecoute_ip": _as_str(p.get("ecoute_ip"), "0.0.0.0"),
                       "port": _as_port(p.get("port"), 0),
                       "actif": _as_bool(p.get("actif"), True),
                       "sorties": sorties})
    cfg["prises"] = prises
    return cfg


def save_config(cfg):
    """Ecriture atomique : fichier temporaire puis remplacement. Une coupure
    en cours d'ecriture ne peut pas laisser une configuration a moitie
    ecrite (et donc illisible au prochain lancement) : le fichier est force
    sur le disque avant de remplacer l'ancien."""
    if cfg.get("_ne_pas_enregistrer"):
        raise OSError("le fichier de configuration illisible est conserve tel quel")
    tmp = CONFIG_PATH + ".tmp"
    data = {k: v for k, v in cfg.items() if not k.startswith("_")}
    data["app_version"] = APP_VERSION
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
    except (ValueError, TypeError) as e:
        # Valeur impossible a ecrire (texte mal encode) : traitee comme une
        # erreur d'enregistrement ordinaire, jamais fatale.
        raise OSError(f"configuration non enregistrable : {e}")
    os.replace(tmp, CONFIG_PATH)


def _as_list(value):
    """Une liste attendue dans le fichier -- n'importe quoi d'autre (fichier
    retouche a la main) compte pour une liste vide."""
    return value if isinstance(value, list) else []


def _as_bool(value, defaut):
    """Booleen lu dans le fichier : "false" ou "0" ecrits a la main ne
    doivent pas valoir True, comme le ferait bool("false")."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "oui", "vrai", "yes"):
            return True
        if v in ("false", "0", "non", "faux", "no"):
            return False
        return defaut
    if isinstance(value, (int, float)):
        return bool(value)
    return defaut


def _as_str(value, defaut):
    """Texte lu dans le fichier : null ne doit pas devenir "None", et un
    caractere mal code (echappement unicode tronque) devient "?" plutot que
    d'empecher tout enregistrement."""
    if value is None:
        return defaut
    value = value if isinstance(value, str) else str(value)
    return value.encode("utf-8", "replace").decode("utf-8")


def _as_port(value, fallback=0):
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    return n if 1 <= n <= 65535 else fallback


# =========================================================================
# Repetiteur : un fil par prise
# =========================================================================

class Stats:
    """Compteurs et memoire tampon d'une prise.

    Les compteurs sont de simples entiers, ecrits par le seul fil de la
    prise et lus par la boucle Tk : un seul ecrivain par compteur, aucun
    verrou n'est necessaire sur le chemin des trames. Seule la file des
    trames est protegee, parce qu'une lecture pendant une ecriture peut,
    elle, echouer."""

    def __init__(self):
        self.rx = 0
        self.rx_bytes = 0
        self.tx = 0
        self.tx_err = 0
        self.last_rx = 0.0
        self.last_line = ""
        self.error = ""
        self.running = False
        self.seq = 0
        self.debut = time.time()
        # Compteurs PAR SORTIE, indexes comme dans la configuration :
        # [envoyes, echecs, dernier envoi, dernier refus, boucle] -- dernier
        # envoi : None (rien encore), True (parti), False (echoue) ; dernier
        # refus : instant (time.monotonic) du dernier "aucun programme
        # n'ecoute" ; boucle : la sortie revient sur l'entree, jamais emise.
        # C'est ce qui permet de voir qu'une destination precise ne recoit
        # rien alors que les autres sont servies, et qu'elle s'est remise a
        # recevoir.
        self.per_out = {}
        self._lock = threading.Lock()
        self._trames = deque(maxlen=MONITOR_DEPTH)

    def push(self, t, src, texte):
        with self._lock:
            self.seq += 1
            self._trames.append((self.seq, t, src, texte))

    def since(self, seq):
        """Trames arrivees APRES le numero d'ordre donne. Le lecteur retient
        le dernier numero affiche : il ne reaffiche donc jamais deux fois la
        meme trame, meme si le tampon a tourne entre-temps."""
        with self._lock:
            return [x for x in self._trames if x[0] > seq]


class _Sortie:
    """Une destination d'une prise, vue de son fil : adresse numerique (None
    tant que le nom n'est pas resolu), socket connectee (destinations de ce
    PC seulement), nom introuvable, boucle detectee apres resolution."""

    __slots__ = ("idx", "ip", "port", "num", "sock", "introuvable", "boucle")

    def __init__(self, idx, ip, port):
        self.idx, self.ip, self.port = idx, ip, port
        self.num = None
        self.sock = None
        self.introuvable = False
        self.boucle = False


class Repeater(threading.Thread):
    """Ecoute un port UDP et recopie chaque datagramme vers ses sorties.

    Ce fil ne doit jamais mourir sur une erreur d'emission : une sortie
    injoignable (programme client eteint, nom introuvable, reseau absent)
    est comptee puis ignoree, sans quoi l'extinction d'un client couterait
    le flux de tous les autres.

    Une sortie vers CE PC a sa propre socket, connectee a sa destination :
    c'est le seul moyen, sous Windows, d'apprendre qu'aucun programme
    n'ecoute en face -- le refus (ICMP "port injoignable") ne revient que sur
    une socket connectee. Les sorties vers d'autres PC passent par la socket
    commune : elle suit les changements d'adresse ou de carte reseau, et le
    refus d'un autre PC n'arrive de toute facon que si son pare-feu le
    laisse partir."""

    # Delai de reception : borne le temps d'arret du fil (et donc la coupure
    # du flux pendant une relance), pour un reveil a vide 10 fois par seconde.
    ATTENTE = 0.1
    # Liaison impossible (port tenu par un autre programme, adresse pas
    # encore attribuee au demarrage de Windows), reception interrompue :
    # nouvel essai a ce rythme.
    REESSAI = 3.0
    # Nom de sortie introuvable (PC eteint, reseau pas pret) : nouvel essai.
    REESSAI_NOM = 30.0
    # Windows limite le nombre de refus qu'il signale par seconde : une
    # sortie reste rouge ce temps apres le dernier refus.
    MEMOIRE_REFUS = 2.0

    def __init__(self, prise, stats):
        super().__init__(daemon=True, name=f"Prise-{prise.get('port')}")
        self.bind_ip = (prise.get("ecoute_ip") or "0.0.0.0").strip() or "0.0.0.0"
        self.port = int(prise.get("port") or 0)
        self.targets = []
        for idx, s in enumerate(prise.get("sorties", [])):
            if not (s.get("actif") and s.get("ip") and s.get("port")):
                continue
            ip, port = s["ip"].strip(), int(s["port"])
            stats.per_out[idx] = [0, 0, None, 0.0, False]
            if _vers_entree(ip, port, self.bind_ip, self.port):
                # Sortie vers l'entree de cette meme prise : jamais emise, les
                # datagrammes tourneraient en rond jusqu'a saturer la machine
                # (affichee "Boucle" dans le tableau des sorties).
                stats.per_out[idx][4] = True
                continue
            self.targets.append((ip, port, idx))
        self.stats = stats
        self._running = threading.Event()
        self._running.set()
        self._sock = None
        self._out = None

    def run(self):
        sorties = [_Sortie(idx, ip, port) for ip, port, idx in self.targets]
        try:
            self._out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._out.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Adresses numeriques installees tout de suite ; les noms sont
            # resolus par un fil a part : un nom introuvable (PC eteint, faute
            # de frappe) coute une a plusieurs secondes, l'ecoute ne doit pas
            # les attendre.
            noms = []
            for so in sorties:
                if _IPV4_RE.match(so.ip):
                    self._installer(so, so.ip)
                else:
                    noms.append(so)
            if noms:
                threading.Thread(target=self._resoudre, args=(noms,), daemon=True,
                                 name=f"Noms-{self.port}").start()
            while self._running.is_set():
                if not self._lier():
                    if not self._attendre(self.REESSAI):
                        return
                    continue
                self.stats.error = ""
                self.stats.running = True
                self._boucle(sorties)
                self.stats.running = False
                self._close()
                # Reception interrompue : l'erreur reste affichee, nouvel essai.
                if self._running.is_set() and not self._attendre(self.REESSAI):
                    return
        except Exception as e:   # filet : un fil ne meurt jamais en silence
            self.stats.error = f"erreur interne : {e}"
        finally:
            self.stats.running = False
            for so in sorties:
                if so.sock is not None:
                    try:
                        so.sock.close()
                    except OSError:
                        pass
            if self._out is not None:
                try:
                    self._out.close()
                except OSError:
                    pass
            self._close()

    def _lier(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # PAS de SO_REUSEADDR sur l'entree : on VEUT que la liaison
            # echoue bruyamment si un autre programme tient deja le port,
            # c'est exactement le probleme que cet outil resout. Et sous
            # Windows, l'exclusivite : un programme lance APRES ne peut pas
            # venir partager le port en douce.
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                try:
                    self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                except OSError:
                    pass
            try:
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RCVBUF)
            except OSError:
                pass
            self._sock.bind((self.bind_ip, self.port))
            self._sock.settimeout(self.ATTENTE)
            return True
        except (OSError, ValueError, TypeError) as e:
            # ValueError / TypeError : adresse d'ecoute illisible (caractere
            # invisible colle avec l'adresse) -- sans cela le fil mourrait.
            self.stats.error = _explain_bind_error(e)
            self.stats.running = False
            self._close()
            return False

    def _attendre(self, duree):
        """Attente decoupee : False si la prise est arretee entre-temps (la
        relance n'attend un fil qu'une seconde). Horloge monotone : une mise
        a l'heure du PC ne doit pas la prolonger."""
        fin = time.monotonic() + duree
        while time.monotonic() < fin:
            if not self._running.is_set():
                return False
            time.sleep(0.2)
        return self._running.is_set()

    def _boucle(self, sorties):
        while self._running.is_set():
            try:
                payload, addr = self._sock.recvfrom(MAX_DATAGRAM)
            except socket.timeout:
                continue
            except ConnectionResetError:
                # Par precaution : cette socket n'emet jamais, un refus n'a
                # pas de raison d'y revenir ; elle reste utilisable.
                continue
            except OSError as e:
                # Erreur reelle : la prise s'arrete, mais en le DISANT --
                # sans message, elle passerait juste a l'arret, muette.
                self.stats.error = f"reception interrompue : {e}"
                return

            now = time.time()
            self.stats.rx += 1
            self.stats.rx_bytes += len(payload)
            self.stats.last_rx = now
            if payload:
                # Un datagramme vide est relaye aussi (octet pour octet) ;
                # seul l'affichage n'a rien a en montrer.
                texte = _decode(payload)
                self.stats.last_line = texte.split("\n")[0][:90]
                self.stats.push(now, addr[0], texte)
            for so in sorties:
                self._emettre(so, payload)

    def _resoudre(self, noms):
        """Fil auxiliaire : resout les noms de sortie, puis reessaie ceux qui
        restent introuvables (PC eteint, reseau pas pret au demarrage de
        Windows). Ce fil ne tient aucun port."""
        en_attente = list(noms)
        while en_attente and self._running.is_set():
            reste = []
            for so in en_attente:
                try:
                    num = socket.gethostbyname(so.ip)
                except (OSError, ValueError, TypeError):
                    so.introuvable = True
                    reste.append(so)
                    continue
                if not self._running.is_set():
                    return
                so.introuvable = False
                self._installer(so, num)
            en_attente = reste
            if en_attente and not self._attendre(self.REESSAI_NOM):
                return

    def _installer(self, so, num):
        """Sortie resolue : boucle sur l'entree (son nom designait ce PC) ?
        socket connectee si la destination est ce PC. L'adresse est posee en
        dernier : le fil d'ecoute ne s'en sert qu'une fois tout pret."""
        if _vers_entree(num, so.port, self.bind_ip, self.port):
            so.boucle = True
            self.stats.per_out[so.idx][4] = True
            return
        if num.startswith("127.") or num in _adresses_propres():
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.connect((num, so.port))
                s.setblocking(False)
                so.sock = s
            except OSError:
                if s is not None:
                    try:
                        s.close()
                    except OSError:
                        pass
                so.sock = None
        so.num = num

    def _emettre(self, so, payload):
        compteur = self.stats.per_out[so.idx]
        if so.boucle:
            return
        if so.num is None:
            if so.introuvable:
                # Nom introuvable : chaque datagramme compte comme un echec.
                self.stats.tx_err += 1
                compteur[1] += 1
                compteur[2] = False
            return   # nom pas encore resolu : rien a compter
        ok = True
        try:
            if so.sock is not None:
                so.sock.send(payload)
            else:
                self._out.sendto(payload, (so.num, so.port))
        except (OSError, ValueError, TypeError):
            ok = False
        if ok and so.sock is not None:
            # Le refus d'un envoi precedent (aucun programme n'ecoute ce port)
            # revient ici, avec un temps de retard. Ce qu'un client
            # renverrait est lu et jete.
            for _k in range(8):
                try:
                    so.sock.recv(2048)
                except BlockingIOError:
                    break
                except ConnectionResetError:
                    ok = False
                    compteur[3] = time.monotonic()
                    break
                except OSError:
                    break
        if ok:
            self.stats.tx += 1
            compteur[0] += 1
        else:
            self.stats.tx_err += 1
            compteur[1] += 1
        compteur[2] = ok

    def stop(self):
        self._running.clear()

    def _close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


def _explain_bind_error(err):
    """Message de systeme -> phrase utilisable. Le cas 'port deja pris' est
    LE cas courant ici : il merite mieux qu'un code d'erreur."""
    if isinstance(err, (TypeError, ValueError)):
        return "adresse d'ecoute illisible (caractere invisible ou non ASCII)"
    code = getattr(err, "winerror", None) or getattr(err, "errno", None)
    if code in (10048, 48, 98):
        return "port deja utilise par un autre programme"
    if code in (10049, 49, 99):
        return "adresse d'ecoute inexistante sur cette machine"
    if code in (10013, 13):
        return "port interdit (reserve par Windows ou tenu en exclusivite par un autre programme)"
    if isinstance(err, socket.gaierror):
        return "adresse d'ecoute introuvable"
    return str(err)


def _decode(payload):
    """Datagramme -> texte affichable, lignes normalisees. Les octets non
    ASCII deviennent des caracteres de remplacement plutot que de faire
    echouer l'affichage : le journal doit rester lisible meme sur un flux
    binaire."""
    texte = payload.decode("ascii", errors="replace")
    return texte.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def _fmt_int(n):
    return f"{int(n):,}".replace(",", " ")


def _fmt_bytes(n):
    n = float(n)
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unit == "Go":
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024


_ADRESSES_PROPRES = None


def _adresses_propres():
    """Adresses et nom de cette machine, calcules une fois (la machine
    resout son propre nom sans passer par le reseau)."""
    global _ADRESSES_PROPRES
    if _ADRESSES_PROPRES is None:
        try:
            nom = socket.gethostname()
            _ADRESSES_PROPRES = set(socket.gethostbyname_ex(nom)[2]) | {nom.lower()}
        except (OSError, UnicodeError):
            _ADRESSES_PROPRES = set()
    return _ADRESSES_PROPRES


def _is_local(ip):
    """Adresse qui revient sur cette machine : bouclage, adresses et nom de
    la machine, et diffusion -- une diffusion envoyee d'ici est aussi recue
    ici, par toute prise qui ecoute ce port sur toutes les interfaces."""
    ip = ip.strip().lower().rstrip(".")
    if ip.startswith("127.") or ip.endswith(".255") or ip in (
            "localhost", "0.0.0.0", "::1", "255.255.255.255"):
        return True
    return ip in _adresses_propres()


def _vers_entree(ip_sortie, port_sortie, ip_ecoute, port_ecoute):
    """Une sortie ip_sortie:port_sortie arrive-t-elle sur l'entree
    ip_ecoute:port_ecoute d'une prise de cette machine ? C'est la condition
    d'une boucle : la prise recevrait ce qu'elle (ou une autre) vient
    d'emettre."""
    if not port_ecoute or port_sortie != port_ecoute:
        return False
    ecoute = (ip_ecoute or "").strip().lower().rstrip(".") or "0.0.0.0"
    if ecoute == "localhost":
        ecoute = "127.0.0.1"
    elif not _IPV4_RE.match(ecoute):
        # Ecoute donnee par un nom (celui du PC...) : elle designe une
        # adresse de CE PC, sans qu'on sache laquelle -- par prudence, toute
        # destination locale compte.
        ecoute = "0.0.0.0"
    if ecoute == "0.0.0.0":
        return _is_local(ip_sortie)
    s = ip_sortie.strip().lower().rstrip(".")
    if s == ecoute or s == "255.255.255.255":
        return True
    if ecoute.startswith("127."):
        # Une prise liee a 127.0.0.1 ne recoit que ce qui est adresse a
        # 127.0.0.1 (pas a 127.0.0.2).
        return s == "localhost" and ecoute == "127.0.0.1"
    # Diffusion du reseau de l'adresse d'ecoute (masque inconnu : /24 suppose).
    # Une diffusion vers un AUTRE reseau (tablettes en Wi-Fi, passerelle en
    # Ethernet) n'est pas une boucle.
    return s.endswith(".255") and s.rsplit(".", 1)[0] == ecoute.rsplit(".", 1)[0]


def _prises_en_boucle(prises):
    """Rangs des prises actives prises dans un cycle (A -> B -> A) : une
    trame y tournerait sans fin. La sortie d'une prise vers sa PROPRE entree
    n'en fait pas partie : elle n'est simplement jamais emise. Une fusion
    (A et B -> C) n'est pas un cycle."""
    actives = {i: p for i, p in enumerate(prises) if p.get("actif") and p.get("port")}

    def suivants(i):
        res = set()
        for s in actives[i].get("sorties", []):
            if not (s.get("actif") and s.get("ip") and s.get("port")):
                continue
            for j, q in actives.items():
                if j != i and _vers_entree(s["ip"], s["port"], q.get("ecoute_ip"), q["port"]):
                    res.add(j)
        return res

    graphe = {i: suivants(i) for i in actives}
    en_boucle = set()
    for depart in graphe:
        vus, pile = set(), list(graphe[depart])
        while pile:
            j = pile.pop()
            if j == depart:
                en_boucle.add(depart)
                break
            if j not in vus:
                vus.add(j)
                pile.extend(graphe[j])
    return en_boucle


_ADRESSE_RE = re.compile(r"^[A-Za-z0-9.\-]{1,253}$")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _adresse_valide(ip):
    """Adresse IPv4 ou nom de machine : chiffres, lettres, points et tirets.
    Ecarte les caracteres invisibles qu'une adresse copiee emporte parfois,
    les espaces, et les adresses IPv6 (non prises en charge)."""
    return bool(_ADRESSE_RE.match(ip))


# Compteurs d'une sortie pas encore servie (voir Stats.per_out).
VIDE_SORTIE = (0, 0, None, 0.0, False)

# Colonnes a trier NUMERIQUEMENT. Sans cela le tri serait alphabetique et
# placerait "1 200" avant "9", ce qui est exactement ce qu'on ne veut pas
# quand on cherche la prise qui debite le plus.
COLONNES_NUMERIQUES = {"debit", "recu", "reemis", "port", "envoyes", "echecs"}

# Ordre de gravite des etats : trier par etat doit remonter les problemes en
# haut de tableau, pas les classer par ordre alphabetique.
ORDRE_ETATS = {"Erreur": 0, "Injoignable": 0, "Boucle": 0,
               "Aucune trame": 1, "En attente": 1, "Demarrage": 2,
               "Flux present": 3, "Diffuse": 3,
               "Hors service": 4, "Inactive": 4, "Non demarree": 4}


def sort_key(colonne, texte):
    """Valeur de tri d'une cellule. Les cellules affichent du texte mis en
    forme ("12 480", "9.8/s", "\u2014") : on le reconvertit ici plutot que de
    tenir un second jeu de donnees en parallele."""
    if colonne in COLONNES_NUMERIQUES:
        brut = (texte.replace("\u2014", "").replace("/s", "")
                .replace("\u00a0", "").replace(" ", ""))
        try:
            return float(brut)
        except ValueError:
            return -1.0
    if colonne == "etat":
        return ORDRE_ETATS.get(texte, 9)
    return texte.lower()


# =========================================================================
# Logo et pastilles
# =========================================================================

def draw_logo(canvas, x, y, s):
    """Multiprise vue de dessus : corps bleu, trois prises, cordon."""
    w = s * 2.0
    h = s * 0.86
    x0, y0 = x, y + (s - h) / 2
    r = h / 2.0
    canvas.create_oval(x0, y0, x0 + h, y0 + h, fill=ACCENT, outline="")
    canvas.create_oval(x0 + w - h, y0, x0 + w, y0 + h, fill=ACCENT, outline="")
    canvas.create_rectangle(x0 + r, y0, x0 + w - r, y0 + h, fill=ACCENT, outline="")
    canvas.create_line(x0 + 2, y0 + r, x0 - s * 0.42, y0 + r * 0.25, fill=ACCENT,
                       width=max(2, s * 0.11), smooth=True, capstyle="round")
    for i in range(3):
        cx = x0 + w * (0.24 + 0.26 * i)
        cy = y0 + r
        pr = h * 0.30
        canvas.create_oval(cx - pr, cy - pr, cx + pr, cy + pr, fill=BG_APP, outline="")
        d = pr * 0.30
        for dx in (-pr * 0.40, pr * 0.40):
            canvas.create_oval(cx + dx - d, cy - d, cx + dx + d, cy + d,
                               fill=ACCENT, outline="")


def make_tray_image(size=64):
    """Meme logo en bitmap pour la zone de notification (necessite Pillow,
    dont pystray a de toute facon besoin). Dessin d'origine en 64 x 64,
    mis a l'echelle pour l'icone de l'exe."""
    from PIL import Image, ImageDraw
    k = size / 64.0

    def sc(*pts):
        return [round(v * k) for v in pts]

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    blue = (47, 111, 196, 255)
    if hasattr(d, "rounded_rectangle"):
        d.rounded_rectangle(sc(4, 20, 60, 46), radius=round(13 * k), fill=blue)
    else:   # Pillow < 8.2 : coins carres, l'icone reste reconnaissable
        d.rectangle(sc(4, 20, 60, 46), fill=blue)
    d.line([tuple(sc(6, 33)), tuple(sc(0, 24))], fill=blue, width=max(1, round(6 * k)))
    for i in range(3):
        cx = 15 + 17 * i
        d.ellipse(sc(cx - 8, 25, cx + 8, 41), fill=(255, 255, 255, 255))
        d.ellipse(sc(cx - 5, 31, cx - 1, 35), fill=blue)
        d.ellipse(sc(cx + 1, 31, cx + 5, 35), fill=blue)
    return img


def write_ico(path):
    """Icone .ico de l'exe Windows (construire_exe.bat l'appelle avant
    PyInstaller). Dessinee en 256 puis reduite par Pillow pour chaque
    taille : les petites restent nettes, aucun fichier image a distribuer."""
    tailles = [(n, n) for n in (16, 24, 32, 48, 64, 128, 256)]
    make_tray_image(256).save(path, format="ICO", sizes=tailles)
    return path


_DOT_CACHE = {}


def dot_image(color, size=11):
    """Pastille de couleur pour la colonne d'etat des tableaux.

    Un tableau ttk ne sait pas colorer UNE cellule (une balise de ligne
    colore toute la ligne, ce qui serait illisible) : on passe donc par une
    petite image, seul moyen d'avoir un temoin de couleur par ligne. Les
    pixels hors du disque sont rendus transparents pour que la pastille
    reste correcte sur une ligne selectionnee (fond bleu)."""
    key = (color, size)
    if key in _DOT_CACHE:
        return _DOT_CACHE[key]
    img = tk.PhotoImage(width=size, height=size)
    c = (size - 1) / 2.0
    r = size / 2.0 - 1.0
    for y in range(size):
        for x in range(size):
            if (x - c) ** 2 + (y - c) ** 2 <= r * r:
                img.put(color, (x, y))
            else:
                try:
                    img.transparency_set(x, y, True)
                except (tk.TclError, AttributeError):
                    img.put(BG_PANEL, (x, y))
    _DOT_CACHE[key] = img
    return img


# =========================================================================
# Petits widgets communs
# =========================================================================

def tool_button(parent, text, command, primary=False, bg=None):
    """Bouton plat facon barre d'outils, avec survol -- les boutons tk
    natifs sous Windows ignorent les couleurs sombres au survol, d'ou le
    reglage a la main."""
    base = ACCENT if primary else (bg or BG_NAV)
    hover = ACCENT_HOVER if primary else BG_HOVER
    fg = "#ffffff" if primary else FG_LABEL
    b = tk.Button(parent, text=text, command=command, font=FONT_BOLD, bg=base,
                  fg=fg, activebackground=hover, activeforeground=fg,
                  relief="flat", bd=0, padx=13, pady=6, cursor="hand2",
                  highlightthickness=0)
    b.bind("<Enter>", lambda _e: b.configure(bg=hover))
    b.bind("<Leave>", lambda _e: b.configure(bg=base))
    return b


def dark_entry(parent, textvariable, width=14, font=None):
    return tk.Entry(parent, textvariable=textvariable, width=width,
                    font=font or FONT, bg=BG_FIELD, fg=FG_LABEL,
                    insertbackground=FG_LABEL, relief="flat",
                    highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=ACCENT)


def dark_check(parent, text, variable, command=None, bg=BG_PANEL):
    return tk.Checkbutton(parent, text=text, variable=variable, command=command,
                          bg=bg, fg=FG_LABEL, activebackground=bg,
                          activeforeground=FG_LABEL, selectcolor=BG_FIELD,
                          font=FONT, highlightthickness=0, bd=0)


def dark_label(parent, text, fg=None, font=None, bg=None):
    return tk.Label(parent, text=text, bg=bg or BG_PANEL, fg=fg or FG_LABEL,
                    font=font or FONT)


def section_header(parent, titre):
    """Titre de section. Volontairement discret -- gris, petit, lettres
    espacees : un intitule de colonne ne doit pas peser autant que les
    donnees qu'il annonce, sinon la fenetre se lit comme un empilement de
    bandeaux. Retourne (cadre, label_droite), la partie droite servant aux
    indications qui changent (prise selectionnee, comptes...)."""
    bar = tk.Frame(parent, bg=BG_PANEL)
    bar.pack(fill="x", padx=PAD_X, pady=(12, 8))
    dark_label(bar, " ".join(titre.upper()), fg=FG_DIM, font=FONT_SMALL).pack(side="left")
    droite = dark_label(bar, "", fg=FG_DIM, font=FONT)
    droite.pack(side="right")
    return bar, droite


def _bureau_virtuel(win):
    """(x, y, largeur, hauteur) de l'ensemble des ecrans. winfo_screenwidth
    ne connait que l'ecran principal : borner par lui renverrait sur
    l'ecran principal un dialogue ouvert depuis un second ecran."""
    try:
        import ctypes
        gsm = ctypes.windll.user32.GetSystemMetrics
        vx, vy, vw, vh = gsm(76), gsm(77), gsm(78), gsm(79)
        if vw > 0 and vh > 0:
            return vx, vy, vw, vh
    except Exception:
        pass
    return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()


def _sur_un_ecran(x, y):
    """Le point (x, y) est-il sur un ecran branche ? (Un second ecran
    debranche depuis la derniere session laisserait la fenetre hors de
    vue.) Dans le doute, oui."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user32.MonitorFromPoint.restype = wintypes.HMONITOR
        return bool(user32.MonitorFromPoint(wintypes.POINT(x, y), 0))  # 0 : aucun ecran -> NULL
    except Exception:
        return True


def center_on(win, parent):
    """Centre une fenetre sur sa fenetre mere sans la laisser deborder des
    ecrans (cas d'une fenetre mere collee a un bord)."""
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    vx, vy, vw, vh = _bureau_virtuel(win)
    x = max(vx, min(px + (pw - w) // 2, vx + vw - w))
    y = max(vy, min(py + (ph - h) // 2, vy + vh - h))
    win.geometry(f"+{x}+{y}")


def make_table(parent, colonnes, height=6):
    """Tableau sombre avec ascenseur. 'colonnes' : (id, titre, largeur,
    alignement, extensible).

    La colonne #0 porte la PASTILLE de couleur et la CASE A COCHER : c'est
    la seule colonne d'un tableau ttk qui accepte une image, et regrouper
    les deux temoins evite d'ajouter une colonne supplementaire pour trois
    pixels d'information. Un clic dessus bascule la ligne en service ou
    hors service (voir _on_click_prises)."""
    wrap = tk.Frame(parent, bg=BG_PANEL)
    wrap.pack(fill="both", expand=True, padx=PAD_X, pady=(0, 12))
    tree = ttk.Treeview(wrap, columns=[c[0] for c in colonnes],
                        show="tree headings", selectmode="browse", height=height)
    tree.heading("#0", text="")
    tree.column("#0", width=52, minwidth=52, stretch=False, anchor="w")
    for cid, titre, w, anchor, stretch in colonnes:
        # Le titre suit l'alignement de sa colonne : un intitule centre
        # au-dessus de chiffres cales a droite donne cet aspect flottant
        # qu'on remarque sans savoir le nommer.
        tree.heading(cid, text=titre, anchor=anchor)
        tree.column(cid, width=w, anchor=anchor, stretch=stretch)
    bar = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    tree.tag_configure("off", foreground=FG_DIM)
    tree.tag_configure("err", foreground=COLOR_ERR)
    # Titres d'origine conserves : l'indicateur de tri est ajoute puis retire
    # a l'affichage, il ne doit pas s'accumuler dans le titre.
    tree.titres = {c[0]: c[1] for c in colonnes}
    tree.tri = None
    return tree


# =========================================================================
# Dialogue : une sortie
# =========================================================================

class SortieDialog(tk.Toplevel):
    """Adresse + port + libelle d'une destination. Fenetre modale : le
    resultat est lu dans self.result, None si annule."""

    def __init__(self, parent, sortie=None):
        super().__init__(parent)
        self.result = None
        s = sortie or {"nom": "", "ip": "127.0.0.1", "port": "", "actif": True}
        self.title("Sortie" if sortie else "Nouvelle sortie")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        self.transient(parent)

        self.v_ip = tk.StringVar(value=s.get("ip", "127.0.0.1"))
        self.v_port = tk.StringVar(value=str(s.get("port") or ""))
        self.v_nom = tk.StringVar(value=s.get("nom", ""))
        self.v_actif = tk.BooleanVar(value=bool(s.get("actif", True)))

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=18, pady=16)
        dark_label(body, "Adresse de destination", fg=FG_DIM).grid(
            row=0, column=0, sticky="w", pady=(0, 3))
        e_ip = dark_entry(body, self.v_ip, width=20, font=FONT_MONO)
        e_ip.grid(row=1, column=0, sticky="we", ipady=3)
        dark_label(body, "Port", fg=FG_DIM).grid(
            row=0, column=1, sticky="w", padx=(12, 0), pady=(0, 3))
        dark_entry(body, self.v_port, width=8, font=FONT_MONO).grid(
            row=1, column=1, sticky="we", padx=(12, 0), ipady=3)
        dark_label(body, "Libelle (le programme servi)", fg=FG_DIM).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(12, 3))
        dark_entry(body, self.v_nom, width=32).grid(
            row=3, column=0, columnspan=2, sticky="we", ipady=3)
        dark_check(body, "Sortie active", self.v_actif).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

        foot = tk.Frame(self, bg=BG_NAV)
        foot.pack(fill="x")
        tool_button(foot, "Valider", self._ok, primary=True).pack(
            side="right", padx=(6, 14), pady=10)
        tool_button(foot, "Annuler", self.destroy).pack(side="right", pady=10)

        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        center_on(self, parent)
        e_ip.focus_set()
        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        ip = self.v_ip.get().strip()
        port = _as_port(self.v_port.get(), 0)
        if not ip:
            messagebox.showerror("Sortie", "Adresse de destination vide.", parent=self)
            return
        if not _adresse_valide(ip):
            messagebox.showerror(
                "Sortie", "Adresse de destination invalide : chiffres, lettres, "
                          "points et tirets seulement (ex. 127.0.0.1 ou 192.168.1.50). "
                          "Une adresse copiee emporte parfois un caractere invisible.",
                parent=self)
            return
        if not port:
            messagebox.showerror("Sortie", "Port invalide (1 a 65535).", parent=self)
            return
        self.result = {"nom": self.v_nom.get().strip(), "ip": ip, "port": port,
                       "actif": bool(self.v_actif.get())}
        self.destroy()


# =========================================================================
# Dialogue : sorties en serie
# =========================================================================

class SerieDialog(tk.Toplevel):
    """Creation de N sorties d'un coup : meme adresse, ports consecutifs.

    self.result contient la liste des sorties creees. L'apercu est
    recalcule a chaque frappe : on voit exactement ce qui va etre cree
    AVANT de valider, ce qui evite de decouvrir apres coup qu'on a fabrique
    douze sorties sur les mauvais ports."""

    def __init__(self, parent, port_ecoute=0, existants=None, ecoute_ip="0.0.0.0"):
        super().__init__(parent)
        self.result = None
        self.port_ecoute = port_ecoute
        self.ecoute_ip = ecoute_ip
        self.existants = set(existants or ())   # {(ip, port)} deja presents

        self.title("Sorties en serie")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        self.transient(parent)

        self.v_ip = tk.StringVar(value="127.0.0.1")
        self.v_depart = tk.StringVar(value=str(port_ecoute + 100 if port_ecoute else 4101))
        self.v_nb = tk.StringVar(value="4")
        self.v_pas = tk.StringVar(value="1")
        self.v_nom = tk.StringVar(value="Sortie")
        self.v_actif = tk.BooleanVar(value=True)

        self._build()
        for v in (self.v_ip, self.v_depart, self.v_nb, self.v_pas, self.v_nom):
            v.trace_add("write", lambda *_a: self._apercu())
        self._apercu()
        center_on(self, parent)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()
        self.wait_window(self)

    def _build(self):
        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=18, pady=16)

        dark_label(body, "Adresse commune", fg=FG_DIM).grid(row=0, column=0, sticky="w")
        e = dark_entry(body, self.v_ip, width=18, font=FONT_MONO)
        e.grid(row=1, column=0, sticky="we", ipady=3, padx=(0, 12))

        dark_label(body, "Port de depart", fg=FG_DIM).grid(row=0, column=1, sticky="w")
        dark_entry(body, self.v_depart, width=8, font=FONT_MONO).grid(
            row=1, column=1, sticky="we", ipady=3, padx=(0, 12))

        dark_label(body, "Nombre", fg=FG_DIM).grid(row=0, column=2, sticky="w")
        dark_entry(body, self.v_nb, width=6, font=FONT_MONO).grid(
            row=1, column=2, sticky="we", ipady=3, padx=(0, 12))

        dark_label(body, "Pas", fg=FG_DIM).grid(row=0, column=3, sticky="w")
        dark_entry(body, self.v_pas, width=6, font=FONT_MONO).grid(
            row=1, column=3, sticky="we", ipady=3)

        dark_label(body, "Libelle (numerote automatiquement)", fg=FG_DIM).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(14, 3))
        dark_entry(body, self.v_nom, width=30).grid(
            row=3, column=0, columnspan=3, sticky="we", ipady=3)
        dark_check(body, "Actives", self.v_actif).grid(row=3, column=3, sticky="w")

        dark_label(body, "Apercu", fg=FG_DIM).grid(
            row=4, column=0, columnspan=4, sticky="w", pady=(14, 3))
        self.txt = tk.Text(body, height=8, width=52, bg=BG_FIELD, fg=FG_LABEL,
                           font=FONT_MONO, relief="flat", highlightthickness=1,
                           highlightbackground=BORDER, padx=8, pady=6)
        self.txt.grid(row=5, column=0, columnspan=4, sticky="we")
        self.txt.tag_configure("skip", foreground=COLOR_WARN)
        self.txt.tag_configure("err", foreground=COLOR_ERR)
        self.txt.configure(state="disabled")

        foot = tk.Frame(self, bg=BG_NAV)
        foot.pack(fill="x")
        self.btn = tool_button(foot, "Creer", self._ok, primary=True)
        self.btn.pack(side="right", padx=(6, 14), pady=10)
        tool_button(foot, "Annuler", self.destroy).pack(side="right", pady=10)
        e.focus_set()

    def _serie(self):
        """(sorties_a_creer, lignes_d_apercu). Une entree ecartee (doublon,
        port occupe par l'ecoute, hors bornes) est signalee dans l'apercu
        plutot que supprimee en silence."""
        ip = self.v_ip.get().strip()
        depart = _as_port(self.v_depart.get(), 0)
        try:
            nb = max(0, min(200, int(self.v_nb.get().strip() or 0)))
        except ValueError:
            nb = 0
        try:
            pas = int(self.v_pas.get().strip() or 1)
        except ValueError:
            pas = 1
        nom = self.v_nom.get().strip()

        lignes = []
        sorties = []
        if not ip:
            return [], [("adresse vide", "err")]
        if not _adresse_valide(ip):
            return [], [("adresse invalide : chiffres, lettres, points et tirets", "err")]
        if not depart:
            return [], [("port de depart invalide", "err")]
        if nb <= 0:
            return [], [("nombre de sorties a creer : au moins 1", "err")]

        vus = set()
        for i in range(nb):
            port = depart + i * pas
            libelle = f"{nom} {i + 1}" if nom else ""
            if not (1 <= port <= 65535):
                lignes.append((f"{ip}:{port}  hors bornes, ignore", "skip"))
                continue
            if _vers_entree(ip, port, self.ecoute_ip, self.port_ecoute):
                lignes.append((f"{ip}:{port}  = entree de la prise (boucle), ignore", "skip"))
                continue
            if (ip, port) in self.existants or (ip, port) in vus:
                lignes.append((f"{ip}:{port}  deja present, ignore", "skip"))
                continue
            vus.add((ip, port))
            sorties.append({"nom": libelle, "ip": ip, "port": port,
                            "actif": bool(self.v_actif.get())})
            lignes.append((f"{ip}:{port}   {libelle}", None))
        return sorties, lignes

    def _apercu(self):
        sorties, lignes = self._serie()
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        for texte, tag in lignes:
            self.txt.insert("end", texte + "\n", tag or "")
        self.txt.configure(state="disabled")
        n = len(sorties)
        self.btn.configure(text=f"Creer {n} sortie{'s' if n > 1 else ''}" if n else "Creer")

    def _ok(self):
        sorties, _lignes = self._serie()
        if not sorties:
            messagebox.showerror("Sorties en serie",
                                 "Aucune sortie a creer avec ces valeurs.",
                                 parent=self)
            return
        self.result = sorties
        self.destroy()


# =========================================================================
# Dialogue : une prise
# =========================================================================

class PriseDialog(tk.Toplevel):
    """Configuration complete d'une prise. self.result contient le
    dictionnaire de prise, ou None si annule. 'sortie' : rang de la sortie
    a selectionner d'emblee (double-clic dans le tableau des sorties)."""

    def __init__(self, parent, prise=None, sortie=None):
        super().__init__(parent)
        self.result = None
        p = prise or {"nom": "", "ecoute_ip": "0.0.0.0", "port": "",
                      "actif": True, "sorties": []}
        self.sorties = [dict(s) for s in p.get("sorties", [])]
        self.title("Configuration de la prise" if prise else "Nouvelle prise")
        self.configure(bg=BG_PANEL)
        self.minsize(600, 470)
        self.transient(parent)

        self.v_nom = tk.StringVar(value=p.get("nom", ""))
        self.v_ip = tk.StringVar(value=p.get("ecoute_ip", "0.0.0.0"))
        self.v_port = tk.StringVar(value=str(p.get("port") or ""))
        self.v_actif = tk.BooleanVar(value=bool(p.get("actif", True)))

        self._build()
        self._refresh(sortie)
        if sortie is not None and self.tree.exists(str(sortie)):
            self.tree.see(str(sortie))
        center_on(self, parent)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()
        self.wait_window(self)

    def _build(self):
        entree = tk.Frame(self, bg=BG_PANEL)
        entree.pack(fill="x", padx=18, pady=(16, 4))
        dark_label(entree, "ENTREE  \u2014  ce que la multiprise ecoute", fg=ACCENT,
                   font=FONT_BOLD).pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(entree, bg=BG_PANEL)
        grid.pack(fill="x")
        dark_label(grid, "Nom", fg=FG_DIM).grid(row=0, column=0, sticky="w")
        e_nom = dark_entry(grid, self.v_nom, width=22)
        e_nom.grid(row=1, column=0, sticky="we", ipady=3)
        dark_label(grid, "Adresse d'ecoute", fg=FG_DIM).grid(
            row=0, column=1, sticky="w", padx=(12, 0))
        dark_entry(grid, self.v_ip, width=16, font=FONT_MONO).grid(
            row=1, column=1, sticky="we", padx=(12, 0), ipady=3)
        dark_label(grid, "Port", fg=FG_DIM).grid(row=0, column=2, sticky="w", padx=(12, 0))
        dark_entry(grid, self.v_port, width=8, font=FONT_MONO).grid(
            row=1, column=2, sticky="we", padx=(12, 0), ipady=3)
        dark_check(entree, "Prise en service", self.v_actif).pack(anchor="w", pady=(10, 0))
        dark_label(entree, "0.0.0.0 = toutes les interfaces de la machine (le cas normal).",
                   fg=FG_DIM, font=FONT_MONO_S).pack(anchor="w", pady=(2, 0))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=18, pady=14)

        haut = tk.Frame(self, bg=BG_PANEL)
        haut.pack(fill="x", padx=18)
        dark_label(haut, "SORTIES  \u2014  vers qui le flux est recopie", fg=ACCENT,
                   font=FONT_BOLD).pack(side="left")
        dark_label(haut, "double-clic pour modifier", fg=FG_DIM,
                   font=FONT_MONO_S).pack(side="right")

        wrap = tk.Frame(self, bg=BG_PANEL)
        wrap.pack(fill="both", expand=True, padx=18, pady=(8, 0))
        self.tree = ttk.Treeview(wrap, columns=("etat", "adresse", "port", "nom"),
                                 show="headings", selectmode="browse", height=7)
        for cid, titre, w, anchor in (("etat", "", 34, "center"),
                                      ("adresse", "Adresse", 150, "w"),
                                      ("port", "Port", 70, "w"),
                                      ("nom", "Libelle", 200, "w")):
            self.tree.heading(cid, text=titre, anchor=anchor)
            self.tree.column(cid, width=w, anchor=anchor, stretch=(cid == "nom"))
        bar = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("off", foreground=FG_DIM)
        self.tree.bind("<Double-1>", lambda _e: self._edit())
        self.tree.bind("<Return>", lambda _e: self._edit())
        self.tree.bind("<Delete>", lambda _e: self._del())

        btns = tk.Frame(self, bg=BG_PANEL)
        btns.pack(fill="x", padx=18, pady=10)
        tool_button(btns, "+ Ajouter", self._add).pack(side="left")
        tool_button(btns, "+ En serie...", self._serie, primary=True).pack(
            side="left", padx=6)
        tool_button(btns, "Modifier", self._edit).pack(side="left")
        tool_button(btns, "Activer / desactiver", self._toggle).pack(side="left", padx=6)
        tool_button(btns, "Supprimer", self._del).pack(side="left")

        foot = tk.Frame(self, bg=BG_NAV)
        foot.pack(fill="x")
        tool_button(foot, "Enregistrer", self._ok, primary=True).pack(
            side="right", padx=(6, 18), pady=10)
        tool_button(foot, "Annuler", self.destroy).pack(side="right", pady=10)
        e_nom.focus_set()

    def _refresh(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(self.sorties):
            actif = bool(s.get("actif", True))
            self.tree.insert("", "end", iid=str(i),
                             values=("\u25cf" if actif else "\u25cb", s.get("ip", ""),
                                     s.get("port", ""), s.get("nom", "")),
                             tags=() if actif else ("off",))
        if select is not None and self.tree.exists(str(select)):
            self.tree.selection_set(str(select))
            self.tree.focus(str(select))

    def _selected(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    # Une sous-fenetre (sortie, serie) prend le grab et le libere en se
    # fermant ; Tk ne le rend pas a cette fenetre-ci. Sans le reprendre, la
    # fenetre principale redeviendrait cliquable pendant la configuration.
    def _add(self):
        dlg = SortieDialog(self)
        self.grab_set()
        if dlg.result:
            self.sorties.append(dlg.result)
            self._refresh(len(self.sorties) - 1)

    def _serie(self):
        dlg = SerieDialog(self, _as_port(self.v_port.get(), 0),
                          {(s["ip"], s["port"]) for s in self.sorties},
                          self.v_ip.get().strip() or "0.0.0.0")
        self.grab_set()
        if dlg.result:
            self.sorties.extend(dlg.result)
            self._refresh(len(self.sorties) - 1)

    def _edit(self):
        i = self._selected()
        if i is None:
            return
        dlg = SortieDialog(self, self.sorties[i])
        self.grab_set()
        if dlg.result:
            self.sorties[i] = dlg.result
            self._refresh(i)

    def _toggle(self):
        i = self._selected()
        if i is None:
            return
        self.sorties[i]["actif"] = not self.sorties[i].get("actif", True)
        self._refresh(i)

    def _del(self):
        i = self._selected()
        if i is None:
            return
        self.sorties.pop(i)
        self._refresh(min(i, len(self.sorties) - 1) if self.sorties else None)

    def _ok(self):
        port = _as_port(self.v_port.get(), 0)
        ecoute = self.v_ip.get().strip() or "0.0.0.0"
        if not port:
            messagebox.showerror("Prise", "Port d'ecoute invalide (1 a 65535).",
                                 parent=self)
            return
        if ecoute.lower() == "localhost":
            ecoute = "127.0.0.1"
        if not _IPV4_RE.match(ecoute):
            messagebox.showerror(
                "Prise", "Adresse d'ecoute invalide : une adresse IPv4 de ce PC "
                         "(ex. 192.168.1.20), ou 0.0.0.0 pour toutes ses cartes "
                         "reseau (le cas normal).", parent=self)
            return
        vues = set()
        for s in self.sorties:
            if not s.get("actif"):
                continue
            if _vers_entree(s["ip"], s["port"], ecoute, port):
                messagebox.showerror(
                    "Prise", f"La sortie {s['ip']}:{s['port']} renvoie vers l'entree "
                             "de cette meme prise : les datagrammes tourneraient en "
                             "boucle.", parent=self)
                return
            cle = (s["ip"].strip().lower(), int(s["port"]))
            if cle in vues:
                messagebox.showerror(
                    "Prise", f"La sortie {s['ip']}:{s['port']} est en double : chaque "
                             "trame lui partirait deux fois.", parent=self)
                return
            vues.add(cle)
        self.result = {"nom": self.v_nom.get().strip() or f"Port {port}",
                       "ecoute_ip": ecoute,
                       "port": port, "actif": bool(self.v_actif.get()),
                       "sorties": self.sorties}
        self.destroy()


# =========================================================================
# Moniteur de flux (fenetre detachee, pour filtrer et exporter)
# =========================================================================

class MonitorWindow(tk.Toplevel):
    """Ce qui passe sur une prise, en clair et en direct.

    Le moniteur ne touche pas au chemin des trames : il relit le tampon
    circulaire rempli par le fil de la prise (voir Stats.push). Le fil
    d'ecoute ne peut donc jamais etre ralenti -- ni bloque -- par une
    fenetre d'affichage ouverte, meme sur un flux rapide."""

    def __init__(self, app, prise, stats):
        super().__init__(app)
        self.app = app
        # La fenetre suit SA prise (l'objet lui-meme), pas un rang dans la
        # liste : supprimer une prise au-dessus ne doit pas lui faire
        # afficher le flux de la voisine.
        self.prise = prise
        self.cle = id(prise)
        self.stats = stats
        self.last_seq = 0
        self.paused = False
        self._tick_id = None
        self.retitrer()
        self.configure(bg=BG_PANEL)
        self.geometry("860x520")
        self.minsize(520, 300)
        self.v_filtre = tk.StringVar()
        self.v_auto = tk.BooleanVar(value=True)
        self.v_horo = tk.BooleanVar(value=True)
        self.v_src = tk.BooleanVar(value=False)
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        self._tick()

    def _build(self):
        bar = tk.Frame(self, bg=BG_NAV)
        bar.pack(fill="x")
        self.pause_btn = tool_button(bar, "Pause", self._toggle_pause)
        self.pause_btn.pack(side="left", padx=(12, 6), pady=8)
        tool_button(bar, "Effacer", self._clear).pack(side="left")
        tool_button(bar, "Enregistrer...", self._save).pack(side="left", padx=6)
        dark_label(bar, "Filtre", fg=FG_DIM, bg=BG_NAV).pack(side="left", padx=(14, 4))
        dark_entry(bar, self.v_filtre, width=16, font=FONT_MONO).pack(side="left", pady=8)
        opts = tk.Frame(bar, bg=BG_NAV)
        opts.pack(side="right", padx=12)
        for txt, var in (("suivre", self.v_auto), ("heure", self.v_horo),
                         ("source", self.v_src)):
            dark_check(opts, txt, var, bg=BG_NAV).pack(side="left")

        wrap = tk.Frame(self, bg=BG_PANEL)
        wrap.pack(fill="both", expand=True)
        self.txt = tk.Text(wrap, bg=BG_FIELD, fg=FG_LABEL, font=FONT_MONO,
                           relief="flat", wrap="none", highlightthickness=0,
                           padx=10, pady=6)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set, state="disabled")
        sb.pack(side="right", fill="y")
        self.txt.pack(side="left", fill="both", expand=True)
        self.txt.tag_configure("ts", foreground=FG_DIM)
        self.txt.tag_configure("src", foreground=ACCENT)
        self.status = dark_label(self, "", fg=FG_DIM, bg=BG_NAV, font=FONT_MONO_S)
        self.status.configure(anchor="w", padx=12, pady=4)
        self.status.pack(fill="x")

    def retitrer(self):
        p = self.prise
        self.title(f"Flux \u2014 {p.get('nom')} ({p.get('ecoute_ip')}:{p.get('port')})")

    def set_stats(self, stats):
        """Rebranchement apres un redemarrage des fils : les compteurs sont
        neufs, la numerotation repart de zero."""
        self.stats = stats
        self.last_seq = 0

    def _tick(self):
        if self.stats is None:
            # Prise hors service (ou port invalide) : rien n'est ecoute, et
            # l'ancienne ligne d'etat ne doit pas continuer d'affirmer le
            # contraire.
            self.status.configure(text="hors service : aucune ecoute sur cette prise")
        elif not self.paused:
            filtre = self.v_filtre.get().strip().upper()
            nouvelles = self.stats.since(self.last_seq)
            if nouvelles:
                self.last_seq = nouvelles[-1][0]
                self.txt.configure(state="normal")
                for _seq, t, src, texte in nouvelles:
                    for ligne in texte.split("\n"):
                        if not ligne.strip() or (filtre and filtre not in ligne.upper()):
                            continue
                        if self.v_horo.get():
                            self.txt.insert("end", _hhmmss(t) + " ", "ts")
                        if self.v_src.get():
                            self.txt.insert("end", f"[{src}] ", "src")
                        self.txt.insert("end", ligne + "\n")
                # Le tampon d'affichage est borne : sur un flux continu, une
                # fenetre laissee ouverte une nuit entiere finirait sinon par
                # avaler toute la memoire de la machine.
                n = int(self.txt.index("end-1c").split(".")[0])
                if n > 4000:
                    self.txt.delete("1.0", f"{n - 3000}.0")
                self.txt.configure(state="disabled")
                if self.v_auto.get():
                    self.txt.see("end")
            etat = (f"ERREUR : {self.stats.error}" if self.stats.error
                    else "en service" if self.stats.running else "demarrage")
            echecs = (f"   \u00b7   echecs {_fmt_int(self.stats.tx_err)}"
                      if self.stats.tx_err else "")
            self.status.configure(
                text=f"{etat}   \u00b7   recu {_fmt_int(self.stats.rx)} datagrammes "
                     f"({_fmt_bytes(self.stats.rx_bytes)})   \u00b7   "
                     f"reemis {_fmt_int(self.stats.tx)}{echecs}")
        self._tick_id = self.after(300, self._tick)

    def _toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.configure(text="Reprendre" if self.paused else "Pause")

    def _clear(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")

    def _save(self):
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".log",
            filetypes=[("Journal", "*.log"), ("Texte", "*.txt")],
            initialfile=time.strftime("flux_%Y%m%d_%H%M.log"))
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.txt.get("1.0", "end"))
        except OSError as e:
            messagebox.showerror("Enregistrement", str(e), parent=self)

    def close(self):
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except tk.TclError:
                pass
            self._tick_id = None
        self.app.monitors.pop(self.cle, None)
        self.destroy()


def _hhmmss(t):
    lt = time.localtime(t)
    return f"{lt.tm_hour:02d}:{lt.tm_min:02d}:{lt.tm_sec:02d}.{int((t - int(t)) * 1000):03d}"


# =========================================================================
# Fenetre des options
# =========================================================================

class OptionsDialog(tk.Toplevel):
    """Les quatre reglages generaux, plus les actions rares (relance,
    quitter). Tout ce qui vivait dans la barre de menus tient ici."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Options")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        self.transient(app)

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=22, pady=18)
        dark_label(body, "COMPORTEMENT", fg=FG_DIM, font=FONT_SMALL).pack(
            anchor="w", pady=(0, 8))
        dark_check(body, "La croix range dans la zone de notification",
                   app.v_tray, command=app._save_options).pack(anchor="w")
        dark_check(body, "Demarrer reduit", app.v_min,
                   command=app._save_options).pack(anchor="w")
        dark_check(body, "Lancer au demarrage de Windows", app.v_auto,
                   command=app._toggle_autostart).pack(anchor="w")
        dark_check(body, "Journal : afficher les trames de la prise selectionnee",
                   app.v_trames, command=app._save_options).pack(anchor="w")

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=14)
        dark_label(body, "ACTIONS", fg=FG_DIM, font=FONT_SMALL).pack(
            anchor="w", pady=(0, 8))
        ligne = tk.Frame(body, bg=BG_PANEL)
        ligne.pack(anchor="w")
        tool_button(ligne, "Relancer l'ecoute (F5)", self._restart).pack(side="left")
        tool_button(ligne, "Quitter la multiprise", self._quit).pack(side="left", padx=6)

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=14)
        dark_label(body, f"{APP_TITLE} v{APP_VERSION}   \u00b7   ETDEL 2026",
                   fg=FG_DIM, font=FONT_MONO_S).pack(anchor="w")
        dark_label(body, "Les datagrammes sont recopies octet pour octet ; les\n"
                         "programmes clients voient la multiprise comme expediteur\n"
                         "(127.0.0.1 en local).", fg=FG_DIM,
                   font=FONT_MONO_S, ).pack(anchor="w", pady=(4, 0))

        foot = tk.Frame(self, bg=BG_NAV)
        foot.pack(fill="x")
        tool_button(foot, "Fermer", self.destroy, primary=True).pack(
            side="right", padx=(6, 22), pady=10)

        self.bind("<Escape>", lambda _e: self.destroy())
        center_on(self, app)
        self.grab_set()

    def _restart(self):
        self.destroy()
        self.app.restart()

    def _quit(self):
        self.destroy()
        self.app._shutdown()


# =========================================================================
# Fenetre principale
# =========================================================================

class App(tk.Tk):

    COLS_PRISES = (("etat", "Etat", 120, "w", False),
                   ("nom", "Prise", 120, "w", False),
                   ("ecoute", "Ecoute", 145, "w", False),
                   ("debit", "Debit", 75, "e", False),
                   ("recu", "Recu", 85, "e", False),
                   ("reemis", "Reemis", 85, "e", False),
                   ("derniere", "Derniere trame", 240, "w", True))

    COLS_SORTIES = (("etat", "Etat", 120, "w", False),
                    ("adresse", "Adresse", 145, "w", False),
                    ("port", "Port", 70, "w", False),
                    ("libelle", "Libelle", 180, "w", True),
                    ("envoyes", "Envoyes", 90, "e", False),
                    ("echecs", "Echecs", 80, "e", False))

    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.configure(bg=BG_APP)
        self.minsize(900, 520)
        self.config_data = load_config()
        alerte = self.config_data.pop("_alerte", None)
        self._appliquer_geometrie(self.config_data.get("geometry"))
        setup_style(self)

        self.threads = []
        self.stats_by_index = {}
        self.monitors = {}       # id(prise) -> fenetre Flux
        self._prev = {}          # index -> (t, rx) pour le calcul du debit
        self._debits = {}
        self._etats = {}         # cle de prise -> dernier etat journalise
        self._journal_seq = 0
        self._journal_stats = None   # prise dont le journal recopie les trames
        self._sorties_de = None      # prise dont le tableau des sorties est affiche
        self._tray_icon = None
        self._icon_ref = None

        self.v_tray = tk.BooleanVar(value=self.config_data.get("close_to_tray", True))
        self.v_min = tk.BooleanVar(value=self.config_data.get("start_minimized", False))
        # La case dit ce qui EST : le .bat present ou non dans le dossier
        # Demarrage (supprime a la main, ou laisse par une autre copie).
        bat = _startup_bat_path()
        self.v_auto = tk.BooleanVar(value=bool(bat and os.path.exists(bat)))
        self.v_trames = tk.BooleanVar(value=self.config_data.get("journal_trames", False))

        self._set_window_icon()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.log(f"{APP_TITLE} v{APP_VERSION} demarre", "info")
        if alerte:
            self.log(alerte, "err")
        for probleme in self._validate(self._prises()):
            self.log(probleme, "warn")
        self._sync_autostart()
        self.start_all()
        self._refresh_prises(rebuild=True)
        self._select_first()
        self._tick()
        if self.config_data.get("start_minimized"):
            # Sans pystray, pas de zone de notification : on reduit au moins
            # dans la barre des taches.
            self.after(200, lambda: self._hide_to_tray() or self.iconify())

    def _appliquer_geometrie(self, geo):
        """Taille et position de la derniere session. Une geometrie illisible
        (fichier retouche) donne la taille par defaut ; une position sur un
        ecran debranche depuis ne garde que la taille, Windows place la
        fenetre."""
        geo = geo or "1120x680"
        m = re.match(r"^\d+x\d+([+-]-?\d+)([+-]-?\d+)$", geo)
        if m:
            x = int(m.group(1).replace("+-", "-").lstrip("+"))
            y = int(m.group(2).replace("+-", "-").lstrip("+"))
            if not _sur_un_ecran(x + 60, y + 12):
                geo = geo.split("+")[0].split("-")[0]
        try:
            self.geometry(geo)
        except tk.TclError:
            self.geometry("1120x680")

    def _memorise_fenetre(self):
        """Taille et poignees, fenetre normale seulement : maximisee ou
        retiree, winfo_geometry ne donne pas la taille a restaurer."""
        try:
            # Jamais affichee (demarrage reduit) : sa taille n'est pas encore
            # la vraie, il n'y a rien a retenir.
            if (self.state() == "normal" and self.winfo_ismapped()
                    and self.winfo_height() > 100):
                self.config_data["geometry"] = self.winfo_geometry()
                self.config_data["sashes"] = [self.paned.sashpos(0), self.paned.sashpos(1)]
        except tk.TclError:
            pass

    # =====================================================================
    # Construction
    # =====================================================================
    def _open_options(self):
        """Reglages generaux, dans une fenetre plutot que dans une barre de
        menus : quatre cases a cocher ne justifient pas un menu permanent en
        haut de la fenetre, qui donnerait a l'outil l'allure d'un logiciel
        de bureautique des annees 90."""
        OptionsDialog(self)

    def _build(self):
        head = tk.Frame(self, bg=BG_PANEL)
        head.pack(fill="x")
        logo = tk.Canvas(head, width=72, height=48, bg=BG_PANEL, highlightthickness=0)
        logo.pack(side="left", padx=(PAD_X - 4, 10), pady=6)
        draw_logo(logo, 20, 12, 22)
        titres = tk.Frame(head, bg=BG_PANEL)
        titres.pack(side="left", pady=8)
        dark_label(titres, APP_TITLE, font=FONT_TITLE).pack(anchor="w")
        dark_label(titres, "Un port ecoute, plusieurs programmes servis",
                   fg=FG_DIM).pack(anchor="w")
        actions = tk.Frame(head, bg=BG_PANEL)
        actions.pack(side="right", padx=PAD_X)
        tool_button(actions, "+  Nouvelle prise", self.add_prise, primary=True).pack(side="left")
        tool_button(actions, "Sorties en serie", self.add_serie).pack(side="left", padx=6)
        tool_button(actions, "Configurer", self.edit_prise).pack(side="left")
        tool_button(actions, "Flux", self.open_monitor).pack(side="left", padx=6)
        tool_button(actions, "Options", self._open_options).pack(side="left")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Trois zones empilees, separateurs deplacables : chacun donne au
        # journal la place qu'il veut sans que les tableaux disparaissent.
        self.paned = ttk.PanedWindow(self, orient="vertical")
        self.paned.pack(fill="both", expand=True)

        z1 = tk.Frame(self.paned, bg=BG_PANEL)
        _bar, self.lbl_prises = section_header(z1, "PRISES")
        self.tree_prises = make_table(z1, self.COLS_PRISES, height=6)
        self.paned.add(z1, weight=3)

        z2 = tk.Frame(self.paned, bg=BG_PANEL)
        _bar2, self.lbl_sorties = section_header(z2, "SORTIES")
        self.tree_sorties = make_table(z2, self.COLS_SORTIES, height=4)
        self.paned.add(z2, weight=2)

        z3 = tk.Frame(self.paned, bg=BG_PANEL)
        bar3, _droite = section_header(z3, "JOURNAL")
        dark_check(bar3, "trames de la prise selectionnee", self.v_trames,
                   command=self._save_options).pack(side="right", padx=(0, 12))
        tk.Button(bar3, text="Effacer", command=self._clear_journal, font=FONT,
                  bg=BG_PANEL, fg=FG_DIM, activebackground=BG_PANEL,
                  activeforeground=FG_LABEL, relief="flat", bd=0,
                  cursor="hand2").pack(side="right")
        jwrap = tk.Frame(z3, bg=BG_PANEL)
        jwrap.pack(fill="both", expand=True, padx=PAD_X, pady=(0, 12))
        self.journal = tk.Text(jwrap, bg=BG_FIELD, fg=FG_LABEL, font=FONT_MONO,
                               relief="flat", wrap="none", highlightthickness=0,
                               padx=10, pady=6, height=8)
        jb = ttk.Scrollbar(jwrap, orient="vertical", command=self.journal.yview)
        self.journal.configure(yscrollcommand=jb.set, state="disabled")
        jb.pack(side="right", fill="y")
        self.journal.pack(side="left", fill="both", expand=True)
        self.journal.tag_configure("ts", foreground=FG_DIM)
        self.journal.tag_configure("info", foreground=FG_LABEL)
        self.journal.tag_configure("ok", foreground=COLOR_OK)
        self.journal.tag_configure("warn", foreground=COLOR_WARN)
        self.journal.tag_configure("err", foreground=COLOR_ERR)
        self.journal.tag_configure("trame", foreground=FG_DIM)
        self.paned.add(z3, weight=2)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        foot = tk.Frame(self, bg=BG_NAV)
        foot.pack(fill="x")
        self.status = dark_label(foot, "", fg=FG_DIM, bg=BG_NAV)
        self.status.configure(anchor="w", padx=PAD_X, pady=6)
        self.status.pack(side="left")
        dark_label(foot, "case a gauche : en service  \u00b7  titre de colonne : trier  "
                         "\u00b7  double-clic : configurer  \u00b7  Ctrl+M : flux",
                   fg=FG_DIM, bg=BG_NAV, font=FONT_MONO_S).pack(side="right", padx=PAD_X)

        for cid, *_r in self.COLS_PRISES:
            self.tree_prises.heading(
                cid, command=lambda c=cid: self._trier(self.tree_prises, c))
        for cid, *_r in self.COLS_SORTIES:
            self.tree_sorties.heading(
                cid, command=lambda c=cid: self._trier(self.tree_sorties, c))

        self.tree_prises.bind("<<TreeviewSelect>>", lambda _e: self._refresh_sorties())
        self.tree_prises.bind("<Double-1>", self._on_double_prise)
        self.tree_prises.bind("<Return>", lambda _e: self.edit_prise())
        self.tree_prises.bind("<space>", lambda _e: self.toggle_prise())
        self.tree_prises.bind("<Delete>", lambda _e: self.delete_prise())
        self.tree_prises.bind("<Button-3>", self._on_right_click)
        self.tree_prises.bind("<Button-1>", self._on_click_prises, add="+")
        self.tree_sorties.bind("<Double-1>", self._on_double_sortie)
        self.tree_sorties.bind("<Button-1>", self._on_click_sorties, add="+")

        self.ctx = tk.Menu(self, tearoff=0, bg=BG_NAV, fg=FG_LABEL,
                           activebackground=ACCENT, activeforeground="#ffffff")
        self.ctx.add_command(label="Configurer...", command=self.edit_prise)
        self.ctx.add_command(label="Sorties en serie...", command=self.add_serie)
        self.ctx.add_command(label="Voir le flux...", command=self.open_monitor)
        self.ctx.add_command(label="Activer / desactiver", command=self.toggle_prise)
        self.ctx.add_separator()
        self.ctx.add_command(label="Supprimer", command=self.delete_prise)

        self.bind("<Control-n>", lambda _e: self.add_prise())
        self.bind("<Control-s>", lambda _e: self.add_serie())
        self.bind("<Control-m>", lambda _e: self.open_monitor())
        self.bind("<F5>", lambda _e: self.restart())
        self.after(150, self._restore_sashes)

    def _restore_sashes(self):
        # Attendre que le panneau soit affiche a sa vraie taille : avant, les
        # positions seraient bornees a sa taille nulle (tableaux ecrases) ou
        # ecrasees par la mise en page initiale (demarrage lent, ouverture
        # de session chargee).
        if not self.paned.winfo_ismapped() or self.paned.winfo_height() < 100:
            self.after(100, self._restore_sashes)
            return
        sashes = self.config_data.get("sashes", [])
        # Positions ecrasees (tableaux reduits a rien) : la mise en page par
        # defaut vaut mieux que des tableaux caches.
        if len(sashes) != 2 or sashes[0] < 40 or sashes[1] - sashes[0] < 40:
            return
        for i, pos in enumerate(sashes):
            try:
                self.paned.sashpos(i, int(pos))
            except (tk.TclError, ValueError):
                pass

    def _set_window_icon(self):
        """Icone de fenetre/barre des taches -- seulement si Pillow est la.
        Son absence ne doit rien empecher : on garde l'icone par defaut."""
        try:
            from PIL import ImageTk
            self._icon_ref = ImageTk.PhotoImage(make_tray_image())
            self.iconphoto(True, self._icon_ref)
        except Exception:
            pass

    # =====================================================================
    # Journal
    # =====================================================================
    def log(self, message, niveau="info"):
        """Ajoute une ligne horodatee. Le journal est ecrit UNIQUEMENT depuis
        la boucle Tk : les fils d'ecoute n'y touchent pas, c'est l'interface
        qui detecte les changements d'etat et les consigne (voir _tick)."""
        suivre = self._journal_en_bas()
        self.journal.configure(state="normal")
        self.journal.insert("end", time.strftime("%H:%M:%S "), "ts")
        self.journal.insert("end", message + "\n", niveau)
        n = int(self.journal.index("end-1c").split(".")[0])
        if n > JOURNAL_LINES + 500:
            self.journal.delete("1.0", f"{n - JOURNAL_LINES}.0")
        self.journal.configure(state="disabled")
        if suivre:
            self.journal.see("end")

    def _journal_en_bas(self):
        """Le journal ne suit les nouvelles lignes que si on est deja en bas :
        remonte pour lire une ancienne ligne, on doit pouvoir y rester. On
        regarde si la derniere ligne est visible : la position de l'ascenseur
        serait faussee par la purge des lignes anciennes."""
        try:
            return self.journal.dlineinfo("end-1c") is not None
        except tk.TclError:
            return True

    def _clear_journal(self):
        self.journal.configure(state="normal")
        self.journal.delete("1.0", "end")
        self.journal.configure(state="disabled")

    # =====================================================================
    # Tableaux
    # =====================================================================
    def _prises(self):
        return self.config_data.setdefault("prises", [])

    def _selected(self):
        sel = self.tree_prises.selection()
        return int(sel[0]) if sel else None

    def _select_first(self):
        if self.tree_prises.get_children():
            first = self.tree_prises.get_children()[0]
            self.tree_prises.selection_set(first)
            self.tree_prises.focus(first)

    def _refresh_prises(self, rebuild=False):
        """Remplit / met a jour le tableau des prises. 'rebuild' recree les
        lignes (changement de structure) ; sinon on reecrit seulement les
        valeurs, ce qui preserve la selection et evite tout clignotement."""
        prises = self._prises()
        avant = list(self.tree_prises.get_children("")) if rebuild else None
        if rebuild:
            self.tree_prises.delete(*self.tree_prises.get_children())
            for i, _p in enumerate(prises):
                self.tree_prises.insert("", "end", iid=str(i))

        now = time.time()
        actives = 0
        debit_total = 0.0
        for i, p in enumerate(prises):
            iid = str(i)
            if not self.tree_prises.exists(iid):
                continue
            stats = self.stats_by_index.get(i)
            couleur, etat, tag = self._etat(p, stats, now)
            self._journalise_etat(p, stats, etat)

            debit = 0.0
            if stats is not None:
                # Point de reference memorise des le premier passage : sans
                # cela, la comparaison se ferait toujours avec l'instant
                # present et l'ecart de temps resterait nul -- aucun debit
                # ne serait jamais calcule.
                if i not in self._prev:
                    self._prev[i] = (now, stats.rx)
                t_prec, rx_prec = self._prev[i]
                dt = now - t_prec
                # Moyenne sur 2 s glissantes : mesure sur un intervalle plus
                # court, le debit retomberait a zero entre deux rafales.
                if dt >= 2.0:
                    debit = max(0.0, (stats.rx - rx_prec) / dt)
                    self._prev[i] = (now, stats.rx)
                    self._debits[i] = debit
                else:
                    debit = self._debits.get(i, 0.0)
                if stats.running:
                    actives += 1
            debit_total += debit

            self.tree_prises.item(
                iid, text=" " + (COCHE if p.get("actif") else NON_COCHE),
                image=dot_image(couleur),
                values=(etat, p.get("nom", ""),
                        f"{p.get('ecoute_ip', '0.0.0.0')}:{p.get('port') or '-'}",
                        f"{debit:.1f}/s" if debit else "\u2014",
                        _fmt_int(stats.rx) if stats else "\u2014",
                        _fmt_int(stats.tx) if stats else "\u2014",
                        (stats.last_line if stats else "") or ""),
                tags=(tag,) if tag else ())

        self._trier_ou_garder(self.tree_prises, avant)
        self.lbl_prises.configure(
            text=f"{actives} en service sur {len(prises)}")
        self.status.configure(
            text=f"{actives} prise(s) en service   \u00b7   {debit_total:.1f} "
                 f"datagrammes/s   \u00b7   v{APP_VERSION}")

    def _trier_ou_garder(self, tree, avant=None):
        """Tri en direct, sauf tant que le pointeur survole le tableau : les
        lignes ne doivent pas fuir sous la souris, un clic sur une case
        viserait la voisine. Apres une reconstruction (clic sur une case,
        avec un tri par etat par exemple), l'ordre affiche juste avant est
        remis tel quel."""
        if not self._pointeur_sur(tree):
            self._appliquer_tri(tree)
        elif avant is not None:
            if sorted(avant, key=int) == sorted(tree.get_children(""), key=int):
                for pos, iid in enumerate(avant):
                    tree.move(iid, "", pos)
            else:
                self._appliquer_tri(tree)

    def _pointeur_sur(self, widget):
        """Le pointeur survole-t-il ce tableau ? Pendant ce temps, pas de tri
        en direct : les lignes bougeraient sous la souris et un clic sur une
        case basculerait une autre prise que celle visee."""
        try:
            return self.winfo_containing(*self.winfo_pointerxy()) is widget
        except (tk.TclError, KeyError):
            return False

    def _refresh_sorties(self):
        """Tableau du bas : les sorties de la prise selectionnee, avec leurs
        compteurs propres."""
        i = self._selected()
        avant = list(self.tree_sorties.get_children("")) if i == self._sorties_de else None
        self._sorties_de = i
        self.tree_sorties.delete(*self.tree_sorties.get_children())
        if i is None or i >= len(self._prises()):
            self.lbl_sorties.configure(text="aucune prise selectionnee")
            return
        p = self._prises()[i]
        stats = self.stats_by_index.get(i)
        self.lbl_sorties.configure(text=f"{p.get('nom')}  \u2014  "
                                        f"{p.get('ecoute_ip')}:{p.get('port')}")
        for j, s in enumerate(p.get("sorties", [])):
            actif = bool(s.get("actif", True))
            c = stats.per_out.get(j, VIDE_SORTIE) if stats else VIDE_SORTIE
            couleur, etat, tag = self._etat_sortie(p, s, c, stats)
            self.tree_sorties.insert(
                "", "end", iid=str(j),
                text=" " + (COCHE if actif else NON_COCHE), image=dot_image(couleur),
                values=(etat, s.get("ip", ""), s.get("port", ""), s.get("nom", ""),
                        _fmt_int(c[0]), _fmt_int(c[1]) if c[1] else "\u2014"),
                tags=(tag,) if tag else ())
        if avant is None:
            self._appliquer_tri(self.tree_sorties)   # autre prise : tri normal
        else:
            self._trier_ou_garder(self.tree_sorties, avant)

    def _refresh_sorties_values(self):
        """Mise a jour des compteurs et de l'etat (sans reconstruire les
        lignes) : une sortie qui se met a echouer vire au rouge sans
        attendre qu'on change de prise selectionnee."""
        i = self._selected()
        if i is None or i >= len(self._prises()):
            return
        stats = self.stats_by_index.get(i)
        if stats is None:
            return
        p = self._prises()[i]
        for j, s in enumerate(p.get("sorties", [])):
            iid = str(j)
            if not self.tree_sorties.exists(iid):
                continue
            c = stats.per_out.get(j, VIDE_SORTIE)
            couleur, etat, tag = self._etat_sortie(p, s, c, stats)
            vals = list(self.tree_sorties.item(iid, "values"))
            vals[0] = etat
            vals[4] = _fmt_int(c[0])
            vals[5] = _fmt_int(c[1]) if c[1] else "\u2014"
            self.tree_sorties.item(iid, values=vals, image=dot_image(couleur),
                                   tags=(tag,) if tag else ())
        if not self._pointeur_sur(self.tree_sorties):
            self._appliquer_tri(self.tree_sorties)

    @staticmethod
    def _etat_sortie(prise, sortie, c, stats):
        """(couleur, etat, balise) d'une sortie (c = compteurs, voir Stats),
        d'apres le DERNIER envoi et le dernier refus : une sortie qui se met
        a echouer passe au rouge, celle dont le programme revient repasse au
        vert. Windows limite le nombre de refus signales par seconde : le
        rouge tient Repeater.MEMOIRE_REFUS apres le dernier."""
        if not sortie.get("actif", True):
            return COLOR_IDLE, "Inactive", "off"
        if c[4] or _vers_entree(sortie.get("ip", ""), sortie.get("port"),
                                prise.get("ecoute_ip"), prise.get("port")):
            return COLOR_ERR, "Boucle", "err"
        if stats is None or stats.error:
            # Prise hors service ou en erreur : la sortie n'est pas servie.
            return COLOR_IDLE, "Inactive", "off"
        if c[2] is False or (c[3] and time.monotonic() - c[3] < Repeater.MEMOIRE_REFUS):
            return COLOR_ERR, "Injoignable", "err"
        if c[2]:
            return COLOR_OK, "Diffuse", None
        return COLOR_WARN, "En attente", None

    @staticmethod
    def _etat(prise, stats, now):
        if not prise.get("actif"):
            return COLOR_IDLE, "Hors service", "off"
        if stats is None:
            return COLOR_IDLE, "Non demarree", "off"
        if stats.error:
            return COLOR_ERR, "Erreur", "err"
        if not stats.running:
            return COLOR_WARN, "Demarrage", None
        if stats.last_rx and now - stats.last_rx < 3.0:
            return COLOR_OK, "Flux present", None
        return COLOR_WARN, "Aucune trame", None

    @staticmethod
    def _cle_prise(prise):
        """Identite d'une prise pour le journal et le report de la derniere
        reception d'une relance a l'autre : l'objet lui-meme, qui survit aux
        relances (deux prises de meme nom et meme port restent distinctes),
        et ce qu'elle ecoute (changer de port en fait une nouvelle prise)."""
        return (id(prise), prise.get("ecoute_ip"), prise.get("port"))

    def _journalise_etat(self, prise, stats, etat):
        """Consigne les CHANGEMENTS d'etat, pas l'etat courant : le journal
        doit se lire comme un historique, pas defiler en boucle.

        La memoire des etats est indexee par l'identite de la prise (voir
        _cle_prise) et NON par rang dans la liste : les fils sont recrees a
        chaque modification, et un rang aurait fait reapparaitre "en ecoute,
        en attente de trames" pour toutes les prises a chaque case cochee."""
        cle = self._cle_prise(prise)
        precedent = self._etats.get(cle)
        if precedent == etat or etat == "Demarrage":
            # Demarrage : etat de passage d'un fil qui (re)demarre, l'etat
            # d'avant tient toujours.
            return
        if etat == "Aucune trame" and stats is not None:
            if not stats.rx and time.time() - stats.debut < 3.0:
                # Fils tout juste relances : rien de significatif avant le
                # delai de "Flux present".
                return
            if (precedent == "Flux present"
                    and time.time() - (stats.last_rx or stats.debut) < 10.0):
                # Source lente (AIS au mouillage, capteur a 0,2 Hz) : quelques
                # secondes de silence ne sont pas une perte de flux.
                return
        self._etats[cle] = etat
        nom = prise.get("nom", "?")
        port = prise.get("port", "?")
        if precedent is None and etat in ("Hors service", "Non demarree"):
            return
        if etat == "Erreur":
            self.log(f"{nom} ({port}) : {stats.error if stats else 'erreur'}", "err")
        elif etat == "Flux present":
            self.log(f"{nom} ({port}) : flux present", "ok")
        elif etat == "Aucune trame":
            if precedent == "Flux present":
                self.log(f"{nom} ({port}) : plus aucune trame recue", "warn")
            else:
                self.log(f"{nom} ({port}) : en ecoute, en attente de trames", "info")
        elif etat == "Hors service":
            self.log(f"{nom} ({port}) : mise hors service", "info")

    def _trier(self, tree, colonne):
        """Clic sur un titre de colonne : tri croissant, puis decroissant au
        clic suivant, puis retour a l'ordre de la configuration au
        troisieme -- on peut toujours revenir a l'ordre qu'on a soi-meme
        etabli, ce qu'un tri a deux etats ne permet pas."""
        if tree.tri and tree.tri[0] == colonne:
            tree.tri = (colonne, True) if not tree.tri[1] else None
        else:
            tree.tri = (colonne, False)
        for cid, titre in tree.titres.items():
            fleche = ""
            if tree.tri and tree.tri[0] == cid:
                fleche = "  \u25be" if tree.tri[1] else "  \u25b4"
            tree.heading(cid, text=titre + fleche)   # l'ancrage est conserve
        if tree.tri is None:
            # Retour a l'ordre de la configuration : les identifiants de
            # ligne SONT les rangs, il suffit de les remettre dans l'ordre.
            for pos, iid in enumerate(sorted(tree.get_children(""), key=int)):
                tree.move(iid, "", pos)
        else:
            self._appliquer_tri(tree)

    @staticmethod
    def _appliquer_tri(tree):
        """Reordonne les lignes affichees. On DEPLACE les lignes existantes
        au lieu de les recreer : les identifiants restent les rangs dans la
        configuration, donc la selection, les compteurs et les bascules
        continuent de designer la bonne prise."""
        if not tree.tri:
            return
        colonne, inverse = tree.tri
        lignes = [(sort_key(colonne, tree.set(iid, colonne)), iid)
                  for iid in tree.get_children("")]
        try:
            lignes.sort(key=lambda x: x[0], reverse=inverse)
        except TypeError:
            return
        for pos, (_v, iid) in enumerate(lignes):
            tree.move(iid, "", pos)

    def _on_double_prise(self, event):
        # Un double-clic dans le vide (sous la derniere ligne) ne doit pas
        # ouvrir la configuration d'une prise choisie au hasard ; sur la case
        # a cocher non plus, sinon le second clic rouvrirait la fenetre juste
        # apres avoir bascule la prise.
        if self.tree_prises.identify_column(event.x) == "#0":
            return "break"
        if self.tree_prises.identify_row(event.y):
            self.edit_prise()

    def _on_click_prises(self, event):
        """Clic sur la case a cocher : la prise entre ou sort de service.
        Une seule zone cliquable, la plus a gauche -- ailleurs, le clic
        selectionne normalement."""
        if self.tree_prises.identify_region(event.x, event.y) != "tree":
            return
        row = self.tree_prises.identify_row(event.y)
        if not row:
            return
        i = int(row)
        p = self._prises()[i]
        # Le changement lui-meme n'est pas journalise ici : _journalise_etat
        # s'en charge au prochain rafraichissement, et le faire aux deux
        # endroits ecrivait la ligne en double.
        p["actif"] = not p.get("actif", True)
        self._commit(select=i)
        return "break"

    def _on_click_sorties(self, event):
        """Meme principe sur une sortie : on coupe une destination sans
        ouvrir la configuration de la prise."""
        if self.tree_sorties.identify_region(event.x, event.y) != "tree":
            return
        row = self.tree_sorties.identify_row(event.y)
        i = self._selected()
        if not row or i is None:
            return
        j = int(row)
        sorties = self._prises()[i].get("sorties", [])
        if j >= len(sorties):
            return
        s = sorties[j]
        s["actif"] = not s.get("actif", True)
        self.log(f"sortie {s['ip']}:{s['port']} : "
                 f"{'activee' if s['actif'] else 'desactivee'}", "info")
        self._commit(select=i)
        return "break"

    def _on_double_sortie(self, event):
        """Double-clic sur une sortie : on ouvre la configuration de la prise
        avec cette sortie deja selectionnee -- le chemin le plus court entre
        "cette sortie ne sert rien" et "je la corrige". Sur la case a cocher,
        rien : le premier clic a deja bascule la sortie."""
        if self.tree_sorties.identify_column(event.x) == "#0":
            return "break"
        row = self.tree_sorties.identify_row(event.y)
        if not row:
            return
        self.edit_prise(sortie=int(row))

    def _on_right_click(self, event):
        row = self.tree_prises.identify_row(event.y)
        if row:
            self.tree_prises.selection_set(row)
            self.tree_prises.focus(row)
            self.ctx.tk_popup(event.x_root, event.y_root)

    # =====================================================================
    # Actions
    # =====================================================================
    def add_prise(self):
        dlg = PriseDialog(self)
        if dlg.result:
            self._prises().append(dlg.result)
            self.log(f"prise \"{dlg.result['nom']}\" creee sur le port "
                     f"{dlg.result['port']} ({len(dlg.result['sorties'])} sortie(s))",
                     "info")
            self._commit(select=len(self._prises()) - 1)

    def edit_prise(self, sortie=None):
        i = self._selected()
        if i is None:
            return
        avant = self._prises()[i]
        dlg = PriseDialog(self, avant, sortie)
        if not dlg.result:
            return
        # La prise est mise a jour EN PLACE : sa fenetre Flux et sa memoire
        # du journal la suivent. Et si la liste a change pendant le dialogue,
        # c'est bien CETTE prise qui est modifiee, pas celle de son ancien
        # rang (rien du tout si elle a ete supprimee entre-temps).
        rang = next((k for k, q in enumerate(self._prises()) if q is avant), None)
        if rang is None:
            return
        avant.clear()
        avant.update(dlg.result)
        self.log(f"prise \"{avant['nom']}\" modifiee : port "
                 f"{avant['port']}, {len(avant['sorties'])} sortie(s)", "info")
        self._commit(select=rang)

    def add_serie(self):
        """Sorties en serie directement depuis la fenetre principale, sur la
        prise selectionnee -- sans passer par sa configuration."""
        i = self._selected()
        if i is None:
            messagebox.showinfo("Sorties en serie",
                                "Selectionnez d'abord une prise.", parent=self)
            return
        p = self._prises()[i]
        dlg = SerieDialog(self, p.get("port", 0),
                          {(s["ip"], s["port"]) for s in p.get("sorties", [])},
                          p.get("ecoute_ip") or "0.0.0.0")
        if dlg.result:
            p.setdefault("sorties", []).extend(dlg.result)
            premiers = ", ".join(f"{s['ip']}:{s['port']}" for s in dlg.result[:3])
            suite = "..." if len(dlg.result) > 3 else ""
            self.log(f"{len(dlg.result)} sortie(s) ajoutee(s) a \"{p.get('nom')}\" : "
                     f"{premiers}{suite}", "info")
            self._commit(select=i)

    def toggle_prise(self):
        i = self._selected()
        if i is None:
            return
        p = self._prises()[i]
        p["actif"] = not p.get("actif", True)
        self._commit(select=i)

    def delete_prise(self):
        i = self._selected()
        if i is None:
            return
        p = self._prises()[i]
        if not messagebox.askyesno("Supprimer",
                                   f"Supprimer la prise \"{p.get('nom')}\" "
                                   f"(port {p.get('port')}) et ses sorties ?",
                                   parent=self):
            return
        self._prises().pop(i)
        self.log(f"prise \"{p.get('nom')}\" ({p.get('port')}) supprimee", "info")
        reste = len(self._prises())
        self._commit(select=min(i, reste - 1) if reste else None)

    def restart(self):
        self.log("relance de l'ecoute", "info")
        self._commit(select=self._selected())

    def _commit(self, select=None):
        """Enregistre, verifie, relance les fils et remet les tableaux a jour.
        Un seul chemin pour toutes les modifications : impossible de se
        retrouver avec un reglage affiche mais pas applique."""
        for probleme in self._validate(self._prises()):
            self.log(probleme, "warn")
        try:
            self._memorise_fenetre()
            save_config(self.config_data)
        except OSError as e:
            self.log(f"reglages non enregistres : {e}", "err")
        self.stop_all()
        self.start_all()
        self._prev.clear()
        self._debits.clear()
        vivantes = {self._cle_prise(p) for p in self._prises()}
        self._etats = {k: v for k, v in self._etats.items() if k in vivantes}
        self._refresh_prises(rebuild=True)
        if select is not None and self.tree_prises.exists(str(select)):
            self.tree_prises.selection_set(str(select))
            self.tree_prises.focus(str(select))
        elif self._prises():
            self._select_first()
        self._refresh_sorties()

    @staticmethod
    def _validate(prises):
        """Signale ce qui ne peut pas marcher, ou pas comme on le croit :
        - deux prises actives sur le meme port d'entree (la seconde ne peut
          pas s'y lier), ou une prise active sans port valide ;
        - une sortie vers l'entree de sa propre prise : elle n'est jamais
          emise ;
        - une BOUCLE entre prises (A -> B -> A) : une trame y tournerait sans
          fin et saturerait la machine, ces prises ne sont pas demarrees.
          Une fusion (A et B -> C) n'en est pas une ;
        - une sortie en double : chaque trame lui partirait deux fois."""
        problems = []
        entrees = {}
        for p in prises:
            if not p.get("actif"):
                continue
            if not p.get("port"):
                problems.append(f"{p['nom']} : port d'ecoute invalide, prise non demarree")
                continue
            if p["port"] in entrees:
                problems.append(f"{p['nom']} : le port {p['port']} est deja ecoute "
                                f"par \"{entrees[p['port']]}\"")
            entrees.setdefault(p["port"], p["nom"])
        for p in prises:
            if not p.get("actif") or not p.get("port"):
                continue
            vues = set()
            for s in p.get("sorties", []):
                if s.get("actif") and not (s.get("ip") and s.get("port")):
                    problems.append(f"{p['nom']} : une sortie sans adresse ou au port "
                                    "invalide (fichier retouche ?) est ignoree")
                if not (s.get("actif") and s.get("ip") and s.get("port")):
                    continue
                if _vers_entree(s["ip"], s["port"], p.get("ecoute_ip"), p["port"]):
                    problems.append(f"{p['nom']} : la sortie {s['ip']}:{s['port']} "
                                    "renvoie vers sa propre entree -- boucle, elle "
                                    "n'est pas emise")
                cle = (s["ip"].strip().lower(), s["port"])
                if cle in vues:
                    problems.append(f"{p['nom']} : la sortie {s['ip']}:{s['port']} "
                                    "est en double, chaque trame lui part deux fois")
                vues.add(cle)
        boucle = _prises_en_boucle(prises)
        if boucle:
            noms = ", ".join(f"\"{prises[i]['nom']}\"" for i in sorted(boucle))
            problems.append(f"boucle entre les prises {noms} : leurs sorties se "
                            "renvoient le flux, elles ne sont pas demarrees")
        return problems

    # =====================================================================
    # Moniteur
    # =====================================================================
    def open_monitor(self):
        i = self._selected()
        if i is None:
            return
        p = self._prises()[i]
        win = self.monitors.get(id(p))
        if win is not None and win.winfo_exists():
            win.deiconify()
            win.lift()
            return
        self.monitors[id(p)] = MonitorWindow(self, p, self.stats_by_index.get(i))

    def _rebind_monitors(self):
        """Apres un redemarrage des fils, chaque fenetre Flux ouverte suit le
        NOUVEL objet de statistiques de SA prise -- sinon elle resterait
        figee sur des compteurs morts, ce qui ferait croire a une panne.
        Celle d'une prise supprimee se ferme ; un titre suit le nouveau nom
        ou le nouveau port."""
        rangs = {id(p): i for i, p in enumerate(self._prises())}
        for cle, win in list(self.monitors.items()):
            if not win.winfo_exists():
                self.monitors.pop(cle, None)
                continue
            i = rangs.get(cle)
            if i is None:
                win.close()
            else:
                win.retitrer()
                win.set_stats(self.stats_by_index.get(i))

    # =====================================================================
    # Fils d'ecoute
    # =====================================================================
    def start_all(self):
        # Derniere reception reportee d'une generation de fils a la suivante :
        # une relance (case cochee, F5) ne doit ni faire croire a une perte
        # de flux, ni faire clignoter l'etat des prises.
        anciens = {getattr(st, "cle", None): st for st in self.stats_by_index.values()}
        en_boucle = _prises_en_boucle(self._prises())
        self.stats_by_index = {}
        self.threads = []
        for i, prise in enumerate(self._prises()):
            if not prise.get("actif") or not prise.get("port"):
                continue
            stats = Stats()
            stats.cle = self._cle_prise(prise)
            vieux = anciens.get(stats.cle)
            if vieux is not None:
                stats.last_rx, stats.last_line = vieux.last_rx, vieux.last_line
            self.stats_by_index[i] = stats
            if i in en_boucle:
                stats.error = "boucle avec une autre prise : non demarree (voir le journal)"
                continue
            th = Repeater(prise, stats)
            th.start()
            self.threads.append((th, stats))
        self._rebind_monitors()

    def stop_all(self):
        for th, _stats in self.threads:
            th.stop()
        # Un fil en ecoute sort au bout du delai de reception (Repeater.ATTENTE,
        # 0,1 s), un fil qui attend un nouvel essai en 0,2 s au plus ; on
        # attend qu'ils soient sortis pour que les ports soient bien liberes
        # avant d'etre relies. (Le fil qui resout les noms ne tient aucun port.)
        for th, _stats in self.threads:
            th.join(timeout=1.0)
        self.threads = []

    def _tick(self):
        self._refresh_prises()
        self._refresh_sorties_values()
        if self.v_trames.get():
            self._echo_trames()
        else:
            # Option coupee : a sa reprise, le journal repart des trames a
            # venir, sans deverser l'arriere accumule entre-temps.
            self._journal_stats = None
        self._tick_id = self.after(500, self._tick)

    def _echo_trames(self):
        """Recopie dans le journal les trames de la prise selectionnee. Le
        debit est volontairement plafonne : sur un flux rapide, tout ecrire
        rendrait le journal illisible et ferait ramer l'interface."""
        i = self._selected()
        stats = self.stats_by_index.get(i) if i is not None else None
        if stats is None:
            self._journal_stats = None
            return
        if stats is not self._journal_stats:
            # Autre prise selectionnee, fils relances ou option remise : les
            # numeros d'ordre sont propres a chaque prise. Repartir de
            # l'ancien numero masquerait ses trames jusqu'a ce qu'elle le
            # rattrape ; on reprend donc a partir de sa derniere trame.
            self._journal_stats = stats
            self._journal_seq = stats.seq
            return
        nouvelles = stats.since(self._journal_seq)
        if not nouvelles:
            return
        self._journal_seq = nouvelles[-1][0]
        if len(nouvelles) > 20:
            omises = len(nouvelles) - 20
            nouvelles = nouvelles[-20:]
        else:
            omises = 0
        suivre = self._journal_en_bas()
        self.journal.configure(state="normal")
        if omises:
            self.journal.insert("end", f"           ({omises} trame(s) non affichee(s))\n",
                                "warn")
        for _seq, t, _src, texte in nouvelles:
            for ligne in texte.split("\n"):
                if ligne.strip():
                    self.journal.insert("end", _hhmmss(t) + " ", "ts")
                    self.journal.insert("end", ligne + "\n", "trame")
        n = int(self.journal.index("end-1c").split(".")[0])
        if n > JOURNAL_LINES + 500:
            self.journal.delete("1.0", f"{n - JOURNAL_LINES}.0")
        self.journal.configure(state="disabled")
        if suivre:
            self.journal.see("end")

    # =====================================================================
    # Options
    # =====================================================================
    def _save_options(self):
        self.config_data["close_to_tray"] = bool(self.v_tray.get())
        self.config_data["start_minimized"] = bool(self.v_min.get())
        self.config_data["autostart"] = bool(self.v_auto.get())
        self.config_data["journal_trames"] = bool(self.v_trames.get())
        try:
            save_config(self.config_data)
        except OSError:
            pass

    def _toggle_autostart(self):
        """Un simple .bat depose dans le dossier Demarrage : pas de base de
        registre, pas de raccourci a fabriquer, et l'utilisateur peut le
        voir et le supprimer a la main."""
        path = _startup_bat_path()
        try:
            if self.v_auto.get():
                _ecrire_demarrage()
                self.log("lancement au demarrage de Windows : active", "info")
            elif path and os.path.exists(path):
                os.remove(path)
                self.log("lancement au demarrage de Windows : desactive", "info")
        except (OSError, UnicodeError) as e:
            self.v_auto.set(not self.v_auto.get())
            self.log(f"demarrage automatique : {e}", "err")
        self._save_options()

    def _sync_autostart(self):
        """Au lancement, le .bat du dossier Demarrage suit la copie lancee :
        deplacer le dossier, passer du script a Multiprise.exe ou changer de
        Python ne laisse pas Windows relancer l'ancienne (ou rien du tout).
        Supprime a la main, il n'est PAS recree : la case reste decochee,
        pour dire ce qui est."""
        path = _startup_bat_path()
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
                    actuel = fh.read()
            except OSError:
                actuel = None
            if actuel != _contenu_demarrage():
                try:
                    _ecrire_demarrage()
                    self.log("lancement au demarrage de Windows : pointe desormais sur "
                             f"{_cible_lancement()}", "info")
                except (OSError, UnicodeError) as e:
                    self.log(f"demarrage automatique : {e}", "err")
        if bool(self.config_data.get("autostart")) != bool(self.v_auto.get()):
            self._save_options()

    # =====================================================================
    # Fermeture / zone de notification
    # =====================================================================
    def _on_close(self):
        """La croix RANGE l'application si l'option est active et si pystray
        repond : la repartition continue de tourner, sans quoi fermer la
        fenetre couperait le flux de tous les programmes clients."""
        if self.v_tray.get() and self._hide_to_tray():
            return
        self._shutdown()

    def _hide_to_tray(self):
        try:
            import pystray
        except Exception:
            return False
        try:
            if self._tray_icon is None:
                menu = pystray.Menu(
                    pystray.MenuItem(f"Ouvrir {APP_TITLE}", self._tray_open, default=True),
                    pystray.MenuItem("Quitter", self._tray_quit))
                self._tray_icon = pystray.Icon("multiprise", make_tray_image(),
                                               f"{APP_TITLE} v{APP_VERSION}", menu)
                # Boucle de l'icone dans son propre fil : la boucle Tk
                # continue de tourner, fenetre simplement retiree.
                self._tray_icon.run_detached()
            # Taille et poignees retenues AVANT de retirer la fenetre : quitter
            # ensuite depuis l'icone ne trouve plus qu'une fenetre retiree.
            self._memorise_fenetre()
            self.withdraw()
            return True
        except Exception:
            self._tray_icon = None
            return False

    # Les rappels pystray arrivent dans le FIL DE L'ICONE : ils ne font que
    # reposter vers la boucle Tk, seule habilitee a toucher aux widgets.
    def _tray_open(self, icon=None, item=None):
        self.after(0, self._restore)

    def _tray_quit(self, icon=None, item=None):
        self.after(0, self._shutdown)

    def _restore(self):
        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def _shutdown(self):
        try:
            self.after_cancel(self._tick_id)
        except (AttributeError, tk.TclError):
            pass
        try:
            self._memorise_fenetre()
            save_config(self.config_data)
        except (OSError, tk.TclError):
            pass
        for win in list(self.monitors.values()):
            try:
                win.close()
            except tk.TclError:
                pass
        self.stop_all()
        if self._tray_icon is not None:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        self.destroy()


def _python_exe():
    """Interpreteur du lancement automatique : PYTHONW.EXE, sans console, a
    cote de celui qui fait tourner l'application ici. Une console reduite
    resterait dans la barre des taches toute la session, sans nom, et la
    fermer tuerait la multiprise sans rien enregistrer."""
    exe = sys.executable or "pythonw.exe"
    if exe.lower().endswith("python.exe"):
        cand = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(cand):
            return cand
    return exe


def _cible_lancement():
    """Ce que le lancement automatique execute : l'exe lui-meme s'il s'agit
    de Multiprise.exe (le .py n'existe pas a cote de lui), sinon le script."""
    if FROZEN:
        return os.path.abspath(sys.executable)
    return os.path.join(APP_DIR, os.path.basename(__file__))


def _contenu_demarrage():
    """Le .bat du dossier Demarrage.
    - chcp 65001 : cmd lit la suite du fichier en UTF-8. Sans lui, un chemin
      accentue (Telechargements, compte Windows a nom accentue...) serait
      relu dans la page de codes de la console (850), et introuvable.
    - % double : sinon cmd le prendrait pour le debut d'une variable.
    - Pas de /min : l'option "Demarrer reduit" decide de la fenetre."""
    if FROZEN:
        commande = f'"{_cible_lancement()}"'
    else:
        commande = f'"{_python_exe()}" "{_cible_lancement()}"'
    commande = commande.replace("%", "%%")
    return '@echo off\r\nchcp 65001 >nul\r\nstart "" ' + commande + "\r\n"


def _ecrire_demarrage():
    path = _startup_bat_path()
    if not path:
        raise OSError("dossier de demarrage introuvable")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # newline="" : les \r\n ecrits ici restent tels quels (en mode texte,
    # Windows en ferait des \r\r\n).
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(_contenu_demarrage())


def _startup_bat_path():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs",
                        "Startup", f"{APP_TITLE}.bat")


# =========================================================================
# Instance unique + lancement
# =========================================================================

def acquire_single_instance():
    """(verrou, deja_lancee).

    Sous Windows, un mutex nomme : le systeme le libere tout seul si
    l'application est tuee, et il ne depend d'aucun port. Un port de
    bouclage peut etre pris par un autre programme, ou reserve par Windows
    (Hyper-V, WSL2, Docker) : la multiprise croirait a tort en tourner une
    autre, et refuserait de demarrer.

    Hors Windows, repli sur un port : seul "port deja pris" designe une
    autre multiprise, toute autre erreur laisse demarrer sans verrou."""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        k32.CreateMutexW.restype = wintypes.HANDLE
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        h = k32.CreateMutexW(None, False, MUTEX_NAME)
        erreur = ctypes.get_last_error()
        if h:
            if erreur == 183:   # ERROR_ALREADY_EXISTS
                k32.CloseHandle(h)
                return None, True
            return h, False   # garde jusqu'a la fin du processus
        if erreur == 5:
            # ERROR_ACCESS_DENIED : le mutex existe, tenu par une multiprise
            # lancee en administrateur.
            return None, True
    except Exception:   # pas Windows (ou ctypes indisponible) : repli
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
        return s, False
    except OSError as e:
        s.close()
        code = getattr(e, "winerror", None) or e.errno
        return None, code in (10048, 48, 98)


def main():
    verrou, deja = acquire_single_instance()
    if deja:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(APP_TITLE,
                            f"{APP_TITLE} tourne deja.\n\nRetrouvez la fenetre "
                            "(barre des taches ou icone de la zone de notification, "
                            "pres de l'horloge).")
        root.destroy()
        return
    try:
        App().mainloop()
    finally:
        if isinstance(verrou, socket.socket):
            try:
                verrou.close()
            except OSError:
                pass


if __name__ == "__main__":
    main()
