# Journal des versions

Toutes les livraisons de Multiprise, de la plus récente à la plus ancienne.

## Comment se lit un numéro de version

`X.Y` : `3.2`, `3.3`, `3.4`…

- Le **premier chiffre** change quand l'application change de visage — une
  refonte de l'interface, une configuration qui ne se relit plus telle
  quelle.
- Le **second** monte à chaque livraison — une correction, un réglage ou une
  fonction de plus.

Le numéro vit à un seul endroit dans le code, `APP_VERSION` en tête de
`multiprise.py`. Il s'affiche dans la barre de titre, la barre d'état et les
options, et il est inscrit dans `multiprise_config.json` (`app_version`) à
chaque enregistrement. Il est destiné à l'humain : il ne pilote **aucun**
comportement du programme.

---

## 3.5

Multiprise dit d'où elle vient. Elle reste un logiciel libre (GPL v3 ou
ultérieure) ; des conditions additionnelles (article 7) demandent à toute
copie ou version modifiée de garder visible la mention d'origine, et à une
version modifiée de dire qu'elle l'est. La répartition des flux, la fenêtre
principale et la configuration ne changent pas.

### Ajouté

- **`NOTICE`** : les conditions additionnelles de la licence (article 7 b
  et c), en français et en anglais — garder, visible, la mention
  « Multiprise, par ETDEL — https://github.com/theptitprince/Multiprise »
  dans toute copie ou version modifiée ; une version modifiée doit le dire.
- **Section *À propos* dans les options**, fenêtre renommée *Options et à
  propos* : version, mention d'origine (un clic ouvre la page du dépôt),
  copyright, licence, absence de garantie, et les adresses où lire la
  licence et les conditions — `Multiprise.exe`, copié seul, n'a ni
  `LICENSE` ni `NOTICE` à côté de lui.
- **Mention d'origine au journal**, à chaque démarrage, juste après la
  ligne de version.
- **En-tête des sources** : `multiprise.py` et les trois `.bat` portent la
  mention et renvoient au fichier `NOTICE`.

### Modifié

- **Section Licence des README** (français et anglais) : les conditions
  additionnelles, la mention à conserver et l'endroit où le programme
  l'affiche.
- La ligne « version · ETDEL 2026 » du bas des options laisse la place à la
  section *À propos*.

## 3.4

Première version publiée. Elle ajoute les scripts d'installation et de
construction de l'exécutable, et corrige ce qu'une relecture complète du
code, vérifiée par des essais réels, a trouvé.

### Ajouté

- **`installer_dependances.bat`** : vérifie Python 3.8+ et tkinter (et dit
  quoi faire s'ils manquent), remet `pip` en place au besoin, installe
  `pystray` et `pillow`.
- **`construire_exe.bat`** : construit `Multiprise.exe`, autonome (Python et
  tkinter embarqués, pystray et pillow s'ils sont installés, sans numpy), avec l'icône
  de la multiprise, et le pose à côté de `multiprise.py`.
- **`Multiprise.bat`** : lancement par double-clic, sans fenêtre de console ;
  dit ce qui manque si Python ou tkinter est absent.
- **Mode exe** : la configuration est rangée à côté de `Multiprise.exe`, et
  non dans le dossier temporaire où l'exe se déballe, effacé à chaque
  fermeture. Le lancement au démarrage de Windows lance l'exe.
- **Programme absent détecté** : chaque sortie vers ce PC a sa propre
  socket, et le refus que renvoie Windows quand aucun programme n'écoute
  fait passer la sortie à *Injoignable* (2 s après le dernier refus) ; elle
  revient à *Diffuse* dès que le programme écoute de nouveau.
- **États *Boucle*** (sortie vers l'entrée de sa propre prise, jamais
  émise) et ***Démarrage*** (l'écoute se met en place, remplace *Arrêtée*).
- La fenêtre Flux affiche les échecs d'envoi.

### Modifié

- **Liaison retentée toutes les 3 s** : un port libéré par l'autre
  programme, une adresse d'écoute qui arrive après la multiprise au
  démarrage de Windows, ou une réception interrompue, est repris sans
  intervention.
- **Port d'entrée pris en exclusivité** : un programme lancé après la
  multiprise ne peut plus venir partager le port en douce.
- **Noms de PC résolus à part**, sans retarder l'écoute (et non plus à
  chaque datagramme) ; un nom introuvable est réessayé toutes les 30 s.
- **Boucles** : reconnues aussi vers l'adresse ou le nom du PC et vers une
  diffusion du même réseau ; des prises qui se renvoient le flux ne sont pas
  démarrées ; une fusion (deux prises vers une troisième) n'est plus
  signalée à tort comme une boucle.
- **Lancement au démarrage de Windows** : sans fenêtre de console
  (`pythonw`), chemins accentués et `%` acceptés, fichier réécrit à chaque
  lancement pour suivre la copie lancée ; la case reflète le fichier
  réellement présent.
- **Instance unique** par un verrou Windows (mutex) au lieu d'un port : une
  plage de ports réservée par Hyper-V, WSL2 ou Docker ne peut plus faire
  croire que Multiprise tourne déjà ; une copie lancée en administrateur est
  reconnue aussi.
- **Adresse d'écoute** : une adresse IPv4 de ce PC, ou `0.0.0.0` (un nom
  désactivait la détection des boucles).
- **Coupure du flux à chaque modification** ramenée à un dixième de seconde
  au plus.
- **Datagrammes vides** relayés aussi, octet pour octet.
- Le journal ne signale plus une perte de flux qu'après 10 s de silence (les
  sources lentes, comme l'AIS au mouillage, ne le remplissent plus) et reste
  où on l'a remonté.
- Tant que le pointeur survole un tableau trié, ses lignes ne bougent plus.
- Les dialogues s'ouvrent sur l'écran de la fenêtre principale, et une
  fenêtre sur un écran débranché depuis reprend une place visible.
- Sans `pystray`, *Démarrer réduit* réduit la fenêtre dans la barre des
  tâches.

### Corrigé

- **Une sortie donnée par un nom de PC éteint ou mal tapé paralysait toute
  sa prise** (moins d'une trame par seconde pour toutes les sorties), et F5
  faisait ensuite croire à un « port déjà utilisé ».
- **Une adresse copiée avec un caractère invisible tuait l'écoute** de la
  prise sans rien dire. Les adresses sont maintenant vérifiées à la saisie.
- **Configuration** : un fichier illisible (BOM, faute de frappe) était
  remplacé en silence par la configuration d'exemple, puis écrasé ; il est
  maintenant mis de côté (`.illisible`) et signalé. Une valeur de type
  inattendu (liste remplacée par un nombre, taille de fenêtre illisible,
  `"false"` écrit à la main) empêchait le démarrage ou était mal lue.
- **Journal** : chaque modification écrivait de fausses pertes de flux pour
  toutes les prises ; après un changement de prise sélectionnée, les trames
  recopiées pouvaient rester invisibles longtemps ; deux prises de même nom
  et même port le remplissaient sans fin.
- **Fenêtres Flux** : après la suppression d'une prise, elles montraient le
  flux de la prise voisine sous leur ancien titre ; elles suivent
  maintenant leur prise, et disent quand elle est hors service.
- **Sorties** : l'état *Injoignable* n'apparaissait qu'en changeant de prise
  sélectionnée ; une sortie servie une fois restait verte pour toujours.
- **Réception interrompue** : la prise s'arrêtait sans rien dire ; elle
  passe en *Erreur*, avec le message du système au journal.
- **Dialogues** : la configuration d'une prise cessait d'être modale après
  l'ajout d'une sortie (modifier la liste pendant ce temps faisait écraser
  une autre prise) ; une sortie en double était acceptée (chaque trame
  partait deux fois) ; un double-clic sur la case d'une sortie ouvrait en
  plus la configuration.
- **Fenêtre** : une fenêtre maximisée était enregistrée comme une fenêtre
  normale de la taille de l'écran ; la position des séparateurs se perdait
  en quittant depuis la zone de notification ou sur un démarrage lent.

## 3.3 et précédentes

Versions de travail. La série 3 a donné à Multiprise son visage actuel :
tableau des prises, tableau des sorties avec leurs propres compteurs,
journal horodaté, sorties en série, zones séparées par des poignées
déplaçables.
