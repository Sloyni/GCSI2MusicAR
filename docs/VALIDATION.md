# Validation de MusicAR 0.2 — 14 octobre 2026

PC cible : **i7-13620H**, 10 cœurs / 16 threads, **NVIDIA RTX 4060 Laptop**, Intel UHD, **32 Go de RAM**, Windows, Python 3.12.14.

## Comportement vérifié

- **29 tests Python réussis** : contact dès la première détection, entrée horizontale, maintien sans répétition, sortie immédiate, glissement entre notes, doigts indépendants, pertes de suivi, pads, guitare à deux mains, translation sans faux grattage, contact des cordes, grattage rapide, frettes, validation des réglages et paquets, HTTP, WebSocket et port occupé.
- **4 contrôles audio JavaScript réussis** : gain ×2, coupure du piano à la sortie malgré le sustain, sustain clavier conservé et résonance naturelle des cordes.
- **3 contrôles d’interface JavaScript réussis**, sur un DOM simulé : création et dessin des 25 touches, des six cordes et des quatre pads. Ces contrôles vérifient l’exécution des branches de rendu ; ils ne remplacent pas une inspection visuelle.
- Le lancement répété avec un serveur actif retourne proprement « Instance MusicAR déjà active », sans nouvelle tentative de bind sur 8765. Un test réserve un port étranger et vérifie la sélection d’un port libre.
- Les **17 fichiers piano et huit fichiers guitare** ont été décodés dans WebView2. Un rendu hors ligne des modules audio produit un signal non nul : piano RMS ~0,036 / crête ~0,267 ; guitare RMS ~0,139 / crête ~0,874 pour les accords de test.
- `pip check`, compilation Python et vérification syntaxique des modules JavaScript passent.

## Mesures et choix du mode Turbo

Image de référence officielle `right_hands.jpg`, réduite à 640 × 340, 30 images ; mesures après dix images d’échauffement pour les modes web.

| Mode | Inférence moyenne | Mains détectées | Conclusion |
|---|---:|---:|---|
| MediaPipe Python natif | ~27,4 ms | 2 | Suivi fiable sur cet essai |
| MediaPipe WebGL GPU | ~37 ms | 1 | Écart de détection observé ; non retenu par défaut |
| MediaPipe WebAssembly CPU | ~206 ms | 2 | Plus lent dans cette exécution WebView |
| Hybride CPU natif + vidéo GPU | **~27,7 ms** | **2 sur 30/30 images** | **Mode Turbo par défaut** |

Le mode hybride mesure **~40,4 ms** pour préparation, encodage, transfert local et analyse. Le contexte graphique a identifié **ANGLE / NVIDIA GeForce RTX 4060 Laptop / Direct3D11**. Le backend utilise XNNPACK pour l’inférence CPU. Aucun changement de pilote, de registre, d’overclocking ou de réglage système n’a été nécessaire.

## Caméra et limites

La caméra HP True Vision FHD a été ouverte et 30 images à 640 × 480 traitées lors du diagnostic initial. L’ancienne interface native a affiché la vidéo avec le clavier superposé et exporté un fichier WebM. La nouvelle logique de contact et la guitare ont été vérifiées par les tests et le rendu simulé ; l’essai musical complet avec les mains du joueur reste à faire.

Les mesures sur image fixe ne garantissent pas la précision en occultation, l’efficacité des mouvements de frettes ou la cadence d’une session caméra réelle. Elles ne mesurent pas la latence totale du mouvement jusqu’au haut-parleur. L’application demande jusqu’à 60 fps ; le débit réel dépend de la caméra et du mode vidéo accepté.

Référence : https://storage.googleapis.com/mediapipe-assets/right_hands.jpg

Tests officiels : https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/python/test/vision/hand_landmarker_test.py

Rapports bruts locaux : `artifacts/hybrid-web-validation.json`, `artifacts/gpu-web-validation.json`, `artifacts/cpu-web-validation.json`, `artifacts/audio-validation.json`.
