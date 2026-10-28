"""Simulation hors ligne : parties complètes avec joueurs aléatoires (sans WhatsApp)."""
import asyncio
import os
import random

os.environ.update(NIGHT_SECONDS="0.4", WITCH_SECONDS="0.4", HUNTER_SECONDS="0.4", DAY_SECONDS="0.6")
os.environ.pop("ANTHROPIC_API_KEY", None)

from game import Game  # noqa: E402


async def play_one(n: int) -> int:
    out: list[tuple[str, str]] = []
    ended = asyncio.Event()

    async def send(dest, text):
        out.append((dest, text))

    g = Game("grp", ["p1"], send, on_end=lambda _g: ended.set())
    for i in range(1, n + 1):
        g.add_player([f"p{i}"], f"Joueur{i}", f"dm{i}")

    async def driver():
        while not ended.is_set():
            al = g.alive()
            for p in al:
                others = [x for x in al if x is not p and x.role != "loup"]
                if g.state == "night":
                    if p.role == "voyante":
                        await g.handle_private(p, "voir", [str(random.choice([x for x in al if x is not p]).num)])
                    if p.role == "loup" and others:
                        await g.handle_private(p, "devorer", [str(random.choice(others).num)])
                    if p.role == "cupidon":
                        await g.handle_private(p, "aimer", [str(random.choice(al).num), str(random.choice(al).num)])
                    if p.role == "sorciere" and random.random() < 0.5:
                        await g.handle_private(p, random.choice(["sauver", "empoisonner"]), [str(random.choice(al).num)])
                if g.state == "day":
                    await g.handle_vote(p, str(random.choice([x for x in al if x is not p]).num))
            if g.hunter:
                await g.handle_private(g.hunter.p, "tirer", [str(random.choice(g.alive()).num)])
            await asyncio.sleep(0.08)

    g.start()
    d = asyncio.create_task(driver())
    await asyncio.wait_for(ended.wait(), 60)
    d.cancel()
    last = [t for dest, t in out if dest == "grp"][-1]
    assert "Les rôles étaient" in last, "La partie ne se termine pas proprement"
    return len(out)


async def main():
    for n in (5, 6, 7, 8, 9, 12, 18):
        print(f"Partie à {n} joueurs OK ({await play_one(n)} messages)")


asyncio.run(main())
