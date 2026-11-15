"""Étape A4 — ETL : transformer les fichiers JSON de StatsBomb en 9 tables CSV (modèle en constellation).

Lancement (dans le dossier Projet_BI) :   python etl.py
Lit    : data/raw/      (créé par telecharger_donnees.py)
Écrit  : data/csv/      (les 9 CSV + dictionnaire_donnees.csv + controles_etl.txt)

Le script suit les trois lettres de l'ETL :
  E — Extract   : lire les fichiers JSON des 11 matchs
  T — Transform : nettoyer, traduire, attribuer les clés de substitution, appliquer les règles
  L — Load      : écrire les CSV, puis CONTRÔLER le résultat (test des 11 scores)
Aucune bibliothèque à installer : uniquement des modules fournis avec Python."""

import csv, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
RAW = os.path.join("data", "raw")
OUT = os.path.join("data", "csv")
os.makedirs(OUT, exist_ok=True)

# =============================================================================
# 0. TABLES DE TRADUCTION (règles métier écrites à la main, une fois pour toutes)
# =============================================================================
COMPETITIONS = {"mondial_2022": "Coupe du monde 2022", "can_2023": "CAN 2023"}

PHASES = {  # nom StatsBomb -> (libellé français, ordre de tri)
    "Group Stage": ("Phase de groupes", 1), "Round of 16": ("Huitièmes de finale", 2),
    "Quarter-finals": ("Quarts de finale", 3), "Semi-finals": ("Demi-finale", 4),
    "3rd Place Final": ("Match pour la 3e place", 5), "Final": ("Finale", 6),
}

STADES = {  # stade -> (ville, pays) : nécessaire pour la carte dans Power BI
    "Al Thumama Stadium": ("Doha", "Qatar"),
    "Al Bayt Stadium": ("Al Khor", "Qatar"),
    "Sheikh Khalifa International Stadium": ("Al Rayyan", "Qatar"),
    "Education City Stadium": ("Al Rayyan", "Qatar"),
    "Stade Laurent Pokou": ("San-Pédro", "Côte d'Ivoire"),
}

EQUIPES = {  # nom StatsBomb -> (nom français, confédération)
    "Morocco": ("Maroc", "CAF"), "Croatia": ("Croatie", "UEFA"), "Belgium": ("Belgique", "UEFA"),
    "Canada": ("Canada", "CONCACAF"), "Spain": ("Espagne", "UEFA"), "Portugal": ("Portugal", "UEFA"),
    "France": ("France", "UEFA"), "Tanzania": ("Tanzanie", "CAF"), "Congo DR": ("RD Congo", "CAF"),
    "Zambia": ("Zambie", "CAF"), "South Africa": ("Afrique du Sud", "CAF"),
}

POSTES = {  # poste StatsBomb -> (poste en français, ligne)
    "Goalkeeper": ("Gardien", "Gardien"),
    "Right Back": ("Arrière droit", "Défense"), "Left Back": ("Arrière gauche", "Défense"),
    "Right Center Back": ("Défenseur central droit", "Défense"),
    "Left Center Back": ("Défenseur central gauche", "Défense"),
    "Center Back": ("Défenseur central", "Défense"),
    "Right Wing Back": ("Piston droit", "Défense"), "Left Wing Back": ("Piston gauche", "Défense"),
    "Center Defensive Midfield": ("Milieu défensif", "Milieu"),
    "Right Defensive Midfield": ("Milieu défensif droit", "Milieu"),
    "Left Defensive Midfield": ("Milieu défensif gauche", "Milieu"),
    "Right Center Midfield": ("Milieu central droit", "Milieu"),
    "Left Center Midfield": ("Milieu central gauche", "Milieu"),
    "Center Midfield": ("Milieu central", "Milieu"),
    "Right Midfield": ("Milieu droit", "Milieu"), "Left Midfield": ("Milieu gauche", "Milieu"),
    "Center Attacking Midfield": ("Milieu offensif", "Milieu"),
    "Right Wing": ("Ailier droit", "Attaque"), "Left Wing": ("Ailier gauche", "Attaque"),
    "Center Forward": ("Avant-centre", "Attaque"),
    "Right Center Forward": ("Attaquant droit", "Attaque"),
    "Left Center Forward": ("Attaquant gauche", "Attaque"),
}

TYPES = {  # type StatsBomb -> (libellé français, famille)
    "Pass": ("Passe", "Offensive"), "Ball Receipt*": ("Réception", "Offensive"),
    "Carry": ("Conduite de balle", "Offensive"), "Dribble": ("Dribble", "Offensive"),
    "Shot": ("Tir", "Offensive"), "Foul Won": ("Faute subie", "Offensive"),
    "Offside": ("Hors-jeu", "Offensive"), "Shield": ("Protection de balle", "Offensive"),
    "Pressure": ("Pressing", "Défensive"), "Ball Recovery": ("Récupération", "Défensive"),
    "Interception": ("Interception", "Défensive"), "Clearance": ("Dégagement", "Défensive"),
    "Block": ("Contre", "Défensive"), "Duel": ("Duel", "Défensive"),
    "50/50": ("Duel 50/50", "Défensive"), "Dribbled Past": ("Dribblé", "Défensive"),
    "Foul Committed": ("Faute commise", "Défensive"), "Goal Keeper": ("Action du gardien", "Défensive"),
    "Miscontrol": ("Mauvais contrôle", "Perte de balle"), "Dispossessed": ("Dépossédé", "Perte de balle"),
    "Error": ("Erreur", "Perte de balle"),
    "Own Goal For": ("But contre son camp (bénéficiaire)", "Autre"),
    "Own Goal Against": ("But contre son camp (concédé)", "Autre"),
    "Substitution": ("Remplacement", "Autre"), "Player On": ("Entrée en jeu", "Autre"),
    "Player Off": ("Sortie du terrain", "Autre"), "Starting XI": ("Composition de départ", "Autre"),
    "Tactical Shift": ("Changement tactique", "Autre"), "Half Start": ("Début de période", "Autre"),
    "Half End": ("Fin de période", "Autre"), "Injury Stoppage": ("Arrêt pour blessure", "Autre"),
    "Referee Ball-Drop": ("Balle à terre", "Autre"), "Bad Behaviour": ("Comportement antisportif", "Autre"),
}

INCONNU = "Inconnu"

# =============================================================================
# 1. EXTRACT — lire les 11 matchs et leurs événements
# =============================================================================
matchs = []                                   # liste de (compétition, match, événements)
for dossier, competition in COMPETITIONS.items():
    with open(os.path.join(RAW, dossier, "matches.json"), encoding="utf-8") as f:
        for m in json.load(f):
            with open(os.path.join(RAW, dossier, "events", f"{m['match_id']}.json"), encoding="utf-8") as g:
                matchs.append((competition, m, json.load(g)))
matchs.sort(key=lambda t: t[1]["match_date"])  # ordre chronologique
print(f"Extract : {len(matchs)} matchs lus")

# =============================================================================
# 2. TRANSFORM — construire les dimensions
#    Chaque dimension : une clé de substitution (entier 1, 2, 3…) + la clé naturelle
#    de StatsBomb + des attributs lisibles. La clé 0 = membre « Inconnu ».
# =============================================================================

# --- dim_match --------------------------------------------------------------
dim_match, cle_match = [], {}                 # cle_match : id StatsBomb -> clé de substitution
dim_match.append(dict(cle_match=0, id_match="", date="", annee="", competition=INCONNU,
                      phase=INCONNU, ordre_phase=0, stade=INCONNU, ville=INCONNU, pays=INCONNU,
                      libelle_match=INCONNU))
for n, (competition, m, _) in enumerate(matchs, 1):
    cle_match[m["match_id"]] = n
    phase, ordre = PHASES.get(m["competition_stage"]["name"], (m["competition_stage"]["name"], 9))
    stade = m["stadium"]["name"].strip()                       # anomalie : espace en trop dans un nom
    ville, pays = STADES.get(stade, (INCONNU, INCONNU))
    dom, ext = m["home_team"]["home_team_name"], m["away_team"]["away_team_name"]
    dim_match.append(dict(
        cle_match=n, id_match=m["match_id"], date=m["match_date"], annee=m["match_date"][:4],
        competition=competition, phase=phase, ordre_phase=ordre, stade=stade, ville=ville, pays=pays,
        libelle_match=f"{EQUIPES[dom][0]} {m['home_score']}-{m['away_score']} {EQUIPES[ext][0]}"))

# --- dim_equipe -------------------------------------------------------------
noms_equipes = sorted({m["home_team"]["home_team_name"] for _, m, _ in matchs} |
                      {m["away_team"]["away_team_name"] for _, m, _ in matchs})
dim_equipe = [dict(cle_equipe=0, nom_equipe=INCONNU, nom_fr=INCONNU, confederation=INCONNU)]
cle_equipe = {}
for n, nom in enumerate(noms_equipes, 1):
    cle_equipe[nom] = n
    nom_fr, confed = EQUIPES.get(nom, (nom, INCONNU))
    dim_equipe.append(dict(cle_equipe=n, nom_equipe=nom, nom_fr=nom_fr, confederation=confed))

# --- dim_joueur et dim_poste (à partir des joueurs et postes rencontrés) -----
joueurs, postes = {}, set()
for _, _, evenements in matchs:
    for e in evenements:
        if "player" in e:
            joueurs[e["player"]["id"]] = e["player"]["name"]
        if "position" in e:
            postes.add(e["position"]["name"])

dim_joueur = [dict(cle_joueur=0, id_joueur="", nom_joueur=INCONNU)]
cle_joueur = {}
for n, (pid, nom) in enumerate(sorted(joueurs.items(), key=lambda t: t[1]), 1):
    cle_joueur[pid] = n
    dim_joueur.append(dict(cle_joueur=n, id_joueur=pid, nom_joueur=nom))

dim_poste = [dict(cle_poste=0, poste=INCONNU, poste_fr=INCONNU, ligne=INCONNU)]
cle_poste = {}
for n, p in enumerate(sorted(postes), 1):
    cle_poste[p] = n
    poste_fr, ligne = POSTES.get(p, (p, INCONNU))
    dim_poste.append(dict(cle_poste=n, poste=p, poste_fr=poste_fr, ligne=ligne))

# --- dim_temps_jeu : GÉNÉRÉE COMPLÈTE (comme un calendrier), pas tirée des faits
PERIODES = {1: ("1re mi-temps", 0, 60), 2: ("2e mi-temps", 45, 110),
            3: ("1re prolongation", 90, 110), 4: ("2e prolongation", 105, 130)}

def tranche(periode, minute):
    """Range une minute dans une tranche de 15 min ; les arrêts de jeu sont isolés."""
    if periode == 1:
        bornes = [(15, "00-15", 1), (30, "15-30", 2), (45, "30-45", 3), (999, "45+ (arrêts de jeu)", 4)]
    elif periode == 2:
        bornes = [(60, "45-60", 5), (75, "60-75", 6), (90, "75-90", 7), (999, "90+ (arrêts de jeu)", 8)]
    else:
        return ("Prolongations", 9)
    for limite, libelle, ordre in bornes:
        if minute < limite:
            return (libelle, ordre)

dim_temps = [dict(cle_temps=0, periode=0, libelle_periode=INCONNU, minute="", tranche_15=INCONNU, ordre_tranche=0)]
cle_temps, n = {}, 0
for periode, (libelle, debut, fin) in PERIODES.items():
    for minute in range(debut, fin + 1):
        n += 1
        cle_temps[(periode, minute)] = n
        t, ordre = tranche(periode, minute)
        dim_temps.append(dict(cle_temps=n, periode=periode, libelle_periode=libelle,
                              minute=minute, tranche_15=t, ordre_tranche=ordre))

# --- dim_zone : le terrain StatsBomb mesure 120 x 80 ; on le découpe en 3 x 3 zones
TIERS = [(40, "Tiers défensif"), (80, "Tiers médian"), (999, "Tiers offensif")]
COULOIRS = [(80 / 3, "Gauche"), (160 / 3, "Axe"), (999, "Droit")]
dim_zone = [dict(cle_zone=0, zone=INCONNU, tiers=INCONNU, couloir=INCONNU)]
cle_zone, n = {}, 0
for _, nom_tiers in TIERS:
    for _, nom_couloir in COULOIRS:
        n += 1
        cle_zone[(nom_tiers, nom_couloir)] = n
        dim_zone.append(dict(cle_zone=n, zone=f"{nom_tiers} - {nom_couloir}", tiers=nom_tiers, couloir=nom_couloir))

def zone_de(location):
    """Position (x, y) -> clé de zone. StatsBomb oriente toujours le terrain dans le sens
    d'attaque de l'équipe qui agit : x grand = près du but adverse ; y petit = côté gauche."""
    if not location:
        return 0                                  # action sans position -> zone « Inconnu »
    x, y = location[0], location[1]
    t = next(nom for limite, nom in TIERS if x < limite)
    c = next(nom for limite, nom in COULOIRS if y < limite)
    return cle_zone[(t, c)]

# --- dim_type_action --------------------------------------------------------
types_vus = sorted({e["type"]["name"] for _, _, ev in matchs for e in ev})
dim_type = [dict(cle_type=0, type_action=INCONNU, libelle_fr=INCONNU, famille=INCONNU)]
cle_type = {}
for n, t in enumerate(types_vus, 1):
    cle_type[t] = n
    libelle, famille = TYPES.get(t, (t, "Autre"))
    dim_type.append(dict(cle_type=n, type_action=t, libelle_fr=libelle, famille=famille))

# =============================================================================
# 3. TRANSFORM — construire les tables de faits
# =============================================================================
fait_evenement, exclus_tab = [], 0
for _, m, evenements in matchs:
    dom, ext = m["home_team"]["home_team_name"], m["away_team"]["away_team_name"]
    for e in evenements:
        if e["period"] == 5:                      # RÈGLE 1 : la séance de tirs au but est exclue
            exclus_tab += 1
            continue
        equipe = e["team"]["name"]
        adversaire = ext if equipe == dom else dom    # dimension à rôles multiples
        t = e["type"]["name"]

        xg, but, reussie = 0.0, 0, 0
        if t == "Shot":
            xg = e["shot"].get("statsbomb_xg", 0.0)
            but = 1 if e["shot"]["outcome"]["name"] == "Goal" else 0
        if t == "Own Goal For":                   # RÈGLE 2 : but contre son camp crédité au bénéficiaire
            but = 1
        if t == "Pass":                           # une passe sans « outcome » est réussie
            reussie = 0 if "outcome" in e["pass"] else 1
        if t == "Dribble":
            reussie = 1 if e["dribble"]["outcome"]["name"] == "Complete" else 0

        loc = e.get("location")
        fait_evenement.append(dict(
            id_evenement=e["id"],                                   # dimension dégénérée
            cle_match=cle_match[m["match_id"]],
            cle_equipe=cle_equipe[equipe],
            cle_adversaire=cle_equipe[adversaire],
            cle_joueur=cle_joueur.get(e.get("player", {}).get("id"), 0),
            cle_poste=cle_poste.get(e.get("position", {}).get("name"), 0),
            cle_temps=cle_temps.get((e["period"], e["minute"]), 0),
            cle_zone=zone_de(loc),
            cle_type=cle_type[t],
            num_possession=e["possession"],                         # dimension dégénérée
            x=round(loc[0], 1) if loc else "", y=round(loc[1], 1) if loc else "",
            nb_actions=1, xg=round(xg, 4), but=but, action_reussie=reussie))

fait_match_equipe = []
for _, m, _ in matchs:
    dom, ext = m["home_team"]["home_team_name"], m["away_team"]["away_team_name"]
    for equipe, adversaire, pour, contre, domicile in (
            (dom, ext, m["home_score"], m["away_score"], 1),
            (ext, dom, m["away_score"], m["home_score"], 0)):
        fait_match_equipe.append(dict(
            cle_match=cle_match[m["match_id"]], cle_equipe=cle_equipe[equipe],
            cle_adversaire=cle_equipe[adversaire], domicile=domicile,
            buts_marques=pour, buts_encaisses=contre,
            victoire=int(pour > contre), nul=int(pour == contre), defaite=int(pour < contre)))

# =============================================================================
# 4. LOAD — écrire les CSV (UTF-8 avec BOM : accents lus correctement par Excel et Power BI)
# =============================================================================
TABLES = {
    "dim_match": dim_match, "dim_equipe": dim_equipe, "dim_joueur": dim_joueur,
    "dim_poste": dim_poste, "dim_temps_jeu": dim_temps, "dim_zone": dim_zone,
    "dim_type_action": dim_type, "fait_evenement": fait_evenement,
    "fait_match_equipe": fait_match_equipe,
}
for nom, lignes in TABLES.items():
    with open(os.path.join(OUT, f"{nom}.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        w.writeheader()
        w.writerows(lignes)
    print(f"Load    : {nom:<18} {len(lignes):>6} lignes")

# =============================================================================
# 5. CONTRÔLES — l'ETL est-il juste ?
# =============================================================================
rapport = []
def ctrl(texte):
    print(texte); rapport.append(texte)

ctrl("\n=== CONTRÔLES ===")
ctrl(f"Événements de séance de tirs au but exclus : {exclus_tab}")

# Test 1 : buts recalculés depuis fait_evenement = score officiel de fait_match_equipe
buts_calcules = {}
for f in fait_evenement:
    k = (f["cle_match"], f["cle_equipe"])
    buts_calcules[k] = buts_calcules.get(k, 0) + f["but"]
ok = sum(1 for r in fait_match_equipe
         if buts_calcules.get((r["cle_match"], r["cle_equipe"]), 0) == r["buts_marques"])
ctrl(f"Test 1 — buts recalculés = score officiel : {ok}/{len(fait_match_equipe)} lignes équipe-match")

# Test 2 : intégrité référentielle — chaque clé étrangère existe dans sa dimension
cles = {"cle_match": dim_match, "cle_equipe": dim_equipe, "cle_adversaire": dim_equipe,
        "cle_joueur": dim_joueur, "cle_poste": dim_poste, "cle_temps": dim_temps,
        "cle_zone": dim_zone, "cle_type": dim_type}
erreurs = 0
for col, dim in cles.items():
    nom_cle = "cle_equipe" if col == "cle_adversaire" else col
    existantes = {d[nom_cle] for d in dim}
    erreurs += sum(1 for f in fait_evenement if f[col] not in existantes)
ctrl(f"Test 2 — clés étrangères orphelines : {erreurs}")

# Test 3 : les membres « Inconnu » utilisés (à mentionner dans la note qualité)
for col in ("cle_joueur", "cle_poste", "cle_temps", "cle_zone"):
    ctrl(f"         actions rattachées à {col} = 0 (Inconnu) : {sum(1 for f in fait_evenement if f[col] == 0)}")

with open(os.path.join(OUT, "controles_etl.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(rapport))

# =============================================================================
# 6. DICTIONNAIRE DES DONNÉES (livrable de passation)
# =============================================================================
DICO = [
    ("dim_match", "cle_match", "Entier", "Clé de substitution (0 = inconnu)", "Générée par l'ETL"),
    ("dim_match", "id_match", "Entier", "Identifiant du match chez StatsBomb (clé naturelle)", "matches.json"),
    ("dim_match", "date / annee", "Date / texte", "Date du match, année", "matches.json"),
    ("dim_match", "competition", "Texte", "Coupe du monde 2022 ou CAN 2023", "Dossier source"),
    ("dim_match", "phase / ordre_phase", "Texte / entier", "Phase en français et son ordre de tri", "matches.json, traduit"),
    ("dim_match", "stade / ville / pays", "Texte", "Lieu du match (pour la carte)", "matches.json + table STADES"),
    ("dim_match", "libelle_match", "Texte", "Ex. : Maroc 1-0 Portugal", "Calculé"),
    ("dim_equipe", "cle_equipe", "Entier", "Clé de substitution", "Générée par l'ETL"),
    ("dim_equipe", "nom_equipe / nom_fr", "Texte", "Nom anglais (source) et français", "matches.json + table EQUIPES"),
    ("dim_equipe", "confederation", "Texte", "CAF, UEFA, CONCACAF", "Table EQUIPES"),
    ("dim_joueur", "cle_joueur / id_joueur / nom_joueur", "Entier / entier / texte", "Clé, identifiant StatsBomb, nom", "events"),
    ("dim_poste", "cle_poste / poste / poste_fr / ligne", "Entier / texte", "Poste occupé lors de l'action et sa ligne", "events + table POSTES"),
    ("dim_temps_jeu", "cle_temps", "Entier", "Clé : une ligne par (période, minute), générée complète", "Générée par l'ETL"),
    ("dim_temps_jeu", "periode / libelle_periode / minute", "Entier / texte / entier", "1-2 temps réglementaire, 3-4 prolongations", "Générée"),
    ("dim_temps_jeu", "tranche_15 / ordre_tranche", "Texte / entier", "Tranche de 15 min, arrêts de jeu isolés", "Générée"),
    ("dim_zone", "cle_zone / zone / tiers / couloir", "Entier / texte", "Terrain découpé en 3 tiers x 3 couloirs", "Générée"),
    ("dim_type_action", "cle_type / type_action / libelle_fr / famille", "Entier / texte", "Type d'action et sa famille", "events + table TYPES"),
    ("fait_evenement", "id_evenement", "Texte", "Identifiant de l'action (dimension dégénérée)", "events"),
    ("fait_evenement", "cle_match … cle_type", "Entier", "Clés étrangères vers les 7 dimensions (cle_adversaire -> dim_equipe)", "ETL"),
    ("fait_evenement", "num_possession", "Entier", "Numéro de la séquence de jeu dans le match (dimension dégénérée)", "events"),
    ("fait_evenement", "x / y", "Décimal (point)", "Position sur le terrain 120 x 80 (vide si inconnue)", "events"),
    ("fait_evenement", "nb_actions", "Entier", "Toujours 1 : sert à compter", "Calculé"),
    ("fait_evenement", "xg", "Décimal (point)", "Probabilité de but du tir ; 0 pour les autres actions", "events (statsbomb_xg)"),
    ("fait_evenement", "but", "Entier 0/1", "1 si tir marqué ou but contre son camp crédité", "Calculé (règles 1 et 2)"),
    ("fait_evenement", "action_reussie", "Entier 0/1", "1 si passe ou dribble réussi", "Calculé"),
    ("fait_match_equipe", "cle_match / cle_equipe / cle_adversaire", "Entier", "Une ligne par équipe et par match", "ETL"),
    ("fait_match_equipe", "domicile", "Entier 0/1", "1 si équipe « à domicile » sur la feuille de match", "matches.json"),
    ("fait_match_equipe", "buts_marques / buts_encaisses", "Entier", "Score officiel", "matches.json"),
    ("fait_match_equipe", "victoire / nul / defaite", "Entier 0/1", "Issue ; un 0-0 gagné aux tirs au but compte comme nul", "Calculé"),
]
with open(os.path.join(OUT, "dictionnaire_donnees.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["table", "colonne", "type", "description", "origine"])
    w.writerows(DICO)
print(f"\nTerminé : 9 tables + dictionnaire_donnees.csv + controles_etl.txt dans {OUT}")
