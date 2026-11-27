---
name: reel-factory
description: Chaîne de production automatisée de Reels Instagram à partir des vidéos enregistrées (Saved) et des rushes personnels, avec une équipe de 5 agents (analyse des références, recherche de clips, montage, sound design, QC et publication). À utiliser dès qu'il faut produire, reprendre ou contrôler des Reels « avec la méthode », traiter les vidéos enregistrées Instagram, ou relancer la production (registre, rapport).
---

# Reel Factory : production autonome de Reels

Outils : `python <KIT>/rf.py <commande>` (KIT = dossier du kit, par défaut `D:/ReelFactory/_kit`,
configuration `D:/ReelFactory/config.json`). Méthode de référence : `METHODE.md` (même dossier que ce skill).
Profil du créateur et retours : `D:/ReelFactory/PROFIL_CREATEUR.md`.

## Priorités (dans l'ordre)
1. Aucune vidéo enregistrée sans traitement (registre `06_rapports/registre.json`).
2. Reproduire fidèlement la méthode (METHODE.md) de chaque référence.
3. Les meilleurs clips personnels pour chaque plan (variés, de face, l'utilisateur visible).
4. Qualité artistique et technique maximale (QC obligatoire).
5. Un message fort et cohérent. 6. Optimisé pour la croissance. 7. Organisation traçable.

## Règles de conduite
- **Ne jamais poser de question à l'utilisateur** pendant la production : décider, documenter, continuer.
- Une difficulté sur une vidéo ne bloque jamais la suite : noter dans le registre (`ledger set ID status=failed:<raison> note=...`) et passer à la suivante.
- Ne jamais publier sur Instagram, ne jamais saisir ni lire d'identifiants, ne contourner aucune protection.
  Les références sont téléchargées uniquement si elles sont publiques, pour analyse privée, avec pauses.
- Ne jamais réutiliser d'images de la référence dans un Reel : seulement sa méthode et son audio.
- Toujours mettre à jour le registre puis `rf.py report` après chaque Reel.

## 0. Démarrage (une fois)
```
python install.py --root D:/ReelFactory --rushes D:/RUSH --project "D:/Vault IA"
python rf.py rushes index            # inventaire + planches de tous les rushes (incrémental)
```
Puis l'agent 2 tague tous les clips (personne, tenue, cadrage, angle, allongé, exercice, qualité) et ajoute les
meilleurs moments (`rushes moment`). C'est l'investissement qui rend chaque montage rapide et juste.

## 1. Liste des vidéos enregistrées
Dans cet ordre, s'arrêter dès qu'une source fonctionne :
1. `rf.py saved find-exports` → `rf.py saved import-export <dossier|zip>` (export officiel Instagram).
2. Navigateur de l'utilisateur déjà connecté (Claude in Chrome) : ouvrir instagram.com → profil → Enregistrements
   (toutes les publications + chaque collection), faire défiler jusqu'en bas, relever les liens `/reel/…` et `/p/…`
   dans `00_inbox/saved_urls.txt` (une URL par ligne, `# Collection: Nom` avant chaque collection), puis
   `rf.py saved import-urls 00_inbox/saved_urls.txt`. Lire seulement la page ; aucun téléchargement par le navigateur.
3. Sinon : documenter l'obstacle dans le rapport et écrire `00_inbox/LISEZMOI.txt` (comment fournir l'export).
   Continuer avec les références déjà connues.

## 2. Boucle de production (pour CHAQUE référence du registre)
| Étape | Agent | Commandes | Statut registre |
|---|---|---|---|
| Récupération | 1 `rf-ref-analyst` | `rf.py fetch <ID>` | downloaded |
| Analyse + brief | 1 | `rf.py analyze <ID>` ; lire `sheets/*.jpg`, `analysis.md` ; écrire `brief.md`, `plan.json`, `text_events.json` | analyzed |
| Clips | 2 `rf-clip-scout` | `rf.py match propose <ID> --plan …/plan.json` ; vérifier avec `rushes sheet` ; écrire les plans dans `spec.json` | clips_selected |
| Montage + texte | 3 `rf-editor` | `rf.py edit build`, `rf.py sil`, `rf.py text render`, `rf.py text preview` | edited |
| Son | 4 `rf-sound-designer` | `rf.py sound cues`, `rf.py sound mix` | sound_done |
| Export + QC + publication | 5 `rf-qc-social` | `rf.py render <spec> [--landscape]`, lecture `*.qc.jpg`, `rf.py pub init` | qc_pass → delivered |

Fichiers d'un projet : `03_projects/<ID>/spec.json` (source de vérité du montage, modifiable plus tard),
`build_*`, `layer_*`, `audio/`. Reels : `04_reels/NNN_<slug>_<ID>_9x16.mp4`. Extraits choisis : `02_clips/<ID>/`.

## 3. Orchestration
- Lancer les agents avec l'outil Agent (`subagent_type` = `rf-ref-analyst`, `rf-clip-scout`, `rf-editor`,
  `rf-sound-designer`, `rf-qc-social`). S'ils ne sont pas chargés dans la session, utiliser `general-purpose` et
  coller le contenu du fichier `.claude/agents/<nom>.md` en tête du prompt.
- Travailler en flux : pendant qu'une référence est montée, l'agent 1 analyse les 2 suivantes en arrière-plan.
  Un seul rendu lourd à la fois (CPU).
- Chaque agent renvoie un résumé court (≤ 10 lignes) : décisions, fichiers, problèmes. Le détail reste dans les fichiers.
- Après chaque Reel : `rf.py ledger set <ID> status=delivered` puis `rf.py report`.
- Contrôle qualité qui échoue : au plus 2 allers-retours ciblés ; ensuite livrer la meilleure version avec une
  note précise dans le registre (`qc=a_revoir`).

## 4. Fin de mission
`rf.py report` + résumé : nombre de références, Reels livrés, en échec (avec raison), où sont les fichiers,
ce qui attend l'utilisateur (vérification visuelle, publication avec le son original).
