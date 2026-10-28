"""Couche WhatsApp (neonize) : traduit les messages WhatsApp en appels vers le moteur de jeu.

Tout ce qui dépend de WhatsApp est dans CE fichier. Le moteur (game.py) n'en sait rien.
"""
import asyncio
import threading
import traceback
import unicodedata

from dotenv import load_dotenv

load_dotenv()

from neonize.client import NewClient  # noqa: E402
from neonize.events import ConnectedEv, MessageEv  # noqa: E402

from game import Game  # noqa: E402
from tutorial import HELP, ROLES_HELP, TUTO  # noqa: E402

# --- Boucle asyncio dédiée : neonize appelle nos handlers depuis ses propres threads,
#     on y renvoie tout le travail pour que le moteur reste mono-thread. ---
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, daemon=True).start()

client = NewClient("loupgarou.sqlite3")  # fichier de session (QR code scanné une seule fois)
games: dict[str, Game] = {}  # clé = identifiant du groupe
_send_lock = asyncio.Lock()


async def send(jid, text: str):
    """Envoi sérialisé avec une petite pause (limite les risques de blocage anti-spam)."""
    async with _send_lock:
        await asyncio.to_thread(client.send_message, jid, text)
        await asyncio.sleep(0.65)


def jid_key(jid) -> str:
    return f"{jid.User}@{jid.Server}"


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def game_of(ids):
    for g in games.values():
        p = g.find_player(ids)
        if p and g.state != "over":
            return g, p
    return None


async def handle(event: MessageEv):
    info = event.Info
    src = info.MessageSource
    if src.IsFromMe:
        return
    msg = event.Message
    body = (msg.conversation or msg.extendedTextMessage.text or "").strip()
    if not body or body[0] not in "/!":
        return

    chat = src.Chat
    sender = src.Sender
    is_group = bool(src.IsGroup)
    name = info.Pushname or "Joueur"

    # Identifiants du joueur : numéro et/ou identifiant « LID » (WhatsApp utilise les deux)
    ids = [sender.User]
    alt = getattr(src, "SenderAlt", None)
    if alt is not None and getattr(alt, "User", ""):
        ids.append(alt.User)
    ids = [i for i in ids if i]

    parts = body[1:].strip().split()
    cmd = strip_accents(parts[0].lower()) if parts else ""
    args = parts[1:]

    async def reply(text):
        try:
            await send(chat, text)
        except Exception as e:
            print("reply:", e)

    # Commandes d'information, partout
    if cmd in ("tuto", "regles", "regle"):
        return await reply(TUTO)
    if cmd == "roles":
        return await reply(ROLES_HELP)
    if cmd in ("aide", "help"):
        return await reply(HELP)

    # ---------------- Groupe ----------------
    if is_group:
        key = jid_key(chat)
        game = games.get(key)

        if cmd in ("nouvelle", "loup", "jouer"):
            if game and game.state != "over":
                return await reply("Une partie est déjà en cours dans ce groupe. (/stop pour l'annuler, créateur seulement)")
            if game_of(ids):
                return await reply("Tu participes déjà à une partie dans un autre groupe.")

            def on_end(g, key=key):
                if games.get(key) is g:
                    games.pop(key, None)

            g = Game(chat, ids, send, on_end)
            games[key] = g
            if args:
                g.village = " ".join(args)[:40]
            ok, text = g.add_player(ids, name, sender)
            village_line = f"🏰 Village : *{g.village}*\n" if g.village else "🏰 Quel nom pour le village ? Répondez avec */village NOM* (sinon j'en inventerai un).\n"
            return await reply(
                f"🐺 *Nouvelle partie de Loup-Garou !*\n\n{village_line}\n{text}\n\n"
                "• /rejoindre pour participer (de 5 à 18 joueurs)\n• /start pour lancer\n• /tuto pour apprendre les règles"
            )

        if not game or game.state == "over":
            return await reply("Aucune partie ici. Tape /nouvelle pour en créer une.")
        me = game.find_player(ids)

        if cmd == "village":
            if game.state != "lobby":
                return await reply("Le village est déjà baptisé.")
            if not me:
                return await reply("Rejoins la partie (/rejoindre) pour proposer un nom.")
            if not args:
                return await reply("Usage : /village NOM")
            game.village = " ".join(args)[:40]
            return await reply(f"🏰 Le village s'appellera *{game.village}*.")
        if cmd in ("rejoindre", "join"):
            if game_of(ids) and not me:
                return await reply("Tu participes déjà à une partie dans un autre groupe.")
            return await reply(game.add_player(ids, name, sender)[1])
        if cmd == "quitter":
            return await reply(game.remove_player(ids)[1])
        if cmd in ("joueurs", "liste"):
            extra = f"\n\nEn vie : {', '.join(p.name for p in game.alive())}" if game.state != "lobby" else ""
            return await reply(game.lobby_text() + extra)
        if cmd in ("start", "lancer", "commencer"):
            if not game.is_creator(ids):
                return await reply("Seul le créateur de la partie peut la lancer.")
            if game.state != "lobby":
                return await reply("La partie est déjà lancée.")
            err = game.can_start()
            if err:
                return await reply(err)
            return game.start()
        if cmd == "vote":
            return await game.handle_vote(me, " ".join(args))
        if cmd in ("stop", "annuler"):
            if not game.is_creator(ids):
                return await reply("Seul le créateur peut annuler la partie.")
            game.stop()
            games.pop(key, None)
            return await reply("🛑 Partie annulée.")
        return

    # ---------------- Message privé ----------------
    found = game_of(ids)
    if not found:
        return await reply("Tu n'es dans aucune partie. Rejoins-en une dans un groupe avec /rejoindre, ou tape /aide.")
    g, p = found
    p.ids.update(ids)
    p.dm = chat  # discussion privée prouvée valide : on s'en sert pour répondre
    return await g.handle_private(p, cmd, args)


async def safe_handle(event):
    try:
        await handle(event)
    except Exception:
        traceback.print_exc()


@client.event(ConnectedEv)
def on_connected(_: NewClient, __: ConnectedEv):
    print("✅ Bot connecté.")


@client.event(MessageEv)
def on_message(_: NewClient, event: MessageEv):
    asyncio.run_coroutine_threadsafe(safe_handle(event), loop)


if __name__ == "__main__":
    print("Démarrage… scanne le QR code avec le WhatsApp du numéro dédié au bot.")
    client.connect()
    if hasattr(client, "idle"):  # selon la version de neonize, connect() peut ne pas bloquer
        client.idle()
