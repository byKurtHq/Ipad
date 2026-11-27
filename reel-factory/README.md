# Reel Factory

Chaîne de production de Reels Instagram : à partir des vidéos enregistrées (Saved) et des rushes personnels,
elle reproduit la méthode de montage des Reels de référence (coupes à l'image près, étalonnage mesuré,
typographie animée mot à mot, silhouettes, glitchs, son de la référence) et livre des MP4 9:16 contrôlés.

Tout tourne en local avec **ffmpeg + Python** (numpy, Pillow, yt-dlp, faster-whisper, rembg). Les polices (SIL OFL),
les sons (synthèse) et les overlays (procéduraux) sont libres de droits.

## Installation (PC de production)
```
git clone -b claude/sharp-pasteur-y53z1k https://github.com/byKurtHq/Ipad.git
xcopy /E /I Ipad\reel-factory D:\ReelFactory\_kit
python D:\ReelFactory\_kit\install.py --root D:/ReelFactory --rushes D:/RUSH --project "D:/Vault IA"
```
L'installeur crée l'arborescence, installe les bibliothèques, les polices, les sons, le skill `/reel-factory`
et les 5 agents dans `D:/Vault IA/.claude/`, puis rend un mini-reel de test.

## Arborescence
| Dossier | Contenu |
|---|---|
| `00_inbox/` | Export Instagram, `saved_urls.txt` |
| `01_references/<ID>/` | `ref.mp4`, `meta.json`, `analysis.json/.md`, `brief.md`, `plan.json`, `sheets/` |
| `02_clips/<ID>/` | Propositions de clips, extraits retenus, `selection.json` |
| `03_projects/<ID>/` | `spec.json` (projet de montage modifiable), rendus intermédiaires, audio |
| `04_reels/` | Reels finaux (`_9x16.mp4`, `_16x9.mp4`), `_apercus/`, `_sans_son_original/`, fiches QC |
| `05_publication/` | Accroche, légende, hashtags, couverture par Reel |
| `06_rapports/` | `registre.json/.csv`, `rapport_production.md/.html` |
| `_assets/` | Polices, sons, overlays | 
| `_index/` | Index et tags des rushes, planches, usages |

## Commandes
`python rf.py` liste tout. Principales : `saved`, `fetch`, `analyze`, `rushes`, `match`, `edit`, `text`, `sil`,
`sound`, `compose`, `render`, `qc`, `pub`, `report`, `ledger`. Format d'un projet : voir `templates/exemple_methode_A_anger.json`
(reconstruction exacte du Reel n°1) et l'aide de chaque module (`rf/edit.py`, `rf/textfx.py`, `rf/sound.py`).

## Équipe d'agents (Claude Code)
1. `rf-ref-analyst` : récupère et analyse chaque référence, écrit le brief.
2. `rf-clip-scout` : indexe et tague les rushes, choisit les meilleurs extraits.
3. `rf-editor` : montage, étalonnage, effets, typographie.
4. `rf-sound-designer` : son de la référence, SFX, mixage -14 LUFS.
5. `rf-qc-social` : export, contrôle qualité, fiche de publication.

Méthode détaillée : `skill/METHODE.md`. Orchestration : `skill/SKILL.md`.

## Limites assumées
- La liste des Enregistrés vient de l'export officiel Instagram ou de la page Enregistrements lue dans le navigateur
  de l'utilisateur : pas de connexion automatisée au compte.
- Les références sont récupérées uniquement si elles sont publiques, pour analyse privée, avec des pauses.
- Publier de préférence avec le son original sélectionné dans Instagram.
