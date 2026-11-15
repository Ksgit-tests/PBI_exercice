"""Étape A2 — Explorer les données et relever les anomalies de qualité.
Lancement (dans le dossier Projet_BI) : python explorer_donnees.py
Lit data/raw/ et écrit un résumé à l'écran + le fichier rapport_qualite.txt"""

# ---------------------------------------------------------------------------
# 1. Les outils utilisés
# ---------------------------------------------------------------------------
import json          # lire les fichiers .json (le format des données StatsBomb)
import os            # construire les chemins de fichiers (data/raw/...)
import sys           # régler l'affichage du terminal
import collections   # Counter : un dictionnaire qui compte (ex. : buts par équipe)
import unicodedata   # repérer les lettres accentuées dans les noms

sys.stdout.reconfigure(encoding="utf-8")   # afficher les accents dans le terminal Windows
RAW = os.path.join("data", "raw")          # dossier créé par telecharger_donnees.py

lignes = []                                # tout ce qu'on affiche, gardé pour le rapport
def note(texte=""):
    """Affiche une ligne à l'écran ET la mémorise pour rapport_qualite.txt."""
    print(texte)
    lignes.append(texte)

total = collections.Counter()              # totaux sur les 11 matchs
types = collections.Counter()              # nombre d'événements par type (Pass, Shot...)
joueurs_accentues = set()                  # set = ensemble sans doublon

# ---------------------------------------------------------------------------
# 2. On parcourt les deux compétitions, puis chaque match
# ---------------------------------------------------------------------------
note("=== EXPLORATION DES DONNÉES — 11 matchs du Maroc ===")
for comp in ("mondial_2022", "can_2023"):
    # matches.json = la liste des matchs : identifiant, date, équipes, score officiel...
    with open(os.path.join(RAW, comp, "matches.json"), encoding="utf-8") as f:
        matchs = json.load(f)
    note(f"\n--- {comp} ({len(matchs)} matchs) ---")

    for m in sorted(matchs, key=lambda x: x["match_date"]):      # dans l'ordre des dates
        mid = m["match_id"]
        dom = m["home_team"]["home_team_name"]                   # équipe « à domicile »
        ext = m["away_team"]["away_team_name"]                   # équipe « à l'extérieur »

        # Le fichier events/<id>.json = TOUTES les actions du match (≈ 3 500).
        # Chaque action est un dictionnaire, par exemple :
        # {"type": {"name": "Shot"}, "period": 1, "minute": 42,
        #  "team": {"name": "Morocco"}, "player": {"name": "Hakim Ziyech"},
        #  "location": [102.3, 35.1],
        #  "shot": {"statsbomb_xg": 0.08, "outcome": {"name": "Saved"}}}
        chemin = os.path.join(RAW, comp, "events", f"{mid}.json")
        if os.path.getsize(chemin) == 0:                         # garde-fou : fichier vide
            note(f"!! {chemin} est vide : relancer telecharger_donnees.py")
            continue
        with open(chemin, encoding="utf-8") as f:
            ev = json.load(f)

        # -------------------------------------------------------------------
        # 3. Les contrôles de qualité sur ce match
        # -------------------------------------------------------------------
        periodes = sorted({e["period"] for e in ev})             # 1-2 = temps réglementaire,
                                                                 # 3-4 = prolongations, 5 = tirs au but
        sans_position = sum(1 for e in ev if "location" not in e)          # actions sans (x, y)
        tab = sum(1 for e in ev if e["period"] == 5)                       # séance de tirs au but
        csc = sum(1 for e in ev if e["type"]["name"] == "Own Goal For")    # buts contre son camp

        buts = collections.Counter()      # buts recalculés, par équipe
        xg = collections.Counter()        # somme des xG, par équipe
        for e in ev:
            types[e["type"]["name"]] += 1

            # Nom accentué ? On retire les accents ; si le nom change, il en avait.
            p = e.get("player", {}).get("name", "")
            sans_accent = unicodedata.normalize("NFKD", p).encode("ascii", "ignore").decode()
            if p and sans_accent != p:
                joueurs_accentues.add(p)

            if e["period"] == 5:          # RÈGLE 1 : la séance de tirs au but ne compte pas
                continue
            if e["type"]["name"] == "Shot":
                xg[e["team"]["name"]] += e["shot"].get("statsbomb_xg", 0)
                if e["shot"]["outcome"]["name"] == "Goal":
                    buts[e["team"]["name"]] += 1
            if e["type"]["name"] == "Own Goal For":   # RÈGLE 2 : le but contre son camp
                buts[e["team"]["name"]] += 1          # est crédité à l'équipe qui en profite

        # -------------------------------------------------------------------
        # 4. Le test de validation : retrouve-t-on le score officiel ?
        # -------------------------------------------------------------------
        ok = (buts[dom], buts[ext]) == (m["home_score"], m["away_score"])
        note(f"{m['match_date']}  {m['competition_stage']['name']:<16} "
             f"{dom} {m['home_score']}-{m['away_score']} {ext}")
        note(f"   {len(ev)} événements | périodes {periodes} | sans position : {sans_position}"
             f" | tirs au but (période 5) : {tab} | buts contre son camp : {csc}")
        note(f"   xG : {dom} {xg[dom]:.2f} - {xg[ext]:.2f} {ext} | buts recalculés : "
             f"{buts[dom]}-{buts[ext]} -> {'OK' if ok else 'ÉCART'}")
        total.update(evenements=len(ev), sans_position=sans_position,
                     periode5=tab, csc=csc, ok=int(ok))

# ---------------------------------------------------------------------------
# 5. La synthèse sur les 11 matchs, puis l'écriture du rapport
# ---------------------------------------------------------------------------
note("\n=== SYNTHÈSE ===")
note(f"Événements : {total['evenements']} | sans position : {total['sans_position']} "
     f"({100 * total['sans_position'] / max(total['evenements'], 1):.1f} %)")
note(f"Événements de séances de tirs au but (période 5) : {total['periode5']} -> à exclure des tirs")
note(f"Buts contre son camp : {total['csc']} -> codés 'Own Goal For', pas comme un tir")
note(f"Scores recalculés conformes : {total['ok']}/11")
note(f"Joueurs aux noms accentués : {len(joueurs_accentues)} "
     f"(ex. : {', '.join(sorted(joueurs_accentues)[:4])})")
note("\nTypes d'événements les plus fréquents :")
for t, n in types.most_common(12):
    note(f"   {t:<20} {n}")

with open("rapport_qualite.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lignes))
print("\nRapport écrit dans rapport_qualite.txt")
