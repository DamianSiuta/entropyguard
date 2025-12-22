# 🗺️ ENTRPYGUARD - ROADMAP (4 TYGODNIE)

## TYDZIEŃ 1: SECURITY & ARCHITECTURE HARDENING

### Dzień 1-2: Security Fixes (KRYTYCZNE)

#### Task 1.1: Naprawić SQL Injection
**Plik:** `control-plane/app/main.py`
**Status:** 🔴 KRYTYCZNE

```python
# PRZED (niebezpieczne):
where_clause = " AND ".join(where_conditions)
count_query = f"SELECT COUNT(*) FROM telemetry_logs WHERE {where_clause}"

# PO (bezpieczne):
from sqlalchemy import and_, or_, func
conditions = []
if search:
    conditions.append(TelemetryLog.content.cast(String).ilike(f"%{search}%"))
if severity:
    conditions.append(TelemetryLog.content['event_type'].astext == severity)
# ... itd.
query = select(func.count(TelemetryLog.id)).where(and_(*conditions))
```

**Szacowany czas:** 4h

#### Task 1.2: Dodać JWT Authentication
**Plik:** `control-plane/app/auth.py` (nowy)

```python
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

**Szacowany czas:** 8h

#### Task 1.3: Dodać Rate Limiting
**Plik:** `control-plane/app/main.py`

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/v1/telemetry/audit")
@limiter.limit("100/minute")
async def get_telemetry_audit(...):
    ...
```

**Szacowany czas:** 2h

#### Task 1.4: Dodać CORS
**Plik:** `control-plane/app/main.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Szacowany czas:** 1h

#### Task 1.5: Dodać Walidację (Pydantic)
**Plik:** `control-plane/app/schemas.py` (nowy)

```python
from pydantic import BaseModel, Field, validator

class AuditQueryParams(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    search: Optional[str] = Field(default=None, max_length=500)
    severity: Optional[str] = Field(default=None, regex="^(error|warning|info|success|debug)$")
    source: Optional[str] = Field(default=None, max_length=100)
```

**Szacowany czas:** 2h

### Dzień 3-4: Architecture Refactoring

#### Task 1.6: Rozdzielić main.py
**Struktura:**
```
control-plane/app/
  ├── main.py (tylko FastAPI app setup)
  ├── routes/
  │   ├── __init__.py
  │   ├── audit.py
  │   ├── stats.py
  │   └── system.py
  ├── services/
  │   ├── __init__.py
  │   └── telemetry_service.py
  └── middleware/
      ├── __init__.py
      ├── auth.py
      └── audit_log.py
```

**Szacowany czas:** 6h

#### Task 1.7: Dodać Error Handling Middleware
**Plik:** `control-plane/app/middleware/error_handler.py`

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )
```

**Szacowany czas:** 2h

### Dzień 5: Database Optimization

#### Task 1.8: Dodać Indeksy
**Plik:** `control-plane/migrations/001_add_indexes.sql` (nowy)

```sql
CREATE INDEX IF NOT EXISTS idx_telemetry_logs_created_at 
ON telemetry_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_logs_content_gin 
ON telemetry_logs USING GIN (content::jsonb);

CREATE INDEX IF NOT EXISTS idx_telemetry_logs_source 
ON telemetry_logs ((content::jsonb->>'source'));

CREATE INDEX IF NOT EXISTS idx_telemetry_logs_event_type 
ON telemetry_logs ((content::jsonb->>'event_type'));
```

**Szacowany czas:** 2h

#### Task 1.9: Dodać Redis Cache
**Plik:** `control-plane/app/cache.py` (nowy)

```python
import redis
from functools import wraps

redis_client = redis.Redis(host='redis', port=6379, db=0)

def cache_result(ttl=300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator
```

**Szacowany czas:** 4h

---

## TYDZIEŃ 2: ADVANCED FEATURES

### Dzień 1-2: Alerting

#### Task 2.1: Model AlertRule
**Plik:** `control-plane/app/models.py`

```python
class AlertRule(Base):
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    threshold = Column(Integer, nullable=False)  # np. 100 errors w 5 min
    time_window_minutes = Column(Integer, default=5)
    webhook_url = Column(String, nullable=True)
    email = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
```

**Szacowany czas:** 2h

#### Task 2.2: Background Worker (Celery)
**Plik:** `control-plane/app/tasks.py` (nowy)

```python
from celery import Celery

celery_app = Celery('entropyguard', broker='redis://redis:6379/0')

@celery_app.task
def check_alerts():
    # Sprawdź wszystkie alert rules
    # Jeśli threshold przekroczony → wyślij webhook/email
    pass
```

**Szacowany czas:** 6h

#### Task 2.3: Slack Webhook Integration
**Plik:** `control-plane/app/services/alert_service.py` (nowy)

```python
import requests

def send_slack_alert(webhook_url: str, message: str):
    payload = {"text": message}
    requests.post(webhook_url, json=payload)
```

**Szacowany czas:** 2h

### Dzień 3-4: Search Enhancement

#### Task 2.4: Elasticsearch Integration
**Plik:** `control-plane/app/services/search_service.py` (nowy)

```python
from elasticsearch import Elasticsearch

es = Elasticsearch(['elasticsearch:9200'])

def index_log(log: TelemetryLog):
    es.index(
        index='telemetry_logs',
        id=log.id,
        body={
            'content': log.content,
            'created_at': log.created_at.isoformat(),
            'source': json.loads(log.content).get('source'),
            'severity': json.loads(log.content).get('event_type'),
        }
    )

def search_logs(query: str, filters: dict):
    return es.search(
        index='telemetry_logs',
        body={
            'query': {
                'bool': {
                    'must': [{'match': {'content': query}}],
                    'filter': [{'term': {k: v}} for k, v in filters.items()]
                }
            }
        }
    )
```

**Szacowany czas:** 8h

### Dzień 5: Data Retention

#### Task 2.5: Scheduled Job
**Plik:** `control-plane/app/tasks.py`

```python
@celery_app.task
def cleanup_old_logs(retention_days: int = 30):
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    db.query(TelemetryLog).filter(
        TelemetryLog.created_at < cutoff_date
    ).delete()
    db.commit()
```

**Szacowany czas:** 3h

---

## TYDZIEŃ 3: AI & INTELLIGENCE

### Dzień 1-3: Anomaly Detection

#### Task 3.1: ML Model
**Plik:** `control-plane/app/services/anomaly_detector.py` (nowy)

```python
from sklearn.ensemble import IsolationForest
import numpy as np

class AnomalyDetector:
    def __init__(self):
        self.model = IsolationForest(contamination=0.1)
    
    def detect_anomalies(self, logs: List[TelemetryLog]):
        features = self._extract_features(logs)
        predictions = self.model.fit_predict(features)
        return [logs[i] for i in range(len(logs)) if predictions[i] == -1]
    
    def _extract_features(self, logs):
        # Extract: error_rate, response_time, source_diversity, etc.
        pass
```

**Szacowany czas:** 12h

---

## TYDZIEŃ 4: DEPLOYMENT & MONETIZATION

### Dzień 1-2: Multi-tenant

#### Task 4.1: Tenant Model
**Plik:** `control-plane/app/models.py`

```python
class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False)
    plan = Column(String, default="free")  # free, pro, enterprise
    created_at = Column(DateTime, server_default=func.now())
```

**Szacowany czas:** 8h

### Dzień 3: Payment Integration

#### Task 4.2: Stripe Integration
**Plik:** `control-plane/app/services/payment_service.py` (nowy)

```python
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_subscription(customer_id: str, plan: str):
    return stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": PLAN_PRICES[plan]}]
    )
```

**Szacowany czas:** 6h

---

## 📊 METRYKI SUKCESU

- **Security:** 0 krytycznych luk (obecnie: 5)
- **Performance:** <500ms response time (obecnie: 2-5s)
- **Features:** 80% funkcjonalności Datadog (obecnie: 20%)
- **Revenue:** $10k MRR w 3 miesiące

