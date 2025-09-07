# Customer API

Microservice **FastAPI** permettant la gestion des clients (**CRUD**) dans une architecture **microservices**.
Il persiste les données dans **PostgreSQL** et publie des **événements** dans **RabbitMQ** lors des opérations CRUD.

---

## 🚀 Technologies

* **FastAPI** — framework web moderne (async, OpenAPI intégré)
* **PostgreSQL** — base de données relationnelle
* **SQLAlchemy** — ORM
* **Pydantic v2** — validation de schémas
* **RabbitMQ** + **aio-pika** — message broker
* **Docker & Docker Compose** — conteneurisation

---

## ⚡ Démarrage rapide

### 1) Cloner le dépôt

```bash
git clone https://github.com/votre-nom/customer-api.git
cd customer-api
```

### 2) Créer un fichier `.env`

Valeurs par défaut pour un lancement **100% Docker** :

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=customerdb
POSTGRES_SERVER=db
POSTGRES_PORT=5432

RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/%2F
# EVENTS_STRICT=false
# EVENT_PUBLISH_TIMEOUT_SECONDS=2
```

### 3) Lancer l’infrastructure

```bash
docker compose up --build
```

Cela va :
✅ construire l’image de l’API
✅ lancer PostgreSQL et RabbitMQ (UI → `http://localhost:15672`, login `guest/guest`)
✅ exposer l’API sur `http://localhost:8000`

---

## 📚 Endpoints principaux

* **Créer un client (201)**

```bash
curl -X POST http://localhost:8000/api/clients \
  -H "Content-Type: application/json" \
  -d '{"name":"Benjamin","email":"ben@kawa.fr"}'
```

* **Lister les clients (200)**

```bash
curl http://localhost:8000/api/clients
```

* **Récupérer un client (200 / 404)**

```bash
curl http://localhost:8000/api/clients/1
```

* **Mettre à jour un client (200)**

```bash
curl -X PUT http://localhost:8000/api/clients/1 \
  -H "Content-Type: application/json" \
  -d '{"name":"Benjamin Updated","email":"benjamin@kawa.fr"}'
```

* **Supprimer un client (200)**

```bash
curl -X DELETE http://localhost:8000/api/clients/1
```

---

## 📡 Événements RabbitMQ

Chaque opération CRUD publie un événement dans l’exchange `customer_events` (**fanout**) :

* `customer.created`
* `customer.updated`
* `customer.deleted`

**Exemple :**

```json
{
  "type": "customer.created",
  "source": "customer-api",
  "data": {
    "id": 42,
    "email": "ben@kawa.fr",
    "name": "Benjamin"
  }
}
```

---

## 🧪 Tests

### Lancer les tests localement

```bash
docker compose run --rm tests
```

ou directement :

```bash
pytest -q --disable-warnings --maxfail=1
```

### Rapport de couverture

```bash
pytest --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml
```

---

## 🛡️ CI/CD

* **GitHub Actions** (CI) : build, lint, tests + rapport de couverture
* **SonarQube** (optionnel) : analyse qualité & dette technique

Fichier principal : `.github/workflows/build.yml`

---

## 📖 Documentation interactive

* Swagger UI : [http://localhost:8000/docs](http://localhost:8000/docs)
* OpenAPI JSON : [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 📂 Structure du projet

```
customer-api/
├── app/
│   ├── api/            # Routes FastAPI (CRUD + publish events)
│   ├── core/           # Logger, DB, RabbitMQ client
│   ├── models/         # Modèles SQLAlchemy
│   ├── schemas/        # Schémas Pydantic v2
│   └── repositories/   # Accès DB
│
├── tests/              # Tests unitaires & intégration
├── docker-compose.yml  # inclut PostgreSQL + RabbitMQ
├── requirements.txt
├── Dockerfile
└── .env
```

---

## 👥 Auteurs

* GIRARD Anthony
* FIACSAN Nicolas
* QUACH Simon
* PRUJA Benjamin

Projet **MSPR TPRE814 — EPSI 2024-2025**
