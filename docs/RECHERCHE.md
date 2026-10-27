# Choix techniques — recherche actualisée le 27 octobre 2026

## Correction des gestes d’expression à hauteur normale

Le pitch par écart pouce–index et le balayage de la main de contrôle sont désormais utilisables partout dans l’image par défaut. La bande haute est une option explicite ; la restriction initiale expliquait l’absence de réaction lors des gestes à hauteur du clavier ou de la guitare. Le balayage est mesuré au centre de la paume et réservé à la main de contrôle.

## Correction après essai utilisateur : toucher des cordes et ancrage au poignet

Le retour du joueur remplace le grattage automatique au poignet décrit ci-dessous : dans le mode accords, la guitare suit désormais le poignet droit et chaque corde n’est jouée que par le contact ou le passage d’un doigt actif. Le détecteur conserve les coordonnées relatives au poignet, une hystérésis de contact et un anti-doublon par corde. Les traversées sont espacées dans Web Audio selon leur position le long du trajet. Les paragraphes sur la surface fixe et le déclenchement global décrivent la première version et ne s’appliquent plus au mode accords actuel.

## Expressivité et jouabilité — 27 octobre

Sources primaires consultées pour la nouvelle interaction :

- [Dastan, Gesture Guitar Studio](https://kelidari.com/dastan-gesture-guitar/) sépare accords et mélodie et propose gammes, transposition et jeu de guitare par accords. MusicAR reprend le principe de séparation des tâches, avec grattage volontaire du poignet ; aucun accompagnement automatique n’est ajouté.
- [Gesture Synth : fonctionnement des gestes](https://synthgesture.com/blog/how-gesture-synth-turns-hand-landmarks-into-music) documente la stabilisation des poses, les frappes avec remontée pour réarmer et la détection du trajet entre deux images. MusicAR utilise une confirmation d’accord de 130 ms, une tolérance de perte de suivi de 180 ms sur la guitare assistée, et un détecteur de frappes avec course minimale et vitesse configurable.
- [Theremotion](https://plule.github.io/theremotion/) utilise des dimensions gestuelles séparées pour hauteur, volume et filtre, et permet un guidage par gamme. MusicAR propose des gammes pour le piano et la mélodie guitare, ainsi qu’un pitch continu distinct des notes.
- [Leap Motion : gestes de déclenchement](https://www.leapmotiontechnology.com/blog-sub/click-bang-go-gestures-for-triggering-events) explique l’intérêt du pincement pour son retour tactile et les conflits possibles entre commandes gestuelles. D’où quatre pincements de mélodie et une bande supérieure réservée aux commandes de pitch et de style.
- [Manuel Aerodrums](https://aerodrums.com/manual/) décrit l’ajustement des surfaces et de la réponse des frappes. MusicAR conserve sa calibration des pads et ajoute une dynamique liée à la vitesse, sans prétendre reproduire la précision de son matériel dédié.

Implémentation locale : pitch en demi-tons via `AudioBufferSourceNode.detune`, lissé avec `setTargetAtTime`, distance pouce–index rapportée à la largeur de paume en tenant compte du format vidéo. Un balayage n’est accepté que dans la bande haute, paume ouverte, avec déplacement horizontal suffisant et délai de répétition. Les styles Acoustique, Jazz, Électrique et Ambient modifient un filtre, un waveshaper, un écho et la réverbération sur les banques déjà installées. Ce sont des traitements sonores, pas une génération automatique de musique ni de nouveaux échantillons de guitare électrique.

La nouvelle guitare assistée abandonne le contact précis avec six fines lignes pour les accords et la mélodie. Le mode libre reste disponible. Les seuils sont couverts par des traces synthétiques et le son par des rendus hors ligne ; le confort avec les mains du joueur reste à évaluer en conditions réelles.

## Mise à jour : contact immédiat, guitare et performances

La version 0.2 joue au **contact visuel**, sans mouvement de frappe requis. Le piano démarre dès que le centre du cercle d’un doigt entre sur une touche ; il s’arrête dès la sortie. Les pads déclenchent une percussion à chaque entrée. Six cordes de guitare sont attachées aux deux paumes et évaluées dans le repère mobile de l’instrument, pour éviter que le simple déplacement de la guitare provoque un grattage.

Sur le PC cible (i7-13620H, RTX 4060 Laptop, 32 Go), les comparaisons mesurées ont conduit au **mode hybride CPU + GPU** : vidéo directe dans WebView2 et rendu sur la RTX, suivi MediaPipe natif sur le CPU avec XNNPACK, traitement dans un thread distinct. L’interface transfère une image réduite uniquement pour l’analyse ; elle ne reçoit plus une copie JPEG pour afficher la caméra. Les événements sont renvoyés immédiatement après l’analyse et aucune file de frames ne s’accumule.

Sur une image de référence identique : Python natif ~27,4 ms d’inférence avec deux mains ; GPU WebGL ~37 ms mais une seule main conservée sur ce test ; CPU WebAssembly ~206 ms avec deux mains. Le mode hybride a conservé deux mains sur 30/30 images, avec ~27,7 ms d’inférence et ~40,4 ms pour encodage + transport + analyse. Ces chiffres ne mesurent pas la latence complète caméra → haut-parleur. Le GPU a été identifié effectivement comme **ANGLE / NVIDIA RTX 4060 / Direct3D11**.

Le [guide MediaPipe web](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/web_js) indique que l’inférence peut bloquer le thread de l’interface et conseille un worker. Le SDK permet un canvas hors écran pour les textures GPU. La [demande officielle de support GPU Python sous Windows](https://github.com/google-ai-edge/mediapipe/issues/4575) explique pourquoi changer simplement une option du modèle Python ne suffit pas sur cette plateforme.

Les sons de guitare proviennent de [tonejs-instruments, N. P. Brosowsky](https://github.com/nbrosowsky/tonejs-instruments), échantillons CC BY 3.0. Ils sont installés localement et transposés pour les frettes. Le gain de sortie des instruments a été doublé.

Le détail des vérifications actuelles est dans **VALIDATION.md**. La recherche ci-dessous décrit le choix de départ et les alternatives ; le franchissement de ligne de la version initiale a été remplacé à la demande de l’utilisateur.

## Recommandation pour une première version

**Python + OpenCV + MediaPipe Hand Landmarker + FastAPI + pywebview + Web Audio** répond au besoin : caméra PC, interface web dans l’application, traitement local, piano superposé et notes déclenchées par les mouvements des doigts.

Le [guide officiel MediaPipe Python](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python) décrit les modes image, vidéo et flux en direct. Le suivi en mode vidéo évite de relancer la détection des paumes sur chaque image. Le modèle fournit 21 repères et permet de suivre deux mains. Le [papier MediaPipe Hands](https://arxiv.org/abs/2006.10214) explique la chaîne détection de paume puis repères des doigts.

Le mode VIDEO est exécuté dans un worker Python : il conserve une correspondance exacte entre image et repères. L’interface reçoit uniquement la dernière image disponible ; les événements de notes sont conservés séparément pour ne pas être perdus lorsque le rendu saute une image. Le mode LIVE_STREAM est une piste si l’inférence devient trop lente, mais demande de gérer les résultats asynchrones et les images éventuellement ignorées ([API officielle](https://developers.google.com/edge/api/mediapipe/python/mp/tasks/vision/HandLandmarker)).

## Alternatives

| Approche | Avantage | Compromis | Décision |
|---|---|---|---|
| MediaPipe Python / webcam RGB | Peu de matériel, traitement local, intégration Python | Profondeur et occultations limitées | Choisie pour démarrer |
| MediaPipe JavaScript / caméra navigateur | Pas de JPEG à transférer, vidéo directe dans le navigateur | Moins de Python, permissions caméra et moteur WebView à valider | Alternative pour réduire le transport |
| Capteur stéréo infrarouge de mains | Suivi spatial dédié, meilleure exploitation de la structure de la main | Matériel et SDK spécifiques | Évolution pour une interaction 3D |
| Caméra RGB-D + MediaPipe | Profondeur mesurée, possibilité de calibrer un plan réel | Coût, installation, bruit en profondeur, alignement RGB/profondeur | Évolution pour une table virtuelle |
| Réseau entraîné sur mesure | Geste adapté à l’usage | Dataset, annotation, entraînement, validation coûteux | Inutile avant d’avoir des données d’usage |

La [documentation Ultraleap](https://docs.ultraleap.com/hand-tracking/index.html) décrit un système à deux caméras infrarouges et un modèle de structure de main. Elle documente aussi [les limites d’occultation](https://docs.ultraleap.com/xr-guidelines/Getting%20started/design-principles.html) et [le placement du capteur](https://docs.ultraleap.com/touchfree-user-manual/camera-placement.html). Ces sources expliquent l’approche ; les disponibilités et prix du matériel ne sont pas établis ici.

La recherche [GMH-D : profondeur ajoutée à MediaPipe](https://arxiv.org/abs/2308.01088) examine l’amélioration du suivi 3D avec une caméra RGB-D. Pour ce projet, je recommande cette piste seulement après la validation du prototype webcam, si le contact avec un plan réel devient un critère prioritaire.

## Un son plus crédible

Un simple oscillateur ne reproduit pas l’attaque et la résonance d’un piano. Le [sampler officiel Tone.js](https://github.com/Tonejs/Tone.js/blob/dev/examples/sampler.html) montre l’usage des échantillons Salamander, espacés de trois demi-tons et transposés pour remplir le clavier. MusicAR applique ce principe directement avec les nœuds Web Audio natifs, sans bibliothèque web supplémentaire.

Les fichiers sont téléchargés depuis [la distribution Tone.js](https://tonejs.github.io/audio/salamander/). Le [projet Salamander](https://github.com/studiorack/salamander-grand-piano/blob/master/README.md) attribue les enregistrements à Alexander Holm, décrit 16 couches de vélocité et indique CC BY 3.0. Cette première version emploie 17 fichiers MP3, une couche, de Do3 à Do7. Le gain et le filtre dépendent de la vitesse de frappe ; le sustain et la réverbération prolongent les notes.

L’option Web Audio `latencyHint: "interactive"` demande un comportement adapté au jeu ; c’est une préférence et pas une garantie de latence. [MDN baseLatency](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/baseLatency) explique la différence entre cette préférence et la latence de traitement réelle. Une mesure complète nécessite de comparer le mouvement, la capture, l’inférence, le transport et la sortie audio sur le PC cible.

## Interface web intégrée

[pywebview](https://pywebview.flowrl.com/guide/usage.html) peut charger une URL locale dans une fenêtre native. Son guide demande que la boucle GUI et le serveur ne se bloquent pas ; le serveur est donc dans un thread séparé. Windows utilise Edge WebView2. La capture caméra côté Python évite de dépendre des permissions `getUserMedia` dans le composant web embarqué.

## Critères de réussite et prochaines étapes

1. Vérifier caméra, modèle, échantillons et fenêtre native sur le PC cible.
2. Tester les frappes avec une puis deux mains : aucune note à la première acquisition, pas de répétition en maintien, note relâchée après perte du suivi.
3. Observer les faux positifs, notes manquées et confort de la ligne de frappe. Ajuster zone, doigts actifs et sensibilité.
4. Mesurer la latence complète avant de promettre une performance instrumentale. Enregistrer des événements de repères anonymes, avec consentement, pour reproduire les gestes problématiques.
5. Si le jeu sur table est nécessaire : ajouter calibration de plan et profondeur mesurée. Si la fidélité sonore est prioritaire : banque SFZ multicouche, résonance et pédale MIDI.

Une webcam classique permet un prototype d’instrument augmenté convaincant. Elle ne fournit ni toucher physique ni certitude de contact 3D ; c’est une limite de cette méthode, à prendre en compte dans le geste demandé au joueur.
