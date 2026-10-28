# 🐺 Bot WhatsApp Loup-Garou (Python)

Anime des parties de Loup-Garou dans un groupe WhatsApp : rôles en privé, nuit/jour, votes, tutoriel et **narration médiévale générée par IA** (différente à chaque partie).

## Installation
1. Python 3.10 ou plus.
2. `pip install -r requirements.txt`
3. Copier `.env.example` en `.env` et renseigner `ANTHROPIC_API_KEY`.
4. `python bot.py`, scanner le QR code avec **un numéro WhatsApp dédié**, ajouter ce numéro au groupe.
5. Test hors ligne du moteur (sans WhatsApp) : `python sim.py`

## Comment ça s'assemble (intégration)
```
WhatsApp ⇄ neonize ⇄ bot.py ⇄ game.py ⇄ narrator.py ⇄ API Claude
```
- **bot.py** : seule couche qui connaît WhatsApp. Elle reçoit les messages, repère les commandes (`/vote 3`), distingue groupe et message privé, identifie le joueur, puis appelle le moteur. Elle fournit aussi la fonction `send()`.
- **game.py** : le moteur (rôles, phases, votes, victoires). Il ne parle jamais à WhatsApp directement : il appelle `send(destinataire, texte)`.
- **narrator.py** : pour chaque événement, envoie à Claude le contexte public (village, nombre de joueurs, vivants, morts révélés, ton de la partie, narrations précédentes) et récupère un texte. Les secrets (rôles des vivants) ne lui sont jamais transmis. En cas d'erreur, un texte de secours prend le relais.
- **Threads** : neonize appelle vos handlers dans ses propres threads ; `bot.py` les renvoie vers une boucle asyncio unique, donc le moteur n'a pas de problèmes de concurrence.
- **Changer de bibliothèque WhatsApp** : seul `bot.py` est à réécrire.

## Utilisation
`/nouvelle [village]`, `/village NOM`, `/rejoindre`, `/start`, `/vote N`, `/stop`, `/tuto`, `/roles`, `/aide`.
En privé avec le bot : `/voir N`, `/devorer N`, `/sauver`, `/empoisonner N`, `/rien`, `/aimer N N`, `/tirer N`.

## Règles simplifiées
Rôles : Loup-Garou, Villageois, Voyante, Sorcière, Chasseur, Cupidon. Loups : 1 (jusqu'à 7 joueurs), 2 (8 à 11), 3 (12 et plus). Sorcière dès 6, Chasseur dès 7, Cupidon dès 8. Égalité au vote = pas d'exécution.

## Remarques
- neonize est **non officiel** : numéro dédié, bannissement possible.
- Les noms de champs neonize (`event.Info.MessageSource`, `Sender`, `Chat`, `IsGroup`…) peuvent varier selon la version : en cas d'erreur à la réception, c'est le seul endroit à ajuster (`handle()` dans `bot.py`).
- « Les Loups-Garous de Thiercelieux » appartient aux éditions « lui-même » : usage privé sans souci, mais pour un bot public changez le nom et ne reprenez ni textes ni illustrations.
