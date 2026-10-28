"""Narrateur médiéval : texte généré par Claude, avec textes de secours hors ligne."""
import os
import random

from roles import label

TONES = [
    "sombre et angoissant, comme une veillée où l'on a peur du noir",
    "épique et solennel, façon chanson de geste",
    "ironique et grinçant, avec une pointe d'humour noir",
    "conte populaire raconté au coin du feu",
    "chronique d'un moine copiste inquiet et un peu dépassé",
    "poétique et mélancolique, images de brume, de corbeaux et de lune",
]


def pick_tone() -> str:
    return random.choice(TONES)


EVENT_BRIEF = {
    "intro": "Ouverture de la partie : présente le village, son ambiance, la menace qui rôde (des loups-garous se cachent parmi les habitants) et appelle à la vigilance. Tiens compte du nombre d'habitants (petit hameau, bourg, grand village…).",
    "night": "La nuit tombe sur le village. Décris le couvre-feu, les volets qui se ferment, les bruits de la nuit. Ne dis rien de ce que font les personnages secrets.",
    "dawn": "L'aube se lève. Annonce le résultat de la nuit. Si la liste des morts est vide, raconte une nuit étonnamment paisible (mais garde un doute). Sinon, raconte la découverte de chaque mort avec leur rôle révélé.",
    "vote_start": "Le jour se lève pour le débat : les villageois se réunissent sur la place pour désigner un coupable. Lance les débats, rappelle que le temps presse.",
    "vote_result": "Le village a voté. Si la liste des morts est vide, c'est une égalité : le village n'a pu se décider et personne n'est exécuté. Sinon, raconte l'exécution et révèle le rôle de la personne.",
    "extra_deaths": "Conséquence immédiate de ce qui vient de se passer (tir du Chasseur ou mort de chagrin d'un amoureux). Raconte ces morts supplémentaires et révèle leur rôle.",
    "end": "La partie est terminée. Raconte le dénouement et la victoire du camp gagnant.",
}
CAUSES = {
    "loups": "dévoré par les loups",
    "poison": "empoisonné",
    "vote": "exécuté par le village",
    "chagrin": "mort de chagrin",
    "chasseur": "abattu par le Chasseur",
}
WINNERS = {
    "village": "le village",
    "loups": "les loups-garous",
    "amoureux": "les deux amoureux (un loup et un villageois)",
}


def _alive_names(game) -> list[str]:
    return [p.name for p in game.players if p.alive]


def build_user_message(game, event: str, data: dict) -> str:
    alive = _alive_names(game)
    lines = [
        f"Village : {game.village}",
        f"Nombre de joueurs au départ : {len(game.players)}",
        f"Habitants encore en vie ({len(alive)}) : {', '.join(alive) or 'aucun'}",
        f"Tour de jeu : {game.day_no}",
        f"Événement à raconter : {EVENT_BRIEF[event]}",
    ]
    if "deaths" in data:
        deaths = data["deaths"]
        txt = " ; ".join(f"{d['name']} — {label(d['role'])} — {CAUSES[d['cause']]}" for d in deaths) or "aucun"
        lines.append(f"Morts (nom — rôle révélé — cause) : {txt}")
    if "winner" in data:
        lines.append(f"Camp vainqueur : {WINNERS[data['winner']]}")
    if game.history:
        lines.append("Tes dernières narrations (ne les répète pas, varie les images et les tournures) :")
        lines += [f"- {h[:220]}" for h in game.history[-3:]]
    return "\n".join(lines)


def system_prompt(game) -> str:
    return "\n".join([
        "Tu es le Conteur d'une partie de Loup-Garou jouée sur WhatsApp, dans un village médiéval.",
        f"Ton de cette partie : {game.tone}. Garde ce ton tout au long de la partie.",
        "Règles strictes :",
        "- Écris en français, dans un style médiéval imagé (sans exagérer l'ancien français).",
        "- 2 à 5 phrases, 90 mots maximum. Pas de liste, pas de Markdown, pas de titre, un seul émoji au maximum.",
        "- Utilise exactement les prénoms/pseudos fournis, sans en inventer.",
        "- N'invente aucun mort, aucun rôle, aucune règle. Ne révèle aucune information secrète : seuls les rôles listés dans « Morts » sont publics.",
        "- Ne mentionne ni commandes ni mécanique de jeu. Ne pose pas de question aux joueurs.",
        "Réponds uniquement avec le texte de la narration.",
    ])


_client = None


async def call_claude(system: str, user: str, max_tokens: int = 300) -> str | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    global _client
    if _client is None:
        import anthropic  # importé ici : le bot reste utilisable sans le paquet

        _client = anthropic.AsyncAnthropic(api_key=key, timeout=20.0)
    resp = await _client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text or None


def _names(d) -> str:
    return " et ".join(x["name"] for x in d["deaths"])


FALLBACK = {
    "intro": [
        lambda g, d: f"Les cloches de {g.village} sonnent dans la brume. {len(g.players)} âmes se serrent autour du puits, car on murmure que des loups marchent déguisés en hommes.",
        lambda g, d: f"Au crépuscule, {g.village} referme ses portes. Parmi ses {len(g.players)} habitants, des bêtes affamées guettent leur heure. Que chacun veille sur son voisin.",
    ],
    "night": [
        lambda g, d: "La nuit s'abat, les volets claquent, et quelque part dans les bois, un hurlement répond au vent.",
        lambda g, d: "La lune se voile, les chandelles s'éteignent une à une. Le village retient son souffle.",
        lambda g, d: "Les ombres s'allongent sur les chaumières ; tout le monde dort, ou fait semblant.",
    ],
    "dawn": [
        lambda g, d: f"L'aube blafarde révèle l'horreur : {_names(d)} ne verra plus jamais le soleil." if d["deaths"] else "Le coq chante, personne ne manque à l'appel. Les loups auraient-ils eu pitié ? Nul n'y croit.",
        lambda g, d: f"Un cri déchire le matin : {_names(d)} gît sans vie, victime de la nuit." if d["deaths"] else "Aucune trace de sang au lever du jour. Étrange silence… qui inquiète plus qu'un cri.",
    ],
    "vote_start": [
        lambda g, d: "Le village se rassemble sur la place, les regards se croisent, lourds de soupçons. Qui cache des crocs sous son sourire ?",
        lambda g, d: "Le conseil des villageois s'ouvre sous le vieux chêne. Les accusations vont fuser ; il faut trancher avant la nuit.",
    ],
    "vote_result": [
        lambda g, d: f"La foule a tranché : {_names(d)} est conduit au bûcher. Justice est faite… ou erreur fatale." if d["deaths"] else "Les voix se divisent, le village hésite, et la foule se disperse sans victime. Les loups sourient peut-être.",
        lambda g, d: f"Le verdict tombe, sans appel : {_names(d)} quitte la place pour la dernière fois." if d["deaths"] else "Aucune majorité ne se dégage ; la nuit tombera sans exécution.",
    ],
    "extra_deaths": [
        lambda g, d: f"Le drame ne s'arrête pas : {_names(d)} s'effondre à son tour.",
        lambda g, d: f"Dans la panique, {_names(d)} rend l'âme à son tour.",
    ],
    "end": [
        lambda g, d: {
            "village": f"Les derniers loups sont tombés. {g.village} peut enfin rallumer ses chandelles et respirer.",
            "loups": f"Plus personne pour s'opposer aux crocs. {g.village} appartient désormais à la meute.",
            "amoureux": f"Deux cœurs ont survécu à tous les autres. {g.village} se tait devant cet amour maudit.",
        }[d["winner"]],
    ],
}


async def narrate(game, event: str, data: dict | None = None) -> str:
    data = data or {}
    text = None
    try:
        text = await call_claude(system_prompt(game), build_user_message(game, event, data))
    except Exception as e:  # réseau, quota, clé invalide…
        print(f"[narrateur] repli sur texte local : {e}")
    if not text:
        text = random.choice(FALLBACK[event])(game, data)
    game.history.append(text)
    return text


PREFIX = ["Saint-", "Val", "Bois", "Mont", "Châtel", "Fontaine", "Roche", "Brume", "Corbeau", "Noire"]
SUFFIX = ["-les-Loups", "combe", "lieu", "fort", "-sur-Brume", "mont", "bois", "-la-Nuit", "ville", "creux"]


async def invent_village_name(game) -> str:
    try:
        t = await call_claude(
            "Tu inventes des noms de villages médiévaux français, évocateurs et inquiétants.",
            f"Invente UN seul nom de village (2 à 4 mots, sans guillemets, sans explication). Il doit être différent de : Thiercelieux, Saint-Loup. Ton de la partie : {game.tone}.",
            30,
        )
        clean = (t or "").split("\n")[0].replace('"', "").replace("«", "").replace("»", "").strip(" .")
        if clean and len(clean) <= 40:
            return clean
    except Exception as e:
        print(f"[narrateur] nom de village local : {e}")
    return random.choice(PREFIX) + random.choice(SUFFIX)
