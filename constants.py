MAX_PLAYERS = 18


def _secs(name: str, default: float) -> float:
    import os

    return float(os.getenv(name) or default)


def T() -> dict:
    return {
        "night": _secs("NIGHT_SECONDS", 90),
        "witch": _secs("WITCH_SECONDS", 60),
        "hunter": _secs("HUNTER_SECONDS", 45),
        "day": _secs("DAY_SECONDS", 240),
    }


def min_players() -> int:
    import os

    return int(os.getenv("MIN_PLAYERS") or 5)


CAUSE = {
    "loups": ("🐺", "a été dévoré(e) cette nuit"),
    "poison": ("🧪", "a succombé à un poison"),
    "vote": ("⚖️", "a été exécuté(e) par le village"),
    "chagrin": ("💔", "est mort(e) de chagrin"),
    "chasseur": ("🏹", "a été abattu(e) par le Chasseur"),
}
