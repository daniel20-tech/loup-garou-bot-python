import random

ROLES = {
    "loup": ("Loup-Garou", "🐺"),
    "villageois": ("Simple Villageois", "🧑‍🌾"),
    "voyante": ("Voyante", "🔮"),
    "sorciere": ("Sorcière", "🧪"),
    "chasseur": ("Chasseur", "🏹"),
    "cupidon": ("Cupidon", "💘"),
}

ROLE_BRIEF = {
    "loup": "Chaque nuit, concerte-toi avec les autres loups pour dévorer un villageois : /devorer N. Le jour, joue l'innocent et évite d'être démasqué.",
    "villageois": "Tu n'as aucun pouvoir : observe, argumente et vote pour démasquer les loups pendant le débat.",
    "voyante": "Chaque nuit, tu peux sonder un joueur et découvrir son rôle : /voir N. Aide le village, mais reste discrète.",
    "sorciere": "Tu as une potion de guérison et une potion de poison, chacune utilisable une seule fois dans la partie. La nuit, je te dirai qui est la victime des loups : /sauver, /empoisonner N ou /rien.",
    "chasseur": "Si tu meurs, tu emportes immédiatement quelqu'un avec toi : /tirer N.",
    "cupidon": "La première nuit, tu lies deux joueurs par l'amour : /aimer N N (tu peux te choisir). Si l'un meurt, l'autre meurt de chagrin.",
}


def label(role: str) -> str:
    name, emoji = ROLES[role]
    return f"{emoji} {name}"


def build_role_list(n: int) -> list[str]:
    """Distribution simplifiée selon le nombre de joueurs."""
    wolves = 3 if n >= 12 else 2 if n >= 8 else 1
    roles = ["loup"] * wolves + ["voyante"]
    if n >= 6:
        roles.append("sorciere")
    if n >= 7:
        roles.append("chasseur")
    if n >= 8:
        roles.append("cupidon")
    roles += ["villageois"] * (n - len(roles))
    return roles


def composition_text(roles: list[str]) -> str:
    counts: dict[str, int] = {}
    for r in roles:
        counts[r] = counts.get(r, 0) + 1
    return "\n".join(f"{c} × {label(r)}" for r, c in counts.items())


def shuffled(items):
    items = list(items)
    random.shuffle(items)
    return items
