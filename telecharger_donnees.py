"""Télécharge les 11 matchs du Maroc (Mondial 2022 + CAN 2023) depuis StatsBomb Open Data.
Source : https://github.com/statsbomb/open-data  —  à citer : « Données : StatsBomb Open Data ».
Lancement : python telecharger_donnees.py   (crée le dossier data/raw/)
Peut être relancé : il ne retélécharge que les fichiers absents ou vides."""
import json, os, urllib.request

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/"
COMPETITIONS = {"mondial_2022": (43, 106), "can_2023": (1267, 107)}
EQUIPE = "Morocco"

def telecharger(chemin):
    with urllib.request.urlopen(BASE + chemin, timeout=120) as reponse:
        return reponse.read()

for nom, (comp, saison) in COMPETITIONS.items():
    dossier = os.path.join("data", "raw", nom)
    for sous in ("events", "lineups"):
        os.makedirs(os.path.join(dossier, sous), exist_ok=True)
    tous = json.loads(telecharger(f"matches/{comp}/{saison}.json"))
    matchs = [m for m in tous if EQUIPE in (m["home_team"]["home_team_name"],
                                           m["away_team"]["away_team_name"])]
    with open(os.path.join(dossier, "matches.json"), "w", encoding="utf-8") as f:
        json.dump(matchs, f, ensure_ascii=False, indent=1)
    for n, m in enumerate(matchs, 1):
        mid = m["match_id"]
        for sous in ("events", "lineups"):
            fichier = os.path.join(dossier, sous, f"{mid}.json")
            if os.path.exists(fichier) and os.path.getsize(fichier) > 0:
                continue                              # déjà téléchargé correctement
            contenu = telecharger(f"{sous}/{mid}.json")   # d'abord télécharger en mémoire…
            json.loads(contenu)                           # …vérifier que c'est du JSON valide…
            with open(fichier, "wb") as f:                # …et seulement ensuite écrire le fichier
                f.write(contenu)
        print(f"{nom} : {n}/{len(matchs)}  {m['home_team']['home_team_name']} "
              f"{m['home_score']}-{m['away_score']} {m['away_team']['away_team_name']}")
print("Terminé : 11 matchs attendus.")
