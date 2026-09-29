# Epic Events CRM

Projet de CRM en ligne de commande, développé étape par étape en Python.

## Étape 1 : environnement Python et base de données

SQLite est utilisé pour la première version. La base est un fichier local créé
automatiquement lors de la première connexion. SQLAlchemy fournit la connexion
qui servira aux modèles ORM des prochaines étapes.

Depuis le dossier du projet, avec Python 3.9 ou plus récent :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe database.py
```

Le dernier appel doit afficher `Connexion à la base de données réussie.` et
créer `epic_events.db`. Le fichier `.env` contient l'URL de connexion et n'est
pas versionné. Le fichier de base de données n'est pas versionné non plus.
Lancez les commandes depuis le dossier du projet, car le chemin SQLite dans
`.env` est relatif à ce dossier.

SQLite ne possède pas de comptes utilisateurs SQL ni de serveur à administrer.
Les droits d'accès au fichier sont ceux du compte Windows qui lance
l'application : utilisez un compte standard, sans droits administrateur, et
conservez la base dans un emplacement accessible uniquement à ce compte.
Les rôles et restrictions d'accès aux données du CRM seront implémentés dans
les étapes de développement.
