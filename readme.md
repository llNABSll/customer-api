# Customer API

Ce microservice `customer-api` fait partie d'une architecture microservices. Il expose une API REST pour la gestion des clients (CRUD complet).

## Technologies

- **FastAPI** (framework backend)
- **PostgreSQL** (base de données relationnelle)
- **Docker & Docker Compose** (conteneurisation)
- **SQLAlchemy** (ORM)
- **Pydantic** (validation de données)

---

## Lancement du projet

### 1. Cloner le dépôt

```bash
git clone https://github.com/votre-nom/customer-api.git
cd customer-api
```

### 2. Créer un fichier `.env`

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=customerdb
POSTGRES_SERVER=db
POSTGRES_PORT=5432
```

> Ce fichier est utilisé par `docker-compose.yml` et FastAPI pour se connecter à la base.

### 3. Lancer les conteneurs

```bash
docker-compose up --build
```

Cela va :
- Construire l’image de l’API
- Lancer la base PostgreSQL
- Attendre que la base soit prête
- Démarrer l’API FastAPI sur `http://localhost:8000`

---

## Requêtes API (via `curl`)

### Créer un client

```bash
curl -X POST http://localhost:8000/api/clients \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Benjamin",
    "email": "ben@kawa.fr",
    "company": "Kawa Corp",
    "phone": "0601020304"
}'
```

### Lister les clients

```bash
curl http://localhost:8000/api/clients
```

### Récupérer un client

```bash
curl http://localhost:8000/api/clients/1
```

### Mettre à jour un client

```bash
curl -X PUT http://localhost:8000/api/clients/1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Benjamin Updated",
    "email": "benjamin@kawa.fr",
    "company": "Kawa Corp",
    "phone": "0611223344"
}'
```

### Supprimer un client

```bash
curl -X DELETE http://localhost:8000/api/clients/1
```

---

## Documentation interactive

Accédez à la documentation Swagger UI générée automatiquement :

[http://localhost:8000/docs](http://localhost:8000/docs)

---

## Structure du projet

```
customer-api/
│
├── app/
│   ├── api/                # Routes FastAPI
│   ├── core/               # Configs, logger, DB
│   ├── models/             # Modèles SQLAlchemy
│   ├── schemas/            # Schémas Pydantic
│   └── repositories/       # Accès aux données
│
├── tests/                  # Tests unitaires
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

---

## Auteurs

GIRARD ANthony, FIACSAN Nicolas, QUACH Simon, PRUJA Benjamin

Projet MSPR TPRE814 — EPSI 2024-2025
