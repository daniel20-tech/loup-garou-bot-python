from dataclasses import dataclass, field


@dataclass(eq=False)
class Player:
    num: int
    ids: set
    name: str
    dm: object
    role: str | None = None
    alive: bool = True
    love: "Player | None" = None


@dataclass
class NightState:
    cupid: bool = False
    seer: bool = False
    votes: dict[int, int] = field(default_factory=dict)
    witch_open: bool = False
    witch_done: bool = False
    heal: bool = False
    poison: "Player | None" = None
    victim_num: int | None = None


@dataclass
class HunterAction:
    p: Player
    choice: Player | None = None
