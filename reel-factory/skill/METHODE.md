# La méthode de référence (Reels du 27-11-26)

Mesurée image par image sur les 3 Reels de référence, puis appliquée aux 3 premiers Reels livrés
(`D:\output\Reel1_Anger_hoodie.mp4`, `Reel2_Sinner_tshirt.mp4`, `Reel3_Trying_17-11.mp4`).
**C'est la référence de qualité absolue.** Chaque nouveau Reel reproduit la méthode *de sa propre référence*
avec le même niveau d'exigence : on copie la structure, le rythme, la typo, l'étalonnage et le son de la vidéo de
référence, mais on remplace toutes les images par les clips personnels.

## 1. Principe

1. La **référence dicte tout** : chaque coupe tombe à la même image, chaque mot apparaît à la même image,
   l'étalonnage reprend ses mesures (luminance, saturation, dominante), le son est le sien.
2. Les **images sont 100 % personnelles** (clips de l'utilisateur), jamais celles de la référence.
3. **Rien d'aléatoire** : chaque effet existe parce que la référence l'utilise ou parce qu'il sert le message.

## 2. Image

| Élément | Règle |
|---|---|
| Source | Rushes Sony 1920×1080 à 50 i/s |
| Cadence | Celle de la référence (24 ou 30 i/s) |
| Ralenti | Chaque image source = une image de sortie (`speed: auto` = 24/50 = 0,48 ou 30/50 = 0,6) |
| Coupes | Uniquement des coupes franches, **aux mêmes images que la référence** (liste `cuts_t` de `analysis.json`) |
| Mouvement | Léger zoom avant continu sur chaque plan (`z0` → `z1`, +0,03 à +0,15), centré sur le sujet (`cx`, `cy`) |
| Exposition | `exposure: auto` (gamma vers une luminance de 0,40) avant l'étalonnage ; +`eq=gamma=1.2` à `1.25` sur les visages sombres |
| Cadrage | Visage ou corps de face lisible ; jamais de plans de dos ni allongés |
| Format | Master 9:16 1080×1920 ; si la référence est en 16:9, on livre aussi la version 16:9 (`--landscape`) |

### Étalonnages mesurés (presets de `rf/edit.py`)
- **G1** (réf. « My anger… ») : très sombre, désaturé (0,28), bleu-vert, vignette, grain 9.
- **G2** (réf. « Yes I'm a sinner… ») : sombre contrasté bleu-vert, saturation 0,5, grain 7.
- **G3** (réf. « I'm always trying… ») : délavé (noirs relevés), saturation 0,45, léger flou, alterné avec **RED**
  (plans teintés rouge) ; décalage RVB **RGB** sur les images glitch.
- Pour une nouvelle référence : `rf.py edit gradetest --ref <ID> --shot <n> --grades G1,G2,G3,match,...` puis choisir
  le preset le plus proche ou `"grade": "match:G1"` (transfert couleur mesuré + finition).

### Effets signature
- **Ouverture flash** : 4 plans d'une image avec `post: ["RGB"]`, puis la **silhouette blanche** détourée
  (`silhouettes`, rembg) qui clignote 3 fois (images 4, 6, 8) sur le premier mot.
- **Montage glitch** sur un mot fort : 11 i normale → 4 i RED → 4 i insert RED+RGB → 1 i RGB → 1 i RED → 2 i.
- **Silhouette flash** sur une coupe (images n et n+1).
- Inserts d'objets (disque, poignée, haltère, lumières, shaker) de 1 à 2 s, sans personne.

## 3. Texte (la signature)

Toujours calé **à l'image près** sur la voix (transcription mot à mot `faster-whisper` + segments du calque texte
de la référence). Apparition sèche, sans fondu, sauf si la référence anime.

| Variante | Typo | Couleurs | Placement |
|---|---|---|---|
| A (« anger ») | Didone majuscule (Bodoni MT), `serif` : hauteur de capitale 0,13 u, « ANGER » = 0,58 u de large | Blanc (245,244,245) / rouge sang (169,23,29), mots forts en rouge, mots bicolores (BE blanc + CAUSE rouge) | Un mot à la fois, centré, y = 0,49 ; mot secondaire sous le principal (DAY sous SINGLE) ; texture grunge |
| B (« sinner ») | Garamond minuscule, `gara` (« walked » = 0,483 u) et `gara_big` pour les mots isolés (« human » = 0,722 u) | Blanc + lilas (150,135,235), or (215,175,65), rouge (200,30,35), saumon (215,95,85), bleu clair (150,205,245), orange (245,165,25) | Mots empilés en colonne (y 0,30 / 0,48 / 0,67…) dont la position change à chaque phrase ; italique, souligné, gras italique sur les mots clés ; grands mots isolés centrés ; plus de texte quand la voix s'arrête |
| C (« trying ») | `serif` + glitch entre 3 polices toutes les 3 images (`heavy`, `serif`, `condensed`) | Rouge / blanc | Mots forts glitchés (DON'T, KILL, ME) ; empilement en haut à gauche (JUST / HELP / ME) |

Unités : u = min(largeur, hauteur). En 9:16, u = 1080 : la taille en pixels reste celle de l'original.
Zones de sécurité Instagram (9:16) : rien au-dessus de 11,5 % de la hauteur ni sous 75 %, marges latérales 5,5 %.

## 4. Son
- L'audio de la référence (voix + musique) est repris tel quel et normalisé à **-14 LUFS, crête -1 dBTP**.
- Sound design **en renfort seulement** (bibliothèque `_assets/sfx`, générée, libre de droits) : impact grave sous
  un flash, whoosh sur une transition, glitch sur un flash RVB, riser avant un drop, 12 à 20 dB sous la voix,
  jamais sur un mot important. Si la référence a déjà l'impact, on n'en ajoute pas.
- Publication recommandée avec le **son original choisi dans Instagram** (version `_sans_son_original/`), sinon
  risque de blocage pour droits d'auteur.

## 5. Export
H.264 High, CRF 18, débit max 20 Mb/s, yuv420p, AAC 192 kb/s 48 kHz, `+faststart` ; aperçu < 28 Mo pour le téléphone.

## 6. Retours de l'utilisateur (à respecter partout)
- Seulement des clips où **l'utilisateur apparaît** (+ inserts d'objets sans personne).
- Des séries où on le voit bien ; **pas de dos, pas allongé** (leg curl, hack squat incliné, développé couché).
- **Varier les clips** : chaque Reel a son propre jeu de clips ; aucun plan commun entre Reels d'un même lot.
- Visage lisible : resserrer et éclaircir les gros plans quand la caméra était basse.
