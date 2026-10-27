# MusicAR

Application **Python avec interface web intégrée**, en français : caméra PC, piano, tambours et guitare en réalité augmentée. Le traitement des images et le son restent sur le PC.

## Démarrer

Double-cliquez sur **`Demarrer.cmd`** puis sur **Activer la caméra**. Le lanceur réutilise un serveur MusicAR déjà actif ; cliquer plusieurs fois ne provoque plus l’erreur du port 8765. Si un autre logiciel utilise ce port, il en réserve automatiquement un libre.

**`Demarrer-Navigateur.cmd`** ouvre la même interface dans le navigateur. La fenêtre intégrée utilise Edge WebView2.

```powershell
# Installation sur une autre machine, avec Python 3.12
powershell -NoProfile -ExecutionPolicy Bypass -File .\Installer.ps1

# Fenêtre intégrée / navigateur / service seul
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe app.py --browser
.\.venv\Scripts\python.exe app.py --headless
```

L’installation est isolée dans `.venv`. Les versions vérifiées sont dans `requirements-lock.txt`. Le modèle, les banques audio et le runtime web sont téléchargés une fois ; le jeu fonctionne ensuite hors ligne. Les fichiers médias et WASM représentent environ 33 Mo, en plus des bibliothèques Python.

## Réglages du son et gestes d’expression

Le panneau **Votre son, vos gestes** propose quatre styles : **Acoustique, Jazz, Électrique et Ambient**. Ils règlent réellement le filtre, la saturation, l’écho et l’espace sur les trois instruments. Le timbre va de chaud à brillant. Le piano et la guitare disposent aussi d’une transposition de −12 à +12 demi-tons.

Pour le **pitch pouce–index**, cochez l’option, choisissez la main de contrôle et l’amplitude, puis gardez cette main à une hauteur confortable. Les gestes fonctionnent partout dans l’image par défaut ; « Zone des gestes » permet de limiter volontairement la commande à la bande haute. Gardez un écart confortable et cliquez sur **Centrer le pitch** : rapprocher les doigts abaisse la hauteur, les écarter la monte. La mesure est normalisée par la largeur de la paume ; le son revient à sa hauteur de base quand la main disparaît, ou quitte la bande si cette restriction est activée. Le pitch agit aussi sur les notes déjà en cours, avec un lissage audio.

Pour **changer de style**, ouvrez la main de contrôle et balayez horizontalement à hauteur normale : droite = suivant, gauche = précédent. Une pause d’environ une seconde évite les changements multiples. Ce geste peut être désactivé. Les réglages sont mémorisés dans le navigateur.

## Piano : contact ou frappe

Placez le **centre d’un cercle de doigt sur une touche** : la note joue immédiatement, même si la main apparaît directement dans le clavier. Elle reste active tant que le doigt est sur cette touche. Sortez le doigt ou la main du piano pour l’arrêter. Vous pouvez passer d’une touche à l’autre sans lever puis frapper.

Le piano est plus haut dans l’image et contient 25 notes. **Calibrer** permet de le déplacer et d’ajuster sa largeur et sa hauteur. Les touches noires ont leur propre zone, prioritaire seulement dans leur rectangle visible.

L’index et le majeur sont actifs par défaut. Vous pouvez activer les autres doigts. La dynamique règle l’expressivité du volume, sans empêcher le contact immédiat.

Le mode **Frappe** permet de répéter une note en relevant puis redescendant le doigt, même sans sortir de la touche. La vitesse règle la vélocité. Le mode contact reste sélectionné par défaut. Les gammes majeure, mineure et pentatonique, avec tonalité configurable, désactivent les touches hors gamme dans la caméra comme au clavier et à la souris.

## Batterie : six pads et frappes répétables

Kick, snare, hi-hat fermé, tom, crash et hi-hat ouvert utilisent une synthèse locale. Le mode **Frappe**, sélectionné par défaut, joue en descendant le doigt sur le pad. Relevez-le légèrement puis redescendez pour répéter ; la vitesse règle le volume. Les frappes rapides qui traversent un pad entre deux images sont également détectées. Un court délai supprime les doublons de doigts d’une même main. Le hi-hat fermé étouffe le hi-hat ouvert. Le mode **Contact** reste disponible pour jouer dès l’entrée dans un pad. Souris et touches A S D F G H fonctionnent dans les deux modes.

## Guitare : accords, mélodie et cordes libres

Le mode **Accords · cordes au toucher**, sélectionné par défaut, sépare les deux tâches. La main à gauche de l’image choisit l’accord avec les doigts levés (**1 Do, 2 Sol, 3 Lam, 4 Fa, 5 Rém**). La guitare s’attache au **poignet droit**, avec un décalage constant pour placer les cordes sous les doigts. Déplacer toute la main déplace la guitare sans déclencher de grattage. Bougez l’index, ou un autre doigt actif, sur une corde côté caisse : **seule cette corde sonne**. Traversez plusieurs cordes pour gratter ; l’ordre et l’espacement des attaques suivent le passage du doigt. Sortez suffisamment de la corde puis revenez pour la rejouer. Une marge de sortie et un anti-doublon empêchent les répétitions dues aux tremblements ou à deux doigts sur la même corde.

L’accord se stabilise pendant 130 ms ; poing fermé = pause. Au premier repérage ou après une perte de suivi, le contact déjà présent est mémorisé sans jouer : bougez le doigt pour commencer. Une nouvelle attaque étouffe l’ancienne note de la même corde au moment prévu. Les cercles de doigts apparaissent uniquement sur la main droite ; la main gauche garde son squelette. Les boutons et touches A S D F G H permettent toujours de jouer les accords complets Do, Sol, Lam, Fa, Rém et Mim.

En mode **Mélodie**, la main à droite pince le pouce avec l’index, le majeur, l’annulaire ou l’auriculaire pour jouer quatre notes. Écartez les doigts avant de repincer : aucun mitraillage pendant le maintien. La main à gauche choisit quatre groupes successifs de la gamme avec 1 à 4 doigts, pour atteindre 16 notes différentes ; gamme et tonalité se règlent dans le panneau. Les quatre notes sont affichées dans l’image et jouables à la souris ou avec A S D F.

En mode **Cordes et frettes libres**, le manche et la caisse suivent les deux paumes, comme dans la version précédente :

- Les six cordes sont accordées **Mi2, La2, Ré3, Sol3, Si3, Mi4**.
- Les doigts de la main côté caisse jouent au contact des lignes ou en les traversant. Un grattage rapide peut jouer plusieurs cordes entre deux images.
- Les doigts de la main côté manche peuvent toucher une corde dans une case pour en changer la note, jusqu’à cinq frettes.
- Les cordes résonnent naturellement après le pincement. La guitare disparaît si une main manque ou si les paumes sont trop proches.

Gardez les doigts visibles et évitez que les mains se cachent l’une l’autre. Les boutons sous la caméra permettent aussi de tester les six cordes à la souris et avec A S D F G H.

## Son et enregistrement

Le **gain de sortie est doublé** par rapport à la version initiale. Le volume reste réglable et la compression limite la saturation en polyphonie.

Le piano utilise 17 enregistrements Salamander et la guitare huit enregistrements acoustiques. Les styles sont des traitements de ces banques locales, notamment une saturation pour Électrique ; ils ne constituent pas des banques supplémentaires d’instruments enregistrés. Espace et le bouton Sustain prolongent les notes du clavier physique ; sortir un doigt du piano coupe toujours sa note, même avec sustain activé. Échap coupe les voix actives.

**Enregistrer** capture uniquement le son des instruments. **Exporter .webm** conserve la session. Aucun microphone ni vidéo n’est enregistré.

## Performances : Turbo CPU + GPU

Le mode Turbo est activé par défaut. La caméra est affichée directement par le moteur web sur le GPU. Un worker prépare une image réduite pour le modèle natif MediaPipe ; le CPU traite le suivi et Python renvoie aussitôt les contacts et la géométrie de la guitare. Une seule analyse est en vol : les images en retard ne forment pas une file d’attente.

Sur ce PC, la RTX 4060 a été identifiée dans le contexte graphique. Le mode hybride était plus fiable et plus rapide que les autres modes web testés, avec deux mains conservées sur les 30 images de référence. Les mesures et leurs limites sont dans [`docs/VALIDATION.md`](docs/VALIDATION.md).

Si le moteur web ne peut pas ouvrir la caméra, l’application revient au mode OpenCV / Python. Vous pouvez aussi désactiver Turbo. La fluidité finale reste limitée par le débit réel de la webcam, les images floues, le suivi et la sortie audio ; demander 60 fps ne garantit pas que la caméra les fournisse.

## Dépannage

- **Caméra inaccessible** : fermez les autres applications qui l’utilisent, vérifiez les autorisations Windows pour les applications de bureau et choisissez la bonne source. Une permission web éventuelle doit être autorisée dans la fenêtre.
- **Une note ne joue pas** : vérifiez que le doigt est actif et que le centre du cercle est dans la touche ou le pad. Aucune ligne de frappe n’est nécessaire.
- **Guitare absente** : montrez deux mains visibles, suffisamment séparées, puis rapprochez les doigts de la main côté caisse des cordes.
- **Pas de son** : cliquez sur un instrument ou l’aperçu, augmentez le volume et vérifiez la sortie Windows. Relancez `Installer.ps1` si un échantillon manque.
- **Ancienne interface** : fermez puis relancez `Demarrer.cmd`, ou rechargez la page du navigateur.
- **Fenêtre native indisponible** : utilisez `Demarrer-Navigateur.cmd`.
- Logs : `logs/musicar.log`. Réglages de la fenêtre : `.runtime/webview/`.

## Vérification et développement

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node tests/test_audio.mjs
# Nécessite un service actif
node tests/test_ui_runtime.mjs
.\.venv\Scripts\python.exe scripts/gpu_probe.py --delegate HYBRID
.\.venv\Scripts\python.exe scripts/gpu_probe.py --audio
```

Les tests couvrent aussi accords stabilisés, grattage dans les deux sens, pincements, réarmement des frappes, pitch normalisé, changement de style et transport des paramètres par WebSocket. Le diagnostic graphique utilise une image de référence officielle, sans ouvrir la webcam. Le diagnostic audio décode les 25 fichiers et vérifie les 12 combinaisons instrument/style avec le graphe d’effets complet. Il peut aussi être ouvert directement à `/static/audio-diagnostic.html` si le lancement WebView du script n’aboutit pas.

Code : `musicar/` pour les gestes et le service ; `web/` pour l’interface, le son et le worker ; `scripts/` pour l’installation et les diagnostics ; `tests/` pour les régressions.

Recherche : [`docs/RECHERCHE.md`](docs/RECHERCHE.md). Crédits et licences des médias : [`assets/ATTRIBUTION.md`](assets/ATTRIBUTION.md).
