#!/usr/bin/env python
"""Reel Factory - point d'entree unique.

python rf.py <commande> [options]      (lancer depuis n'importe ou ; config: RF_CONFIG ou config.json)

Commandes :
  ledger    registre de production (stats, list, next, set, csv)
  saved     import de la liste des videos enregistrees (export Instagram / fichier d'URLs)
  fetch     telechargement des references (yt-dlp, public, avec pauses)
  analyze   analyse complete d'une reference (coupes, texte, couleur, audio, transcription)
  rushes    index des clips personnels, planches, tags, moments
  match     propositions de clips pour chaque plan d'une reference
  edit      rendu des plans + montage de base (spec.json)
  text      calque texte anime (PNG) depuis spec.json
  sil       silhouettes detourees (flash blanc)
  sfx       bibliotheque de sound design (build, list)
  sound     mixage audio (voix/musique de reference + SFX + normalisation -14 LUFS)
  compose   export final MP4 (9:16 et/ou 16:9) + apercu leger
  qc        controle qualite automatique + planche de verification
  pub       fiche de publication (accroche, legende, hashtags, couverture)
  report    rapport de production (Markdown + HTML)
  render    enchaine edit + sil + text + sound + compose + qc pour un projet
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib

CMDS = {'ledger': 'ledger', 'saved': 'ig_saved', 'fetch': 'fetch', 'analyze': 'analyze', 'rushes': 'rushes',
        'match': 'match', 'edit': 'edit', 'text': 'textfx', 'sil': 'silhouette', 'sfx': 'sfx', 'sound': 'sound',
        'compose': 'compose', 'qc': 'qc', 'pub': 'pubkit', 'report': 'report', 'render': 'render',
        'overlays': 'overlays', 'fonts': 'fonts'}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__); sys.exit(0 if len(sys.argv) < 2 else 2)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    mod = importlib.import_module('rf.' + CMDS[sys.argv[1]])
    r = mod.main(sys.argv[2:])
    sys.exit(r if isinstance(r, int) else 0)
