# Evidence Service Extraction Map

## Source Files (from FaultMaven monolith)

| Monolith File | Destination | Action |
|---------------|-------------|--------|
| faultmaven/models/evidence.py | src/evidence_service/domain/models/evidence.py | Extract evidence models |
| faultmaven/services/domain/data_service.py | src/evidence_service/domain/services/evidence_service.py | Extract data processing logic |
| faultmaven/api/v1/routes/data.py | src/evidence_service/api/routes/evidence.py | Extract API endpoints |
| faultmaven/core/processing/*.py | src/evidence_service/domain/services/processing/ | Extract data processors |

## Database Tables (exclusive ownership)

| Table Name | Source Schema | Action |
|------------|---------------|--------|
| evidence | 001_initial_hybrid_schema.sql | MIGRATE to fm_evidence database |
| uploaded_files | 001_initial_hybrid_schema.sql | MIGRATE to fm_evidence database |

## Events Published

| Event Name | AsyncAPI Schema | Trigger |
|------------|-----------------|---------|
| evidence.uploaded.v1 | contracts/asyncapi/evidence-events.yaml | POST /v1/evidence |
| evidence.processed.v1 | contracts/asyncapi/evidence-events.yaml | Background processing complete |
| evidence.deleted.v1 | contracts/asyncapi/evidence-events.yaml | DELETE /v1/evidence/{id} |

## Events Consumed

| Event Name | Source Service | Action |
|------------|----------------|--------|
| case.deleted.v1 | Case Service | Delete case evidence |
| auth.user.deleted.v1 | Auth Service | Delete user's evidence |

## API Dependencies

| Dependency | Purpose | Fallback Strategy |
|------------|---------|-------------------|
| Auth Service | Validate user tokens | Circuit breaker (deny if down) |
| Case Service | Verify case ownership | Circuit breaker (return 403) |

## Migration Checklist

- [ ] Extract domain models (Evidence, UploadedFile)
- [ ] Extract business logic (data classification, preprocessing)
- [ ] Extract API routes (evidence upload, retrieval)
- [ ] Extract repository (PostgreSQL + S3/GCS storage)
- [ ] Create database migration scripts (001_initial_schema.sql)
- [ ] Implement event publishing (outbox pattern)
- [ ] Implement event consumption (inbox pattern)
- [ ] Add circuit breakers for dependencies
- [ ] Write unit tests (80%+ coverage)
- [ ] Write integration tests (DB + storage)
- [ ] Write contract tests (provider verification)
