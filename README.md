<div align="center">

# Multiprise — Répartiteur de flux UDP

**Un port écouté, plusieurs programmes servis.**

![Version](https://img.shields.io/badge/version-3.5-2ea44f)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)
![tkinter](https://img.shields.io/badge/interface-tkinter-3776AB?logo=python&logoColor=white)
![NMEA 0183](https://img.shields.io/badge/flux-NMEA%200183%20%2F%20UDP-0a7ea4)
![Plateforme](https://img.shields.io/badge/plateforme-Windows-0078D6?logo=windows&logoColor=white)
![Licence](https://img.shields.io/badge/licence-GPL--3.0--or--later-blue)

</div>

**Français** · [English](README.en.md)

---

> [!NOTE]
> **La multiprise doit être seule sur le port d'entrée** : les programmes qui écoutaient jusqu'ici le
> port de la passerelle passent sur une prise fille (4101, 4201…). **Fermer la fenêtre ne quitte pas**
> si `pystray` et `pillow` sont installés : la répartition continue depuis la zone de notification, et
> seul *Quitter* l'arrête. Au premier lancement, autorisez Python (`pythonw.exe`) ou
> `Multiprise.exe` dans le pare-feu Windows pour les réseaux privés, sinon les prises n'entendent
> rien du réseau du bord.

Multiprise reçoit un flux UDP — typiquement les trames NMEA 0183 que la
passerelle du bord diffuse sur le réseau — et en recopie chaque datagramme,
octet pour octet, vers autant de destinations que voulu. Elle montre en
direct ce qui entre et ce qui sort, prise par prise et destination par
destination : une destination muette se voit tout de suite.

**À qui ça sert.** À quiconque doit faire lire un même flux UDP à plusieurs
programmes du même PC : logiciel de navigation, générateur de polaires
([Allure](https://github.com/theptitprince/Allure)), enregistreur, afficheur
AIS… Sous Windows, deux programmes ne peuvent pas écouter proprement le même
port UDP : le second qui s'y lie vole le flux au premier, ou échoue, et les
trames n'arrivent qu'à un seul des deux. Multiprise reprend le principe de
la multiprise électrique : elle seule est branchée sur la prise murale (le
vrai port, 4001 par exemple), et chaque programme se branche sur une prise
fille (4101, 4201…).

```
NMEA (réseau bord) --> [4001] MULTIPRISE --> 127.0.0.1:4101     Allure
                                         --> 127.0.0.1:4201     autre outil
                                         --> 192.168.1.50:4001  autre PC
```

Version actuelle : 3.5 — l'historique des livraisons est dans
[CHANGELOG.md](CHANGELOG.md).

## Sommaire

- [1. Installation](#1-installation)
- [2. Les fichiers](#2-les-fichiers)
- [3. Lancement](#3-lancement)
- [4. Prise en main](#4-prise-en-main)
- [5. Comment ça marche](#5-comment-ça-marche)
- [6. L'interface](#6-linterface)
- [7. Ce que le programme crée à côté de lui](#7-ce-que-le-programme-crée-à-côté-de-lui)
- [8. Construire un exécutable](#8-construire-un-exécutable)
- [9. En cas de souci](#9-en-cas-de-souci)
- [10. Licence](#10-licence)

---

## 1. Installation

### Python

Il faut **Python 3.8 ou plus récent**, avec **tkinter**.

Installez Python depuis <https://www.python.org/downloads/> et **cochez
deux cases** dans l'installateur :

- `Add Python to PATH` (sur le premier écran)
- `tcl/tk and IDLE` (sur l'écran « Optional Features »)

Sans la seconde, l'application ne peut pas s'ouvrir : tkinter est ce qui
dessine toute l'interface.

### Le plus simple : `installer_dependances.bat`

Double-cliquez sur **`installer_dependances.bat`**. Il vérifie que Python
(3.8 ou plus récent) et tkinter sont là — ils ne s'installent pas avec
`pip`, il dit quoi faire s'ils manquent —, remet `pip` en place s'il a
disparu, puis installe `pystray` et `pillow` s'ils sont absents (il faut une
connexion internet pour cette étape).

### À la main

Pour vérifier Python, ouvrez PowerShell et tapez :

```powershell
python --version
python -m tkinter
```

La première commande doit afficher un numéro de version, la seconde doit
ouvrir une petite fenêtre de test — fermez-la. Puis, facultatif :

```powershell
python -m pip install "pystray>=0.19" "pillow>=8.2"
```

Multiprise n'a besoin d'aucune bibliothèque pour répartir les flux. Ces deux-là
apportent le confort d'un outil qui tourne en permanence :

| Bibliothèque | Ce qu'elle apporte | Sans elle |
|---|---|---|
| `pystray` + `pillow` | la croix range la fenêtre près de l'horloge : la répartition continue, l'icône garde un menu *Ouvrir* / *Quitter* | la croix ferme le programme, et coupe le flux de tous les programmes servis ; *Démarrer réduit* réduit seulement dans la barre des tâches |
| `pillow` | l'icône de la fenêtre et de la barre des tâches, et celle de `Multiprise.exe` | icône par défaut |

Avec un `pystray` antérieur à 0.19, la zone de notification ne fonctionne
pas : la croix quitte (`installer_dependances.bat` le met à jour).

---

## 2. Les fichiers

Récupérez le dépôt, au choix :

- bouton vert **Code → Download ZIP** sur la page GitHub, puis décompressez
  l'archive dans un dossier (par exemple `C:\Multiprise`) ;
- ou, si vous avez git :

```powershell
git clone https://github.com/theptitprince/Multiprise.git C:\Multiprise
```

| Fichier | Rôle |
|---|---|
| `multiprise.py` | le programme, en un seul fichier |
| `Multiprise.bat` | lancement par double-clic, sans fenêtre de console |
| `installer_dependances.bat` | vérifie Python et tkinter, installe `pystray` et `pillow` |
| `construire_exe.bat` | construit `Multiprise.exe`, autonome (voir « Construire un exécutable ») |
| `CHANGELOG.md` | l'historique des versions |
| `LICENSE` | le texte de la licence (voir « Licence ») |
| `NOTICE` | les conditions additionnelles de la licence (article 7) : la mention à conserver |

`multiprise.py` est organisé en sections :

| Section | Rôle |
|---|---|
| `Repeater` | un fil par prise : écoute le port, recopie chaque datagramme vers les sorties actives (celles vers ce PC par leur propre socket, pour voir si un programme les écoute) |
| `Stats` | les compteurs d'une prise et de chacune de ses sorties, le tampon des dernières trames |
| `App` | la fenêtre principale : tableaux, journal, zone de notification, enregistrement des réglages |
| `PriseDialog`, `SortieDialog`, `SerieDialog` | la configuration d'une prise, d'une sortie, des sorties en série |
| `MonitorWindow` | la fenêtre Flux : ce qui passe sur une prise, en clair |
| `OptionsDialog` | les options, les actions rares et la section « À propos » (version, mention d'origine, licence) |

Placez `multiprise.py` **dans son propre dossier** : il y range sa
configuration (voir « Ce que le programme crée à côté de lui »).

---

## 3. Lancement

Double-cliquez sur **`Multiprise.bat`** : il lance Multiprise sans fenêtre
de console, et dit ce qui manque si Python ou tkinter est absent. Ou ouvrez
PowerShell dans le dossier du programme et tapez :

```powershell
python multiprise.py
```

La fenêtre s'ouvre et les prises se mettent aussitôt à l'écoute.

**Le pare-feu Windows.** Au premier lancement, Windows peut demander
d'autoriser Python à communiquer — `pythonw.exe`, que lancent
`Multiprise.bat` et le démarrage avec Windows, ou `python.exe` si vous
lancez le script à la main — ou `Multiprise.exe` : acceptez, au moins pour
les **réseaux privés**. Chacun de ces programmes a sa propre autorisation. Sans cette autorisation, les prises n'entendent
rien de ce qui arrive du réseau du bord ; seul ce qui vient du PC lui-même
passe.

**Fermer la fenêtre ne quitte pas**, si `pystray` et `pillow` sont installés :
Multiprise se range près de l'horloge et continue de répartir. Pour
l'arrêter : clic droit sur l'icône → *Quitter*, ou *Options* → *Quitter la
multiprise*. Ce détour est volontaire : fermer la fenêtre par mégarde ne doit
pas couper le flux de tous les programmes servis. Sans ces bibliothèques, ou
si l'option est décochée, la croix quitte.

**Un seul exemplaire à la fois.** Le relancer alors qu'il tourne déjà
affiche un message : la fenêtre ouverte est dans la barre des tâches, ou
rangée près de l'horloge. Deux multiprises se disputeraient les mêmes ports.

**Avec Windows.** *Options* → *Lancer au démarrage de Windows* (voir « Les
options »).

---

## 4. Prise en main

Au premier lancement, la configuration est déjà remplie avec le cas courant,
à ajuster sur place :

| Prise | Écoute | Sorties |
|---|---|---|
| NMEA 1 | port 4001 | `127.0.0.1:4101` (Allure), `127.0.0.1:4201` (autre outil) |
| NMEA 2 | port 4003 | `127.0.0.1:4103` (Allure), `127.0.0.1:4203` (autre outil) |

1. **Libérez le port de la passerelle.** Les programmes qui écoutaient
   jusqu'ici le port de la passerelle (4001) doivent passer sur une prise
   fille (4101, 4201…) : la multiprise doit être **seule** sur le port
   d'entrée. Tant qu'un autre programme le tient, la prise reste en rouge
   avec « port déjà utilisé par un autre programme » ; elle réessaie toute
   seule toutes les 3 secondes et prend le port dès qu'il se libère.
2. **Réglez les prises.** Double-clic sur une prise : port d'écoute, puis ses
   sorties — une par programme à servir.
3. **Vérifiez.** Pastille verte *Flux présent* sur la prise : les trames
   arrivent. Dans le tableau du milieu, chaque sortie passe à *Diffuse* et
   compte ses envois ; une sortie dont le programme n'écoute pas passe à
   *Injoignable*, en rouge.
4. **Branchez les programmes.** Chacun écoute le port de sa sortie. S'il
   filtre les trames par adresse d'expéditeur, il doit accepter `127.0.0.1`
   (ou ne pas filtrer, `0.0.0.0`) : l'expéditeur qu'il voit est désormais la
   multiprise, plus la passerelle. Dans Allure : *Paramètres* → *Voies
   d'écoute*.

---

## 5. Comment ça marche

### Une prise, des sorties

Une prise est un port UDP écouté — sur toutes les cartes réseau du PC
(`0.0.0.0`, le cas normal) ou sur l'adresse d'une seule — et une liste de
sorties, chacune une adresse et un port. Chaque prise a son propre fil
d'écoute ; chaque datagramme reçu est recopié vers chacune de ses sorties
actives.

### Octet pour octet

Le datagramme est recopié tel quel, sans décodage ni recomposition de
lignes : NMEA 0183, AIS encapsulé (`!AIVDM`), binaire, et même un datagramme
vide — ce qui entre sort à l'identique. Le texte n'est décodé que pour
l'affichage.

### Seule sur le port

La multiprise se lie au port d'entrée sans option de partage
(`SO_REUSEADDR`), et en exclusivité : un programme lancé après elle ne peut
pas venir partager le port en douce. Si un autre programme le tient déjà, la
liaison échoue et la prise passe en rouge avec le motif. C'est voulu : mieux
vaut une erreur franche qu'un partage silencieux où un paquet sur deux se
perd. La liaison est retentée toutes les 3 secondes : au démarrage de
Windows, une adresse d'écoute (Wi-Fi, DHCP) arrive souvent après la
multiprise, et un port libéré est repris sans intervention.

### L'expéditeur change

Les programmes servis reçoivent les trames de la multiprise : `127.0.0.1` en
local, l'adresse du PC pour une sortie vers une autre machine.

### Les destinations

Une sortie peut viser un programme du même PC (`127.0.0.1`), un autre PC du
réseau (`192.168.1.50:4001`, ou son nom), ou une adresse de diffusion du
réseau local (`192.168.1.255`), la diffusion étant autorisée. IPv4
seulement. Un nom de PC est résolu à part, sans retarder l'écoute ;
introuvable (PC éteint, réseau pas encore prêt au démarrage de Windows), il
est réessayé toutes les 30 secondes.

### Une sortie en panne ne gêne pas les autres

Un envoi qui échoue est compté dans *Échecs* et ignoré : l'extinction d'un
programme client ne coupe jamais le flux des autres, et un nom de PC
introuvable ne ralentit pas la prise.

### Voir qu'un programme n'écoute plus

Quand aucun programme du PC n'écoute le port d'une sortie, Windows renvoie
un refus, que la multiprise recueille : la sortie passe à *Injoignable*,
puis revient à *Diffuse* dès que le programme écoute de nouveau. Windows
limite le nombre de refus qu'il signale par seconde : la sortie reste rouge
2 secondes après le dernier. Pour une sortie vers un autre PC, l'absence
d'un programme ne se voit pas.

### Les boucles

Une sortie qui renverrait vers un port d'entrée de la multiprise ferait
tourner les datagrammes en rond jusqu'à saturer la machine.

- Vers l'entrée de **sa propre prise** (`127.0.0.1`, l'adresse ou le nom du
  PC, ou une diffusion de son réseau, sur le port écouté) : la configuration
  d'une prise la refuse ; activée depuis le tableau des sorties ou un
  fichier retouché, elle n'est jamais émise et s'affiche *Boucle*.
- **Entre prises** (A renvoie vers B, qui renvoie vers A) : ces prises ne
  sont pas démarrées, et le journal le dit.
- **Une fusion n'est pas une boucle** : deux prises qui alimentent une
  troisième (GPS et AIS vers une prise « Fusion » qui sert les programmes)
  fonctionnent normalement.

### Les rafales

Un tampon de réception de 1 Mo par prise encaisse les rafales (un flux AIS
chargé, par exemple).

### Chaque modification est appliquée aussitôt

Créer, modifier, cocher ou décocher : la configuration est enregistrée,
l'écoute relancée et les compteurs repartent de zéro, avec une coupure du
flux d'au plus un dixième de seconde. Il n'existe pas de réglage affiché mais
non appliqué. **F5** relance l'écoute sans rien changer.

---

## 6. L'interface

Trois zones empilées — les prises, leurs sorties, le journal — séparées par
des poignées déplaçables ; leurs positions et la taille de la fenêtre sont
retenues d'un lancement à l'autre (si l'écran de la dernière session n'est
plus branché, la fenêtre reprend sa taille et Windows la place). Dans la
barre du haut : *+ Nouvelle prise*, *Sorties en série*, *Configurer*, *Flux*,
*Options*.

### Le tableau des prises

À gauche de chaque ligne, une pastille de couleur et une case : un clic sur
la case met la prise en service ou hors service. Puis *État*, *Prise*,
*Écoute* (adresse et port), *Débit* (datagrammes par seconde, moyenne sur
2 s), *Reçu*, *Réémis* (envois, toutes sorties confondues) et *Dernière
trame*.

| État | Pastille | Signification |
|---|---|---|
| Flux présent | vert | une trame reçue il y a moins de 3 s |
| Aucune trame | orange | à l'écoute, rien reçu depuis 3 s |
| Démarrage | orange | l'écoute se met en place (un instant, après chaque modification) |
| Erreur | rouge | liaison impossible ou réception interrompue (nouvel essai toutes les 3 s), ou boucle entre prises ; le message est au journal |
| Hors service | gris | case décochée |
| Non démarrée | gris | prise sans port valide |

Clic droit sur une prise : *Configurer…*, *Sorties en série…*, *Voir le
flux…*, *Activer / désactiver*, *Supprimer*.

### Le tableau des sorties

Les sorties de la prise sélectionnée, chacune avec **ses propres
compteurs** : *État*, *Adresse*, *Port*, *Libellé*, *Envoyés*, *Échecs*. La
case de gauche active ou désactive la sortie sans ouvrir la configuration ;
un double-clic ouvre la configuration de la prise, cette sortie déjà
sélectionnée.

| État | Pastille | Signification |
|---|---|---|
| Diffuse | vert | le dernier datagramme est parti vers cette destination |
| En attente | orange | rien à envoyer pour l'instant : la prise n'a rien reçu |
| Injoignable | rouge | le dernier envoi a échoué, ou un refus est arrivé il y a moins de 2 s : aucun programme de ce PC n'écoute ce port, nom de PC introuvable, réseau absent |
| Boucle | rouge | la sortie renvoie vers l'entrée de sa propre prise : elle n'est jamais émise |
| Inactive | gris | case décochée, ou prise hors service ou en erreur |

L'état suit le **dernier** envoi : une sortie qui se met à échouer passe au
rouge, et repasse au vert dès que son programme écoute de nouveau.

### Le journal

Horodaté, il se lit comme un historique : démarrage, mise à l'écoute,
arrivée et perte du flux (« plus aucune trame reçue », après 10 s de
silence, pour ne pas alerter à chaque pause d'une source lente comme l'AIS
au mouillage), erreurs, modifications de réglage, problèmes de
configuration (prises sur le même port, boucles, sorties en double). Il
garde les 3 000 dernières lignes et ne bouge pas quand on change de
sélection ; remonté pour lire une ancienne ligne, il y reste. *Effacer* le
vide.

La case **trames de la prise sélectionnée** y recopie en plus les trames de
la prise sélectionnée, au plus 20 datagrammes par demi-seconde : au-delà, une
ligne dit combien n'ont pas été affichés. Pour tout voir, la fenêtre Flux est
faite pour ça.

### Trier

Un clic sur un titre de colonne trie : croissant, puis décroissant, puis
retour à l'ordre de la configuration au troisième clic. Les compteurs et
débits se trient comme des nombres ; *État* par gravité, les problèmes en
haut. Tant que le pointeur survole le tableau, les lignes ne bougent pas :
un clic sur une case vise toujours la prise qu'on voit.

### Configurer une prise

*Nom*, *Adresse d'écoute* (`0.0.0.0` = toutes les cartes du PC, le cas
normal, ou l'adresse IPv4 d'une seule), *Port*,
*Prise en service* ; puis ses sorties : *+ Ajouter*, *+ En série…*,
*Modifier* (ou double-clic), *Activer / désactiver*, *Supprimer* (ou
**Suppr**). *Enregistrer* refuse un port invalide, une adresse invalide
(seuls les chiffres, lettres, points et tirets sont admis — une adresse
copiée emporte parfois un caractère invisible), une sortie en double, et
une sortie vers l'entrée de la prise elle-même.

### Sorties en série

Pour créer d'un coup N ports de diffusion (4101, 4102, 4103…) : *Adresse
commune*, *Port de départ* (par défaut, port d'écoute + 100), *Nombre*
(jusqu'à 200), *Pas*, et un *Libellé* numéroté automatiquement (« Sortie 1 »,
« Sortie 2 »…). L'aperçu montre, à chaque frappe, exactement ce qui sera
créé ; les ports écartés y figurent en orange avec la raison : hors bornes,
entrée de la prise (boucle), déjà présent. Accessible depuis la barre du haut
(**Ctrl+S**, sur la prise sélectionnée) ou depuis la configuration d'une
prise.

### La fenêtre Flux

**Ctrl+M**, le bouton *Flux* ou le clic droit → *Voir le flux…* : ce qui
passe sur une prise, en clair et en direct, une fenêtre par prise. Elle suit
sa prise : renommée ou changée de port, son titre suit ; supprimée, la
fenêtre se ferme ; hors service, elle le dit.

- *Pause* / *Reprendre*, *Effacer*, *Enregistrer…* (fichier `.log` ou
  `.txt`) ;
- *Filtre* : n'affiche que les lignes qui contiennent le texte saisi, sans
  distinction de casse (`RMC`, `VDM`…) ;
- *suivre* (défilement automatique), *heure* (horodatage à la milliseconde),
  *source* (adresse de l'expéditeur).

La ligne du bas donne l'état de l'écoute, les datagrammes reçus et réémis,
et les échecs d'envoi s'il y en a. La fenêtre relit le tampon des 2 000
dernières trames de la prise, sans jamais toucher au chemin des trames : une
fenêtre Flux ouverte ne peut ni ralentir ni bloquer la répartition, même sur
un flux rapide.

### Les options

- **La croix range dans la zone de notification** (voir « Lancement »).
- **Démarrer réduit** : la fenêtre se range près de l'horloge dès le
  lancement (avec `pystray` et `pillow` ; sans eux, elle est réduite dans la
  barre des tâches).
- **Lancer au démarrage de Windows** : dépose `Multiprise NMEA.bat` dans le
  dossier Démarrage de Windows
  (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`) — pas de base
  de registre, un fichier que vous pouvez voir et supprimer à la main. Il
  lance la multiprise sans fenêtre de console et accepte les chemins
  accentués. À chaque lancement, il est réécrit pour pointer sur la copie
  lancée (script ou exe, dossier déplacé) ; supprimé à la main, il n'est pas
  recréé et la case se décoche. Désactivé dans le Gestionnaire des tâches
  (onglet *Démarrage*), il reste en place et la case reste cochée :
  décochez-la aussi dans Multiprise.
- **Journal : afficher les trames de la prise sélectionnée** (voir « Le
  journal »).

Deux actions : *Relancer l'écoute (F5)* et *Quitter la multiprise*.

La fenêtre s'intitule *Options et à propos* : sa section **À propos** donne
la version, la mention d'origine « Multiprise, par ETDEL —
https://github.com/theptitprince/Multiprise » (un clic ouvre la page du
dépôt), le copyright, la licence (GPL v3 ou ultérieure, avec les conditions
additionnelles du fichier `NOTICE`), l'absence de garantie, et les adresses
où lire la licence et ces conditions : `Multiprise.exe`, copié seul, n'a ni
`LICENSE` ni `NOTICE` à côté de lui. La même mention est écrite dans le
journal à chaque démarrage (voir « Licence »).

### Les raccourcis

| Touche | Action |
|---|---|
| **Ctrl+N** | nouvelle prise |
| **Ctrl+S** | sorties en série sur la prise sélectionnée |
| **Ctrl+M** | fenêtre Flux de la prise sélectionnée |
| **F5** | relancer l'écoute |
| **Entrée** ou double-clic | configurer la prise |
| **Espace** | mettre la prise en service ou hors service |
| **Suppr** | supprimer la prise, après confirmation |
| **Échap** | fermer une fenêtre secondaire |

---

## 7. Ce que le programme crée à côté de lui

| Fichier | Contenu |
|---|---|
| `multiprise_config.json` | prises, sorties, options, taille de la fenêtre et position des séparateurs. **Copiez-le pour sauvegarder votre configuration.** Renommez-le pour repartir de la configuration de départ. |
| `multiprise_config.json.tmp` | fichier de passage : la configuration est écrite à côté, forcée sur le disque, puis remplace l'ancienne d'un coup — une coupure de courant ne peut pas la laisser à moitié écrite. |
| `multiprise_config.json.illisible` | seulement si la configuration n'a pas pu être relue (voir « En cas de souci ») : le fichier d'origine, mis de côté avant qu'il ne soit remplacé (`.illisible2`, `.illisible3`… si une copie existe déjà). |

En dehors du dossier, seulement si l'option est cochée :
`Multiprise NMEA.bat` dans le dossier Démarrage de Windows.

Le dossier doit être **inscriptible** (pas `Program Files`) : sinon, la
configuration n'est pas enregistrée et le journal le signale
(« réglages non enregistrés »).

---

## 8. Construire un exécutable

Un exécutable autonome évite d'installer Python sur la machine qui
l'utilise. Double-cliquez sur **`construire_exe.bat`**, dans le dossier de
`multiprise.py` ; il :

1. trouve le Python du poste (3.8 ou plus récent) ;
2. vérifie tkinter, et repère `pystray` et `pillow` — embarqués s'ils sont
   installés, sinon l'exe n'a ni zone de notification ni icône (lancez
   d'abord `installer_dependances.bat`) ;
3. installe PyInstaller s'il manque (c'est le seul téléchargement) ;
4. dessine l'icône de la multiprise ;
5. empaquette, puis pose `Multiprise.exe` **à côté de `multiprise.py`**.

Comptez de quelques dizaines de secondes à quelques minutes. Résultat :
`Multiprise.exe`, environ 20 Mo. Il range sa configuration à côté de lui : posé à côté de
`multiprise.py`, il partage la sienne (un seul des deux à la fois). Pour un
autre poste, copiez-le seul dans son propre dossier.

- **Pare-feu** : autorisez `Multiprise.exe` au premier lancement (réseau
  privé). Le pare-feu autorise un exécutable, pas un programme : une
  autorisation donnée à `python.exe` ne vaut pas pour lui.
- **SmartScreen** : l'exe n'est pas signé, Windows peut afficher un
  avertissement → *Informations complémentaires* → *Exécuter quand même*.
- **Antivirus** : un antivirus trop zélé peut bloquer PyInstaller, c'est la
  cause la plus fréquente d'échec.

À la main, les mêmes étapes :

```powershell
python -m pip install pyinstaller "pystray>=0.19" "pillow>=8.2"
```

```powershell
python -c "import multiprise; multiprise.write_ico('multiprise.ico')"
```

```powershell
python -m PyInstaller --onefile --windowed --name Multiprise --icon multiprise.ico --exclude-module numpy --hidden-import pystray._win32 --hidden-import PIL._tkinter_finder multiprise.py
```

Le résultat est dans `dist\`. Les dossiers `build\`, `dist\` et le fichier
`Multiprise.spec` peuvent ensuite être supprimés.

---

## 9. En cas de souci

**« port déjà utilisé par un autre programme »** — un autre programme écoute
encore le port d'entrée, souvent le logiciel de navigation resté réglé sur
le port de la passerelle. Passez-le sur une prise fille : la multiprise
reprend le port toute seule dans les 3 secondes. Pour savoir qui tient le
port (ici 4001), dans PowerShell :

```powershell
Get-Process -Id (Get-NetUDPEndpoint -LocalPort 4001).OwningProcess
```

**« adresse d'écoute inexistante sur cette machine »** — l'adresse d'écoute
de la prise n'est celle d'aucune carte réseau du PC (adresse changée, carte
débranchée, Wi-Fi pas encore connecté). La multiprise réessaie toutes les
3 secondes ; si l'adresse ne revient pas, mettez `0.0.0.0`.

**« port interdit »** — Windows réserve ce port (plages réservées par
Hyper-V, WSL2 ou Docker, visibles avec
`netsh int ipv4 show excludedportrange protocol=udp`), ou un autre
programme le tient en exclusivité. Choisissez un autre port.

**« adresse d'écoute illisible »** — l'adresse contient un caractère
invisible ou non ASCII, souvent emporté en la copiant depuis un document.
Retapez-la.

**La prise reste sur « Aucune trame »** — rien n'arrive. Dans l'ordre :
la passerelle émet-elle, et vers ce port ? Le PC est-il sur le bon réseau ?
Le pare-feu Windows laisse-t-il entrer le flux pour `pythonw.exe` (ou
`python.exe`, ou `Multiprise.exe`, selon ce qui lance la multiprise) ?
L'adresse d'écoute est-elle `0.0.0.0` ?

**La sortie est « Injoignable »** — aucun programme n'écoute son port (le
programme est fermé, ou réglé sur un autre port), son nom de PC est
introuvable, ou le réseau est absent. Démarrez ou réglez le programme : la
sortie repasse à *Diffuse* toute seule. Un nom de PC introuvable est
réessayé toutes les 30 secondes.

**La sortie est « Diffuse » mais le programme ne reçoit rien** — le
programme filtre les trames par adresse d'expéditeur : il doit accepter
`127.0.0.1`. Pour une sortie vers un autre PC, son pare-feu peut aussi
bloquer l'entrée sans rien renvoyer. La fenêtre Flux de la prise montre ce
qui entre, et donc ce qui sort.

**Le journal signale une boucle, ou une sortie est « Boucle »** — une sortie
renvoie vers le port d'entrée d'une prise de ce PC : corrigez son port. Une
sortie vers sa propre prise n'est jamais émise ; des prises qui se renvoient
le flux ne sont pas démarrées.

**« Multiprise NMEA tourne déjà »** — l'autre exemplaire est dans la barre
des tâches ou rangé près de l'horloge (`Multiprise.exe` et `multiprise.py`
comptent pour un seul : un seul des deux à la fois).

**« No module named tkinter »** — Python a été installé sans tcl/tk.
Relancez l'installateur, choisissez *Modify*, et cochez `tcl/tk and IDLE`.

**« configuration impossible à lire »** — le fichier est verrouillé par un
autre programme ou protégé (droits) : la multiprise démarre sans prise et ne
l'écrase pas. Fermez ce qui le tient, puis relancez.

**« configuration illisible »** — le fichier de configuration a été abîmé ou
retouché à la main avec une erreur. La multiprise ne le remplace pas en
silence : elle le met de côté sous `multiprise_config.json.illisible`,
démarre sans prise et l'écrit au journal. Corrigez le fichier mis de côté et
renommez-le en `multiprise_config.json` (multiprise fermée), ou recréez vos
prises. Une valeur de type inattendu (un nombre à la place d'une liste, par
exemple) est simplement remplacée par sa valeur par défaut.

---

## 10. Licence

Multiprise est un **logiciel libre**, distribué sous la licence
**GNU General Public License, version 3 ou ultérieure** (GPL-3.0-or-later).

Copyright © 2026 ETDEL.

Concrètement, vous pouvez utiliser le programme librement, y compris à bord
et dans un cadre professionnel, l'étudier, le modifier et le redistribuer —
à condition que toute version redistribuée, modifiée ou non, reste sous la
même licence, avec son code source et la mention de copyright. Le programme
est fourni **sans aucune garantie** : il répartit les trames qu'il reçoit,
il ne remplace ni votre vigilance ni vos instruments de navigation.

### Conditions additionnelles (article 7)

La GPL v3 permet à l'auteur d'ajouter quelques conditions (article 7). Celles de Multiprise sont dans
le fichier [`NOTICE`](NOTICE), en français et en anglais :

- **Attribution** : toute copie ou version modifiée doit garder, visible pour l'utilisateur
  (fenêtre « À propos » ou équivalent) et dans sa documentation, la mention :

  > Multiprise, par ETDEL — https://github.com/theptitprince/Multiprise

  Une version modifiée peut la faire précéder de « D'après » et ajouter ses propres crédits,
  sans la retirer ni la masquer.
- **Origine** : une version modifiée doit dire clairement qu'elle est modifiée, et ne doit se
  présenter ni comme l'original, ni comme approuvée par ETDEL.

Dans Multiprise, cette mention s'affiche dans la fenêtre *Options* (section « A propos ») et dans le journal au démarrage.

Le texte intégral de la licence est dans le fichier `LICENSE` du dépôt et
sur <https://www.gnu.org/licenses/gpl-3.0.html>. Chaque fichier source
(`multiprise.py` et les trois `.bat`) porte un en-tête qui renvoie à
`LICENSE` et `NOTICE`.

---

*Multiprise — ETDEL 2026 — GPL-3.0-or-later*
