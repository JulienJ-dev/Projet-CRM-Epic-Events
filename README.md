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

## Étape 2 : modèles et tables

Après avoir configuré `.env`, créez les tables avec :

```powershell
.\.venv\Scripts\python.exe init_db.py
```

La commande peut être relancée : elle conserve les tables déjà présentes.

```mermaid
erDiagram
    ROLES ||--o{ COLLABORATORS : "département"
    COLLABORATORS ||--o{ CLIENTS : "commercial responsable"
    CLIENTS ||--o{ CONTRACTS : "possède"
    CONTRACTS ||--o{ EVENTS : "concerne"
    COLLABORATORS o|--o{ EVENTS : "support attribué"

    COLLABORATORS {
        int id PK
        string full_name
        string email
        string password_hash
        int role_id FK
    }
    ROLES {
        int id PK
        string name
    }
    CLIENTS {
        int id PK
        int sales_contact_id FK
        string full_name
        string email
        string phone
        string company_name
        date created_at
        date updated_at
    }
    CONTRACTS {
        int id PK
        int client_id FK
        decimal total_amount
        decimal amount_due
        date created_at
        boolean is_signed
    }
    EVENTS {
        int id PK
        int contract_id FK
        int support_contact_id FK
        string name
        datetime start_at
        datetime end_at
        string location
        int attendee_count
        text notes
    }
```

Le commercial d'un contrat est celui de son client. Les coordonnées du client
d'un événement sont accessibles par son contrat. Un événement peut attendre
l'attribution d'un support. Les règles propres aux rôles et la condition
« contrat signé avant création d'un événement » sont définies dans
`permissions.py`. Les opérations CRUD devront appeler ces contrôles.

## Étape 3 : comptes et permissions

Chaque collaborateur possède un numéro d'employé (`Collaborator.id`), un nom,
une adresse email unique et un département lié à la table `roles`.
`init_db.py` initialise les départements gestion, commercial et support.

Installez les dépendances, initialisez la base, puis créez votre premier compte :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe init_db.py
.\.venv\Scripts\python.exe create_first_manager.py
```

L'outil demande un nom, une adresse email et un mot de passe confirmé, masqué
pendant la saisie. Il crée un compte de gestion uniquement si aucun compte
n'existe. La base locale vide de l'étape 2 a été adaptée au nouveau schéma ;
une copie a été conservée dans `epic_events_step2_backup.db`, ignorée par Git.
Pour une autre base contenant l'ancien schéma, `init_db.py` signale qu'une
migration est nécessaire, car `create_all` ne modifie pas les tables existantes.

Les mots de passe doivent comporter de 12 à 128 caractères et ne peuvent pas
être composés uniquement d'espaces. Argon2id génère un sel aléatoire pour chaque
hash. Seul le hash est enregistré. Les emails de connexion sont normalisés en
minuscules, sans espaces autour de l'adresse.

Dans `accounts.py`, `authenticate(session, email, password)` renvoie le compte
identifié ou `None`. `create_collaborator(session, actor, full_name, email,
password, role_name)` exige un compte de gestion. Ces fonctions utilisent une
session SQLAlchemy : l'appelant termine la transaction avec `session.commit()`
ou un bloc `session.begin()`.

L'authentification vérifie l'identité par l'email et le mot de passe.
L'autorisation vérifie ensuite le département et les données concernées avec
`has_permission` ou `require_permission`, à partir du compte authentifié.

| Action | Gestion | Commercial | Support |
| --- | --- | --- | --- |
| Lire les clients, contrats et événements | Tous | Tous | Tous |
| Créer, modifier ou supprimer des collaborateurs | Oui | Non | Non |
| Créer des clients | Non | Oui | Non |
| Modifier un client | Non | Ses clients | Non |
| Créer des contrats | Oui | Non | Non |
| Modifier un contrat | Tous | Contrats de ses clients | Non |
| Créer un événement | Non | Ses clients, contrat signé | Non |
| Attribuer un support à un événement | Oui | Non | Non |
| Modifier un événement | Non | Non | Ses événements attribués |

## Vérifications pendant le développement

Installez les outils de développement, puis lancez les contrôles :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m black --check .
.\.venv\Scripts\python.exe -m pytest
```

Les tests utilisent une base SQLite temporaire en mémoire : ils ne modifient
pas `epic_events.db`. La commande `pytest` affiche aussi la couverture des
modules de connexion, de modèles, de comptes et de permissions. Ces contrôles seront à compléter au fur et
à mesure que l'application grandira.
