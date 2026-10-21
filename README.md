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

## Piano : contact immédiat

Placez le **centre d’un cercle de doigt sur une touche** : la note joue immédiatement, même si la main apparaît directement dans le clavier. Elle reste active tant que le doigt est sur cette touche. Sortez le doigt ou la main du piano pour l’arrêter. Vous pouvez passer d’une touche à l’autre sans lever puis frapper.

Le piano est plus haut dans l’image et contient 25 notes. **Calibrer** permet de le déplacer et d’ajuster sa largeur et sa hauteur. Les touches noires ont leur propre zone, prioritaire seulement dans leur rectangle visible.

L’index et le majeur sont actifs par défaut. Vous pouvez activer les autres doigts. La dynamique règle l’expressivité du volume, sans empêcher le contact immédiat.

## Tambours : entrée sur un pad

Le son démarre dès que le cercle d’un doigt entre sur un pad. Aucun mouvement de frappe n’est requis. Un doigt maintenu ne répète pas le son ; sortez puis revenez pour rejouer. Kick, snare, hi-hat et tom utilisent une synthèse locale.

## Guitare : suit les deux mains

Choisissez **Guitare acoustique**, puis montrez deux mains écartées. Le manche s’attache à la paume côté gauche de l’image ; la caisse s’attache à l’autre. L’instrument se déplace et tourne avec les deux paumes.

- Les six cordes sont accordées **Mi2, La2, Ré3, Sol3, Si3, Mi4**.
- Les doigts de la main côté caisse jouent au contact des lignes ou en les traversant. Un grattage rapide peut jouer plusieurs cordes entre deux images.
- Les doigts de la main côté manche peuvent toucher une corde dans une case pour en changer la note, jusqu’à cinq frettes.
- Les cordes résonnent naturellement après le pincement. La guitare disparaît si une main manque ou si les paumes sont trop proches.

Gardez les doigts visibles et évitez que les mains se cachent l’une l’autre. Les boutons sous la caméra permettent aussi de tester les six cordes à la souris et avec A S D F G H.

## Son et enregistrement

Le **gain de sortie est doublé** par rapport à la version initiale. Le volume reste réglable et la compression limite la saturation en polyphonie.

Le piano utilise 17 enregistrements Salamander et la guitare huit enregistrements acoustiques, avec transposition, filtre selon le geste et réverbération. Espace et le bouton Sustain prolongent les notes du clavier physique ; sortir un doigt du piano coupe toujours sa note, même avec sustain activé. Échap coupe tous les sons.

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

Les tests couvrent contact immédiat, maintien, sortie, glissement, polyphonie, pads, guitare mobile, grattage rapide, frettes, validation des données, WebSocket et réutilisation du port. Le diagnostic graphique utilise une image de référence officielle, sans ouvrir la webcam. Le diagnostic audio décode les 25 fichiers et vérifie un rendu hors ligne.

Code : `musicar/` pour les gestes et le service ; `web/` pour l’interface, le son et le worker ; `scripts/` pour l’installation et les diagnostics ; `tests/` pour les régressions.

Recherche : [`docs/RECHERCHE.md`](docs/RECHERCHE.md). Crédits et licences des médias : [`assets/ATTRIBUTION.md`](assets/ATTRIBUTION.md).
