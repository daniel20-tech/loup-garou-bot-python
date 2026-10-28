TUTO = """📜 *Comment jouer*

Un village est hanté : en secret, certains habitants sont des *Loups-Garous* 🐺. Chaque joueur reçoit un rôle secret, par message privé.

🌙 *La nuit* — le village dort. Les rôles spéciaux agissent discrètement auprès de moi : les loups choisissent une victime, la Voyante sonde un joueur, la Sorcière peut intervenir.

☀️ *Le jour* — j'annonce les morts (leur rôle est révélé). Le village débat, puis vote pour exécuter un suspect avec */vote N*. Égalité = personne n'est exécuté.

🔁 Nuit, jour, nuit, jour… jusqu'à la victoire.

🏆 *Qui gagne ?*
• Le village : tous les loups sont éliminés.
• Les loups : il ne reste plus aucun villageois.
• Deux amoureux (un loup + un villageois) : ils gagnent seuls s'ils sont les derniers en vie.

💡 *Conseils* : on a le droit de bluffer et de mentir ! Mais ne montrez jamais votre rôle en dehors des règles du jeu.

Tapez */roles* pour le détail des rôles, */aide* pour les commandes."""

ROLES_HELP = """🎭 *Les rôles*

🐺 *Loup-Garou* — dévore un villageois chaque nuit (en accord avec les autres loups). Se cache le jour.
🧑‍🌾 *Simple Villageois* — pas de pouvoir, juste son flair et sa voix.
🔮 *Voyante* — sonde le rôle d'un joueur chaque nuit.
🧪 *Sorcière* — une potion de guérison et une de poison, à usage unique chacune.
🏹 *Chasseur* — s'il meurt, il tire sur un joueur de son choix.
💘 *Cupidon* — lie deux joueurs dès la première nuit : si l'un meurt, l'autre le suit.

Selon le nombre de joueurs, tous les rôles ne sont pas toujours en jeu : le bot annonce la composition au début."""

HELP = """🛠️ *Commandes*

*Dans le groupe*
/nouvelle [nom du village] — créer une partie
/village NOM — choisir le nom du village
/rejoindre · /quitter — s'inscrire ou se retirer
/joueurs — liste des joueurs
/start — lancer la partie (créateur)
/vote N — voter pendant le jour
/stop — annuler la partie (créateur)
/tuto · /roles · /aide

*En message privé avec moi*
/voir N — Voyante
/devorer N — Loups-Garous
/sauver · /empoisonner N · /rien — Sorcière
/aimer N N — Cupidon
/tirer N — Chasseur"""
