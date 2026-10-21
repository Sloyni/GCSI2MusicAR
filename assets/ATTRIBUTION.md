# Échantillons et modèle

Piano : **Salamander Grand Piano**, Alexander Holm, licence **Creative Commons Attribution 3.0 Unported**. Échantillons MP3 distribués par le projet Tone.js. Le lecteur transpose les enregistrements voisins ; cette version utilise une couche de vélocité, avec volume et filtre sensibles au geste.

- Source originale : https://archive.org/details/SalamanderGrandPianoV3
- Distribution : https://tonejs.github.io/audio/salamander/
- Licence : https://creativecommons.org/licenses/by/3.0/
- Référence et auteur : https://github.com/studiorack/salamander-grand-piano

Modèle **MediaPipe Hand Landmarker**, Google, téléchargé depuis la distribution officielle. Code MediaPipe sous Apache 2.0 : https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE

Le script `scripts/download_assets.py` garde les URL et empreintes SHA-256 dans `assets/manifest.json`. Les sons de batterie sont synthétisés localement, sans échantillon tiers.

Guitare acoustique : enregistrements de la collection **tonejs-instruments**, **N. P. Brosowsky**, échantillons sous **CC BY 3.0**. MusicAR utilise huit fichiers, les transpose pour les frettes et ajoute gain, filtre et réverbération.

- Collection et licence : https://github.com/nbrosowsky/tonejs-instruments
- Sources originales recensées : https://github.com/nbrosowsky/tonejs-instruments/blob/master/sample-source-info.txt

Runtime web MediaPipe Tasks Vision 0.10.32 : distribution npm officielle `@mediapipe/tasks-vision` via jsDelivr, code Apache 2.0. Le jeu fonctionne sans connexion au CDN une fois les fichiers installés.
