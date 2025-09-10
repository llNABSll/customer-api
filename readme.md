# Customer API

`customer-api` est un microservice FastAPI (CRUD clients) faisant partie d’une architecture **microservices**.
Il persiste les données dans **PostgreSQL** et publie des **événements** dans **RabbitMQ** lors des opérations CRUD.

## Technologies

* FastAPI (backend)
* PostgreSQL (base de données)
* SQLAlchemy (ORM)
* Pydantic v2 (validation)
* RabbitMQ + aio-pika (message broker)
* Docker & Docker Compose (conteneurs)

---

## Démarrage rapide

### 1 Cloner le dépôt

```bash
git clone https://github.com/votre-nom/customer-api.git
cd customer-api
```

### 2 Créer le `.env`

> Valeurs par défaut pour un lancement **100% Docker** (API + DB + RabbitMQ) :

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=customerdb
POSTGRES_SERVER=db
POSTGRES_PORT=5432

# Broker (service "rabbitmq" du docker-compose)
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/%2F

# (Optionnel) rendre l'émission d'événements bloquante en prod
# EVENTS_STRICT=false
# EVENT_PUBLISH_TIMEOUT_SECONDS=2
```

### 3 Lancer les conteneurs

```bash
docker compose up --build
# ou: docker-compose up --build
```

Cela :

* construit l’image de l’API,
* lance PostgreSQL et RabbitMQ (UI sur `http://localhost:15672` / guest\:guest),
* démarre l’API sur `http://localhost:8000`.

---

## Endpoints principaux

### Créer un client (201)

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

### Lister les clients (200)

```bash
curl http://localhost:8000/api/clients
```

### Récupérer un client (200 / 404)

```bash
curl http://localhost:8000/api/clients/1
```

### Mettre à jour un client (200)

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

### Supprimer un client (200)

```bash
curl -X DELETE http://localhost:8000/api/clients/1
```

---

## Événements RabbitMQ

L’API publie un événement **fanout** dans l’exchange `customer_events` après chaque opération :

* `customer.created`
* `customer.updated`
* `customer.deleted`

### Exemple de payload émis

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

> Remarque : les champs **obligatoires** côté création sont `name` et `email`.
> `company` et `phone` sont **optionnels** et peuvent être présents dans les réponses API.

---

## Vérifier le broker (UI RabbitMQ)

1. Ouvrir `http://localhost:15672` (guest/guest) → onglet **Exchanges** → `customer_events` (type **fanout**).
2. Créer une queue de debug : onglet **Queues and Streams** → *Add a new queue* → `debug-customer-events`.
3. Binder la queue : retour sur **customer\_events** → *Add binding from this exchange* → *To queue* = `debug-customer-events` → **Bind**.
4. Rejouer un `POST / PUT / DELETE` client.
5. Aller dans **Queues** → `debug-customer-events` → *Get messages* → vous devez voir les JSON des événements.

---

## Tests de résilience (dev)

Par défaut, l’API est en mode **“safe”** : si RabbitMQ est down, les requêtes HTTP réussissent et l’échec de publication est loggé.

```bash
docker compose stop rabbitmq
# POST /clients -> 201 quand même
# logs: [events] publish failed: ...
docker compose start rabbitmq
```

Pour un comportement **strict** (staging/prod), vous pouvez activer :

```env
EVENTS_STRICT=true
EVENT_PUBLISH_TIMEOUT_SECONDS=2
```

> En mode strict, si la publication échoue, l’API renvoie **503**.

---

## Documentation interactive

* Swagger UI : [http://localhost:8000/docs](http://localhost:8000/docs)
* OpenAPI JSON : [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## Structure du projet

```
customer-api/
│
├── app/
│   ├── api/                # Routes FastAPI (CRUD + publish events)
│   ├── core/               # Logger, DB, client RabbitMQ (aio-pika)
│   ├── models/             # Modèles SQLAlchemy (Client)
│   ├── schemas/            # Pydantic v2 (name/email requis)
│   └── repositories/       # Accès aux données (SQLAlchemy sync)
│
├── tests/                  # (optionnel) tests unitaires/intégration
├── Dockerfile
├── docker-compose.yml      # inclut db + rabbitmq (UI 15672)
├── requirements.txt
└── .env
```

---

## Auteurs

GIRARD Anthony, FIACSAN Nicolas, QUACH Simon, PRUJA Benjamin
Projet MSPR TPRE814 — EPSI 2024-2025


