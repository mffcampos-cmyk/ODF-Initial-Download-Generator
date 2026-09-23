"""Realistic, culture-aware person names and WNPA name-field derivation.

Replaces the previous random-letter name generator. Each NOC maps to a name
pool; unknown NOCs get a deterministic pool so output stays stable per seed.
Derived fields follow the ODF data dictionary and the conventions observed in
the real-life SYOG2026 feed:

- PrintName        = "FAMILY Given"
- PrintInitialName = "FAMILY IJ"      (one initial per given-name part, no dots)
- TVName           = "Given FAMILY"
- TVInitialName    = "I.J. FAMILY"    (one initial per part, each with a dot)
- Passport names   = uppercase, accents stripped
- PSCBShortName    = PrintName if <=15 chars, else "FAMILY I.", else FAMILY,
                     else truncated family + "."  (rule observed in real feed)
"""
from __future__ import annotations

import random
import re
import unicodedata

POOLS: dict[str, dict[str, list[str]]] = {
    "english":  {"m": ["James", "Oliver", "Ethan", "Liam", "Noah", "Jack", "Harry", "Lucas", "Mason", "Dylan", "Owen", "Caleb"],
                 "f": ["Emily", "Charlotte", "Amelia", "Sophie", "Grace", "Chloe", "Ella", "Ruby", "Isla", "Freya", "Holly", "Megan"],
                 "s": ["Smith", "Johnson", "Brown", "Taylor", "Wilson", "Clarke", "Walker", "Robinson", "Wright", "Mitchell", "Carter", "Bennett", "Foster", "Hayes", "Bishop"]},
    "spanish":  {"m": ["Diego", "Mateo", "Santiago", "Sebastián", "Alejandro", "Andrés", "Javier", "Emilio", "Tomás", "Rafael", "Iker", "Marco"],
                 "f": ["Valentina", "Camila", "Sofía", "Isabella", "Lucía", "Mariana", "Daniela", "Gabriela", "Renata", "Ximena", "Paula", "Elena"],
                 "s": ["García", "Rodríguez", "Martínez", "Hernández", "López", "Pérez", "Torres", "Ramírez", "Flores", "Vargas", "Castillo", "Morales", "Rojas", "Mendoza", "Salazar"]},
    "french":   {"m": ["Lucas", "Hugo", "Louis", "Théo", "Antoine", "Baptiste", "Maxime", "Romain", "Quentin", "Julien", "Nolan", "Mathis"],
                 "f": ["Léa", "Manon", "Camille", "Chloé", "Inès", "Jade", "Louise", "Zoé", "Margaux", "Clara", "Océane", "Justine"],
                 "s": ["Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Lefebvre", "Roux", "Fournier", "Girard", "Bonnet", "Dupont", "Fontaine", "Chevalier", "Renard", "Marchand"]},
    "italian":  {"m": ["Lorenzo", "Matteo", "Alessandro", "Gabriele", "Riccardo", "Tommaso", "Federico", "Davide", "Simone", "Pietro", "Nicolò", "Edoardo"],
                 "f": ["Giulia", "Sofia", "Martina", "Chiara", "Alessia", "Beatrice", "Camilla", "Aurora", "Elisa", "Francesca", "Vittoria", "Ludovica"],
                 "s": ["Rossi", "Ferrari", "Bianchi", "Romano", "Conti", "Ricci", "Marino", "Greco", "Gallo", "Costa", "Fontana", "Moretti", "Barbieri", "Rinaldi", "Colombo"]},
    "german":   {"m": ["Lukas", "Finn", "Jonas", "Leon", "Elias", "Paul", "Felix", "Maximilian", "Moritz", "Niklas", "Tim", "Jannik"],
                 "f": ["Mia", "Emma", "Hannah", "Lena", "Leonie", "Anna", "Lea", "Marie", "Johanna", "Laura", "Nele", "Sophie"],
                 "s": ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Hoffmann", "Schäfer", "Koch", "Richter", "Klein", "Wolf", "Neumann"]},
    "nordic":   {"m": ["Emil", "Oskar", "Anton", "Viktor", "Elias", "Axel", "Magnus", "Henrik", "Sindre", "Espen", "Mikkel", "Aksel"],
                 "f": ["Ingrid", "Astrid", "Freja", "Maja", "Saga", "Elsa", "Nora", "Signe", "Thea", "Hedda", "Amanda", "Linnea"],
                 "s": ["Andersson", "Johansson", "Karlsson", "Nilsson", "Eriksson", "Larsson", "Olsen", "Hansen", "Berg", "Lund", "Dahl", "Solberg", "Nygaard", "Holm", "Lindqvist"]},
    "slavic":   {"m": ["Luka", "Ivan", "Marko", "Nikola", "Matej", "Petar", "Filip", "Jan", "Tomáš", "Jakub", "Ondřej", "Vojtěch"],
                 "f": ["Ana", "Petra", "Katarina", "Marija", "Tereza", "Eliška", "Adéla", "Veronika", "Nikolina", "Dora", "Lucie", "Karolína"],
                 "s": ["Novák", "Svoboda", "Dvořák", "Černý", "Procházka", "Horvat", "Kovačević", "Babić", "Jurić", "Vuković", "Novotný", "Marek", "Pavlović", "Zeman", "Krejčí"]},
    "korean":   {"m": ["Minjun", "Seojun", "Dohyun", "Jihoo", "Junseo", "Hyunwoo", "Woojin", "Sungmin", "Taeyang", "Jaehyun", "Yejun", "Siwoo"],
                 "f": ["Seoyeon", "Jiwoo", "Minseo", "Chaewon", "Yuna", "Haeun", "Soomin", "Dahyun", "Eunji", "Hyejin", "Nayeon", "Jimin"],
                 "s": ["Kim", "Lee", "Park", "Choi", "Jung", "Kang", "Cho", "Yoon", "Jang", "Lim", "Han", "Shin", "Oh", "Seo", "Kwon"]},
    "seasian":  {"m": ["Somchai", "Anong", "Phanit", "Bounmy", "Khamla", "Sengphet", "Vilay", "Rithy", "Sovann", "Dara", "Putra", "Agus"],
                 "f": ["Malee", "Chanthavy", "Ketsana", "Soudalath", "Noy", "Vanhnaly", "Sreyneang", "Bopha", "Channary", "Dewi", "Sari", "Putri"],
                 "s": ["Vongsa", "Phommachanh", "Sisouphanh", "Keomany", "Chanthavong", "Sok", "Chea", "Seng", "Wijaya", "Santoso", "Halim", "Susanto", "Rattanavong", "Inthavong", "Sayavong"]},
    "arabic":   {"m": ["Omar", "Youssef", "Karim", "Tariq", "Hamza", "Rashid", "Faisal", "Nasser", "Sami", "Ziad", "Khalil", "Majid"],
                 "f": ["Layla", "Amira", "Yasmin", "Nour", "Salma", "Rania", "Dana", "Hala", "Farah", "Lina", "Maha", "Reem"],
                 "s": ["Al-Sayed", "Haddad", "Nasser", "Khalil", "Mansour", "Awad", "Hamdan", "Saleh", "Farah", "Qasem", "Zahran", "Barakat", "Sabbagh", "Attar", "Karam"]},
    "african":  {"m": ["Kwame", "Kofi", "Sekou", "Mamadou", "Ousmane", "Ibrahima", "Abdou", "Cheikh", "Moussa", "Tendai", "Thabo", "Juma"],
                 "f": ["Ama", "Abena", "Aissatou", "Fatou", "Mariama", "Aminata", "Khady", "Ndeye", "Awa", "Zanele", "Naledi", "Amara"],
                 "s": ["Mensah", "Osei", "Boateng", "Diallo", "Ndiaye", "Diop", "Sow", "Traoré", "Keita", "Nkosi", "Moyo", "Banda", "Sarr", "Fall", "Cissé"]},
    "ethiopic": {"m": ["Abebe", "Tesfaye", "Dawit", "Yonas", "Bekele", "Haile", "Girma", "Solomon", "Elias", "Fikru", "Mekonnen", "Tadesse"],
                 "f": ["Hana", "Selam", "Meron", "Tigist", "Bethlehem", "Rahel", "Sara", "Mahlet", "Lily", "Eden", "Hiwot", "Marta"],
                 "s": ["Abebe", "Bekele", "Tesfaye", "Haile", "Girma", "Kebede", "Alemu", "Desta", "Worku", "Assefa", "Mengistu", "Gebre", "Tadesse", "Negash", "Wolde"]},
    "turkic":   {"m": ["Emir", "Aziz", "Rustam", "Timur", "Nursultan", "Alisher", "Bekzat", "Sanjar", "Dovlet", "Kanat", "Erlan", "Maksat"],
                 "f": ["Aigerim", "Dinara", "Madina", "Aliya", "Zarina", "Gulnara", "Aisha", "Kamila", "Saltanat", "Jamilya", "Nazgul", "Altynay"],
                 "s": ["Abdullaev", "Rakhimov", "Nazarov", "Yusupov", "Karimov", "Bekov", "Toshev", "Saidov", "Umarov", "Ergashev", "Mamedov", "Annayev", "Orazov", "Berdiev", "Islamov"]},
    "southasian": {"m": ["Arif", "Rahim", "Kamal", "Farid", "Jamal", "Sajid", "Imran", "Nadir", "Rashed", "Tanvir", "Shakib", "Habib"],
                 "f": ["Nusrat", "Farzana", "Sadia", "Tasnim", "Rima", "Sharmin", "Nabila", "Farah", "Sumaiya", "Lamia", "Ishrat", "Mahia"],
                 "s": ["Rahman", "Ahmed", "Hossain", "Islam", "Chowdhury", "Khan", "Akter", "Sarkar", "Uddin", "Sheikh", "Mia", "Bhuiyan", "Karim", "Mollah", "Haque"]},
    "caribbean": {"m": ["Andre", "Marlon", "Kevon", "Jamal", "Dwayne", "Shaquille", "Rondell", "Akeem", "Tyrese", "Devon", "Kerron", "Jelani"],
                 "f": ["Shanice", "Keisha", "Aaliyah", "Tamara", "Latoya", "Shakira", "Renee", "Alicia", "Danielle", "Kimora", "Jada", "Nakita"],
                 "s": ["Williams", "Joseph", "Charles", "Baptiste", "Francis", "Alexander", "Phillip", "Toussaint", "Regis", "Duncan", "Cummings", "Springer", "Greaves", "Hackett", "Providence"]},
}

NOC_POOL: dict[str, str] = {
    "ASA": "english", "BAH": "caribbean", "BDI": "african", "CRC": "spanish", "CZE": "slavic",
    "EGY": "arabic", "FRG": "german", "GHA": "african", "ITA": "italian", "JOR": "arabic",
    "KOR": "korean", "LAO": "seasian", "PLE": "arabic", "PUR": "spanish", "SWE": "nordic",
    "URS": "slavic", "USA": "english", "BAR": "caribbean", "BEL": "french", "CAM": "seasian",
    "COD": "african", "CRO": "slavic", "ETH": "ethiopic", "GUM": "english", "INA": "seasian",
    "ISL": "nordic", "LCA": "caribbean", "MOZ": "african", "NCA": "spanish", "NOR": "nordic",
    "OMA": "arabic", "TKM": "turkic", "ALB": "slavic", "AND": "spanish", "AZE": "turkic",
    "BAN": "southasian", "BEN": "african", "CHI": "spanish", "CIV": "african", "COL": "spanish",
    "HUN": "slavic", "IRL": "english", "ISV": "caribbean", "KGZ": "turkic", "KSA": "arabic",
    "SEN": "african", "SOM": "african",
}

_POOL_KEYS = sorted(POOLS)


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def pool_for(org: str) -> dict[str, list[str]]:
    key = NOC_POOL.get(org)
    if key is None:
        # deterministic pool for NOCs without an explicit mapping
        key = _POOL_KEYS[sum(ord(c) for c in org) % len(_POOL_KEYS)]
    return POOLS[key]


def person_name(rng: random.Random, org: str, gender: str,
                used: set[str] | None = None) -> tuple[str, str]:
    """Return (given_name, family_name) plausible for the NOC. ``used`` (if
    given) tracks "org|family|given" keys to avoid duplicates per delegation."""
    pool = pool_for(org)
    given_pool = pool["m"] if gender == "M" else pool["f"]
    for _ in range(60):
        given = rng.choice(given_pool)
        family = rng.choice(pool["s"])
        key = f"{org}|{family}|{given}"
        if used is None or key not in used:
            if used is not None:
                used.add(key)
            return given, family
    return rng.choice(given_pool), rng.choice(pool["s"])


def given_initials(given: str) -> list[str]:
    """One initial per part of the given name, parts split on spaces and
    hyphens: "Maria Luisa" -> ["M", "L"], "Anne-Marie" -> ["A", "M"]
    (ODF Name Language Guidelines 5.2 / 5.5; the real SYOG26 feed does the
    same)."""
    parts = re.split(r"[\s-]+", strip_accents(given).strip())
    return [p[0].upper() for p in parts if p]


def name_fields(given: str, family: str) -> dict[str, str]:
    """Derive all ODF name attributes from a given/family pair.

    Widths are not applied here: ``lengths.clamp`` cuts every attribute to its
    GEN DD S(n) where it is serialised, as the real feed does."""
    fam_upper = strip_accents(family).upper()
    initials = given_initials(given)
    initial = initials[0] if initials else ""
    print_name = f"{fam_upper} {given}"
    if len(print_name) <= 15:
        pscb_short = print_name
    elif len(f"{fam_upper} {initial}.") <= 15:
        pscb_short = f"{fam_upper} {initial}."
    elif len(fam_upper) <= 15:
        pscb_short = fam_upper
    else:
        pscb_short = fam_upper[:14] + "."
    return {
        "GivenName": given,
        "FamilyName": family,
        "PassportGivenName": strip_accents(given).upper(),
        "PassportFamilyName": fam_upper,
        "PrintName": print_name,
        "PrintInitialName": f"{fam_upper} {''.join(initials)}",
        "TVName": f"{given} {fam_upper}",
        "TVInitialName": f"{''.join(i + '.' for i in initials)} {fam_upper}",
        "TVFamilyName": fam_upper,
        "PSCBName": print_name,
        "PSCBShortName": pscb_short,
        "PSCBLongName": print_name,
    }
