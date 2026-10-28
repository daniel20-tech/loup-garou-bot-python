"""Moteur de jeu Loup-Garou : indépendant de WhatsApp (testable hors ligne).

Il ne connaît qu'une fonction `send(destinataire, texte)` fournie par l'extérieur.
"""
import asyncio
import random
import traceback
from collections import Counter

from constants import CAUSE, MAX_PLAYERS, T, min_players
from models import HunterAction, NightState, Player
from narrator import invent_village_name, narrate, pick_tone
from roles import ROLE_BRIEF, ROLES, build_role_list, composition_text, label, shuffled


def death_lines(deaths) -> str:
    return "\n".join(f"{CAUSE[d['cause']][0]} *{d['name']}* {CAUSE[d['cause']][1]} — c'était {label(d['role'])}" for d in deaths)


class Game:
    def __init__(self, group, creator_ids, send, on_end=None):
        self.group = group
        self.creator_ids = set(creator_ids)
        self.send = send
        self.on_end = on_end or (lambda g: None)
        self.state = "lobby"  # lobby | starting | night | resolving | day | over
        self.players: list[Player] = []
        self.village: str | None = None
        self.tone = pick_tone()
        self.day_no = 0
        self.history: list[str] = []
        self.potions = {"heal": True, "poison": True}
        self.lovers: tuple[Player, Player] | None = None
        self.ns: NightState | None = None
        self.votes: dict[int, int] = {}
        self.hunter: HunterAction | None = None
        self.cancelled = False
        self.task = None
        self._ev = asyncio.Event()

    # ---------- utilitaires ----------
    async def say(self, text):
        try:
            await self.send(self.group, text)
        except Exception as e:
            print("say:", e)

    async def dm(self, p: Player, text) -> bool:
        try:
            await self.send(p.dm, text)
            return True
        except Exception as e:
            print("DM impossible vers", p.name, e)
            await self.say(f"⚠️ Je n'arrive pas à écrire en privé à *{p.name}*. Envoie-moi un message privé (ex. /aide) pour ouvrir la discussion.")
            return False

    def is_creator(self, ids) -> bool:
        return any(i in self.creator_ids for i in ids)

    def find_player(self, ids) -> Player | None:
        return next((p for p in self.players if any(i in p.ids for i in ids)), None)

    def alive(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def by_num(self, n) -> Player | None:
        return next((p for p in self.players if p.num == n), None)

    def fmt(self, ps) -> str:
        return "\n".join(f"{p.num}. {p.name}" for p in ps)

    def target(self, arg, pool) -> Player | None:
        if not arg:
            return None
        if arg.isdigit():
            return next((p for p in pool if p.num == int(arg)), None)
        m = [p for p in pool if p.name.lower().startswith(arg.lower())]
        return m[0] if len(m) == 1 else None

    async def wait_until(self, cond, seconds: float) -> str:
        loop = asyncio.get_running_loop()
        end = loop.time() + seconds
        while not (cond() or self.cancelled):
            remaining = end - loop.time()
            if remaining <= 0:
                return "timeout"
            self._ev.clear()
            try:
                await asyncio.wait_for(self._ev.wait(), remaining)
            except asyncio.TimeoutError:
                return "timeout"
        return "done"

    def poke(self):
        self._ev.set()

    # ---------- salon d'attente ----------
    def add_player(self, ids, name, dm):
        if self.state != "lobby":
            return False, "La partie a déjà commencé."
        if self.find_player(ids):
            return False, "Tu es déjà inscrit(e)."
        if len(self.players) >= MAX_PLAYERS:
            return False, f"Le village est plein ({MAX_PLAYERS} joueurs max)."
        base = ((name or "Joueur").strip()[:20]) or "Joueur"
        n, k = base, 2
        while any(p.name.lower() == n.lower() for p in self.players):
            n, k = f"{base} {k}", k + 1
        self.players.append(Player(len(self.players) + 1, set(ids), n, dm))
        c = len(self.players)
        return True, f"✅ *{n}* rejoint le village ! ({c} joueur{'s' if c > 1 else ''})"

    def remove_player(self, ids):
        if self.state != "lobby":
            return False, "Trop tard, la partie a commencé."
        p = self.find_player(ids)
        if not p:
            return False, "Tu n'es pas inscrit(e)."
        self.players.remove(p)
        for i, x in enumerate(self.players):
            x.num = i + 1
        return True, f"👋 *{p.name}* quitte le village."

    def lobby_text(self) -> str:
        v = self.village or "(à nommer avec /village NOM)"
        return f"🏰 *Village : {v}*\n👥 Joueurs ({len(self.players)}) :\n{self.fmt(self.players) if self.players else '—'}"

    def can_start(self) -> str | None:
        if len(self.players) < min_players():
            return f"Il faut au moins {min_players()} joueurs ({len(self.players)} inscrits)."
        return None

    # ---------- déroulement général ----------
    async def run(self):
        try:
            await self.intro()
            while not self.cancelled:
                await self.play_night()
                if self.cancelled:
                    break
                w = self.check_win()
                if w:
                    await self.end(w)
                    break
                await self.play_day()
                if self.cancelled:
                    break
                w = self.check_win()
                if w:
                    await self.end(w)
                    break
        except Exception:
            traceback.print_exc()
            await self.say("⚠️ Une erreur est survenue, la partie est interrompue. Relance avec /nouvelle.")
        finally:
            self.state = "over"
            self.on_end(self)

    def start(self):
        self.state = "starting"
        self.task = asyncio.create_task(self.run())

    def stop(self):
        self.cancelled = True
        self.poke()

    async def intro(self):
        self.state = "night"
        if not self.village:
            self.village = await invent_village_name(self)
        self.players = shuffled(self.players)
        for i, p in enumerate(self.players):
            p.num = i + 1
        roles = shuffled(build_role_list(len(self.players)))
        for p, r in zip(self.players, roles):
            p.role = r

        story = await narrate(self, "intro")
        await self.say(
            f"🏰 *{self.village}*\n\n{story}\n\n*Composition du village :*\n{composition_text(roles)}"
            f"\n\n*Habitants :*\n{self.fmt(self.players)}\n\n📩 Je vous envoie votre rôle en privé. Besoin d'aide ? /tuto"
        )
        wolves = [p for p in self.players if p.role == "loup"]
        for p in self.players:
            name, emoji = ROLES[p.role]
            msg = f"{emoji} *Tu es {name}* au village de {self.village}.\n\n{ROLE_BRIEF[p.role]}\n\nTu es le joueur n°{p.num}."
            if p.role == "loup" and len(wolves) > 1:
                msg += "\n\n🐺 Tes complices : " + ", ".join(w.name for w in wolves if w is not p)
            await self.dm(p, msg)

    # ---------- la nuit ----------
    async def play_night(self):
        self.state = "night"
        self.day_no += 1
        n = self.ns = NightState()
        await self.say(f"🌙 *Nuit n°{self.day_no}*\n\n{await narrate(self, 'night')}")

        al = self.alive()
        cupid = next((p for p in al if p.role == "cupidon"), None) if self.day_no == 1 else None
        seer = next((p for p in al if p.role == "voyante"), None)
        wolves = [p for p in al if p.role == "loup"]

        if cupid:
            await self.dm(cupid, f"💘 Choisis les deux amoureux (tu peux te choisir) : */aimer N N*\n{self.fmt(al)}")
        if seer:
            await self.dm(seer, f"🔮 Qui veux-tu sonder ? */voir N*\n{self.fmt([p for p in al if p is not seer])}")
        for w in wolves:
            await self.dm(w, f"🐺 Qui dévorer cette nuit ? Mettez-vous d'accord : */devorer N*\n{self.fmt([p for p in al if p.role != 'loup'])}")

        def wolves_done():
            return not wolves or (all(w.num in n.votes for w in wolves) and len(set(n.votes.values())) == 1)

        await self.wait_until(lambda: (not cupid or n.cupid) and (not seer or n.seer) and wolves_done(), T()["night"])
        if self.cancelled:
            return

        if cupid and not n.cupid:
            a, b = random.sample(al, 2)
            await self.set_lovers(a, b)

        victim = None
        if n.votes:
            tally = Counter(n.votes.values())
            top = max(tally.values())
            victim = self.by_num(random.choice([k for k, c in tally.items() if c == top]))
        n.victim_num = victim.num if victim else None

        witch = next((p for p in self.alive() if p.role == "sorciere"), None)
        if witch and (self.potions["heal"] or self.potions["poison"]):
            n.witch_open = True
            msg = "🧪 *Sorcière, à toi de jouer.*\n"
            msg += f"Les loups ont attaqué *{victim.name}* cette nuit.\n" if victim else "Les loups n'ont tué personne cette nuit.\n"
            restantes = []
            if self.potions["heal"]:
                restantes.append("💚 guérison")
            if self.potions["poison"]:
                restantes.append("☠️ poison")
            msg += f"Potions restantes : {' '.join(restantes)}\n"
            if self.potions["heal"] and victim:
                msg += "• /sauver — ressusciter la victime\n"
            if self.potions["poison"]:
                msg += f"• /empoisonner N — éliminer quelqu'un\n{self.fmt([p for p in self.alive() if p is not witch])}\n"
            msg += "• /rien — ne rien faire / valider"
            await self.dm(witch, msg)
            await self.wait_until(lambda: n.witch_done, T()["witch"])
            n.witch_open = False
            if self.cancelled:
                return

        deaths = []
        if victim and not n.heal:
            deaths.append({"p": victim, "cause": "loups"})
        if n.poison and not any(d["p"] is n.poison for d in deaths):
            deaths.append({"p": n.poison, "cause": "poison"})

        self.state = "resolving"
        await self.say(f"☀️ *Aube du jour n°{self.day_no}*")
        await self.resolve_deaths(deaths, "dawn")

    async def set_lovers(self, a: Player, b: Player):
        a.love, b.love = b, a
        self.lovers = (a, b)
        for x, y in ((a, b), (b, a)):
            await self.dm(x, f"💘 Tu es amoureux(se) de *{y.name}* ! Si l'un de vous meurt, l'autre meurt de chagrin. Ne votez jamais l'un contre l'autre.")

    # ---------- morts en chaîne ----------
    def apply_deaths(self, batch):
        announced, hunters = [], []
        queue = list(batch)
        while queue:
            item = queue.pop(0)
            p = item["p"]
            if not p.alive:
                continue
            p.alive = False
            announced.append({"name": p.name, "role": p.role, "cause": item["cause"]})
            if p.love and p.love.alive:
                queue.append({"p": p.love, "cause": "chagrin"})
            if p.role == "chasseur":
                hunters.append(p)
        return announced, hunters

    async def resolve_deaths(self, initial, event):
        batch = [{"p": d["p"], "cause": d["cause"]} for d in initial]
        first = True
        while True:
            announced, hunters = self.apply_deaths(batch)
            if announced or first:
                story = await narrate(self, event if first else "extra_deaths", {"deaths": announced})
                await self.say(story + (f"\n\n{death_lines(announced)}" if announced else ""))
            first = False
            batch = []
            for h in hunters:
                t = await self.ask_hunter(h)
                if t:
                    batch.append({"p": t, "cause": "chasseur"})
            if not batch or self.cancelled:
                break

    async def ask_hunter(self, h: Player) -> Player | None:
        targets = self.alive()
        if not targets:
            return None
        await self.say(f"🏹 *{h.name}* était le Chasseur ! Il a {round(T()['hunter'])} secondes pour tirer sa dernière balle…")
        self.hunter = HunterAction(p=h, choice=None)
        await self.dm(h, f"🏹 Tu es mort(e)… mais tu peux tirer une dernière fois : */tirer N*\n{self.fmt(targets)}")
        await self.wait_until(lambda: self.hunter and self.hunter.choice is not None, T()["hunter"])
        if not self.hunter:
            c = random.choice(self.alive())
            return c
        c = self.hunter.choice if self.hunter.choice and self.hunter.choice.alive else random.choice(self.alive())
        self.hunter = None
        return c

    # ---------- le jour ----------
    async def play_day(self):
        self.state = "day"
        self.votes = {}
        al = self.alive()
        story = await narrate(self, "vote_start")
        minutes = round(T()["day"] / 60, 1)
        await self.say(
            f"🗳️ *Débat et vote*\n\n{story}\n\n*Habitants en vie :*\n{self.fmt(al)}\n\n"
            f"Votez avec */vote N* (vous pouvez changer d'avis). Le vote se clôt quand tout le monde a voté ou à la fin du temps imparti ({minutes} min)."
        )

        async def reminder():
            await asyncio.sleep(max(0, T()["day"] - 60))
            await self.say("⏳ Plus qu'une minute avant la clôture du vote !")

        rem = asyncio.create_task(reminder())
        await self.wait_until(lambda: all(p.num in self.votes for p in al), T()["day"])
        rem.cancel()
        if self.cancelled:
            return

        tally = Counter(self.votes.values())
        eliminated = None
        if tally:
            top = max(tally.values())
            leaders = [k for k, c in tally.items() if c == top]
            if len(leaders) == 1:
                eliminated = self.by_num(leaders[0])
        recap = " · ".join(f"{self.by_num(k).name} : {c}" for k, c in tally.most_common()) or "aucun vote"
        self.state = "resolving"
        await self.say(f"📊 Résultat du vote — {recap}")
        await self.resolve_deaths([{"p": eliminated, "cause": "vote"}] if eliminated else [], "vote_result")

    def check_win(self) -> str | None:
        al = self.alive()
        wolves = [p for p in al if p.role == "loup"]
        others = [p for p in al if p.role != "loup"]
        if self.lovers and len(al) == 2 and all(p in self.lovers for p in al) and len(wolves) == 1:
            return "amoureux"
        if not wolves:
            return "village"
        if not others:
            return "loups"
        return None

    async def end(self, winner: str):
        self.state = "over"
        story = await narrate(self, "end", {"winner": winner})
        title = {"village": "🏆 Victoire du *village* !", "loups": "🐺 Victoire des *Loups-Garous* !", "amoureux": "💘 Victoire des *Amoureux* !"}[winner]
        reveal = "\n".join(f"{'✅' if p.alive else '💀'} {p.name} — {label(p.role)}{' 💘' if p.love else ''}" for p in self.players)
        await self.say(f"{story}\n\n{title}\n\n*Les rôles étaient :*\n{reveal}\n\nPour rejouer : /nouvelle")

    # ---------- commandes en jeu ----------
    async def handle_vote(self, p: Player | None, arg: str):
        if self.state != "day":
            return await self.say("🗳️ Ce n'est pas le moment de voter.")
        if not p or not p.alive:
            return await self.say("💀 Seuls les vivants peuvent voter.")
        t = self.target(arg, self.alive())
        if not t:
            return await self.say("❓ Cible invalide. Utilise /vote N (numéro de la liste).")
        if t is p:
            return await self.say("🙃 On ne vote pas contre soi-même.")
        if p.love is t:
            return await self.say("💘 Tu ne peux pas voter contre ton amoureux(se).")
        self.votes[p.num] = t.num
        await self.say(f"🗳️ *{p.name}* a voté ({len(self.votes)}/{len(self.alive())} votes).")
        self.poke()

    async def handle_private(self, p: Player, cmd: str, args: list[str]):
        n = self.ns
        alive = self.alive()
        arg0 = args[0] if args else None

        if cmd == "voir":
            if self.state != "night" or p.role != "voyante" or not p.alive:
                return await self.dm(p, "Tu n'as rien à sonder pour l'instant.")
            if n.seer:
                return await self.dm(p, "Tu as déjà sondé quelqu'un cette nuit.")
            t = self.target(arg0, [x for x in alive if x is not p])
            if not t:
                return await self.dm(p, "❓ Cible invalide. /voir N")
            n.seer = True
            await self.dm(p, f"🔮 *{t.name}* est : {label(t.role)}")
            return self.poke()

        if cmd == "devorer":
            if self.state != "night" or p.role != "loup" or not p.alive:
                return await self.dm(p, "Tu ne peux pas dévorer pour l'instant.")
            t = self.target(arg0, [x for x in alive if x.role != "loup"])
            if not t:
                return await self.dm(p, "❓ Cible invalide (on ne dévore pas un loup). /devorer N")
            n.votes[p.num] = t.num
            for w in [x for x in alive if x.role == "loup"]:
                await self.dm(w, f"🐺 Choix enregistré : *{t.name}*." if w is p else f"🐺 *{p.name}* veut dévorer *{t.name}*.")
            return self.poke()

        if cmd == "aimer":
            if self.state != "night" or self.day_no != 1 or p.role != "cupidon":
                return await self.dm(p, "Tu ne peux pas lancer de flèches maintenant.")
            if n.cupid:
                return await self.dm(p, "Tes flèches sont déjà parties.")
            a = self.target(args[0] if args else None, alive)
            b = self.target(args[1] if len(args) > 1 else None, alive)
            if not a or not b or a is b:
                return await self.dm(p, "❓ Choisis deux joueurs différents : /aimer N N")
            n.cupid = True
            await self.set_lovers(a, b)
            await self.dm(p, f"💘 *{a.name}* et *{b.name}* sont maintenant amoureux.")
            return self.poke()

        if cmd == "sauver":
            if not n or not n.witch_open or p.role != "sorciere":
                return await self.dm(p, "Pas maintenant.")
            if not self.potions["heal"]:
                return await self.dm(p, "Ta potion de guérison est déjà utilisée.")
            if n.victim_num is None:
                return await self.dm(p, "Il n'y a personne à sauver.")
            self.potions["heal"] = False
            n.heal = True
            await self.dm(p, "💚 Potion de guérison utilisée. Tu peux encore /empoisonner N ou valider avec /rien.")
            if not self.potions["poison"]:
                n.witch_done = True
                self.poke()
            return

        if cmd == "empoisonner":
            if not n or not n.witch_open or p.role != "sorciere":
                return await self.dm(p, "Pas maintenant.")
            if not self.potions["poison"]:
                return await self.dm(p, "Ta potion de poison est déjà utilisée.")
            t = self.target(arg0, [x for x in alive if x is not p])
            if not t:
                return await self.dm(p, "❓ Cible invalide. /empoisonner N")
            self.potions["poison"] = False
            n.poison = t
            await self.dm(p, f"☠️ Poison versé pour *{t.name}*. Valide avec /rien ou /sauver si ce n'est pas déjà fait.")
            if not self.potions["heal"]:
                n.witch_done = True
                self.poke()
            return

        if cmd in ("rien", "fini"):
            if n and n.witch_open and p.role == "sorciere":
                n.witch_done = True
                await self.dm(p, "🌙 Très bien, la nuit continue.")
                return self.poke()
            return await self.dm(p, "Rien à valider pour le moment.")

        if cmd == "tirer":
            if not self.hunter or self.hunter.p is not p:
                return await self.dm(p, "Tu n'as pas de balle à tirer maintenant.")
            t = self.target(arg0, alive)
            if not t:
                return await self.dm(p, "❓ Cible invalide. /tirer N")
            self.hunter.choice = t
            await self.dm(p, f"🏹 Tu as visé *{t.name}*.")
            return self.poke()

        return await self.dm(p, "Commande inconnue. Tape /aide.")
