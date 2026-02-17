# 🏗️ RAG para Presupuestos de Obra - Plan Técnico

## Visión General

Sistema RAG (Retrieval Augmented Generation) para crear presupuestos de obra. La base de conocimiento se alimentará progresivamente con documentos PDF, TXT, CSV y DOCX para que el LLM responda con información precisa sobre precios, materiales y normas del sector construcción.

---

## Stack Tecnológico

| Componente | Tecnología | Justificación |
|------------|------------|---------------|
| **API Framework** | FastAPI | Rápido, documentación automática con Swagger, ideal para ML/RAG |
| **Base de Datos** | PostgreSQL + pgvector | Robusto, escalable, capacidades vectoriales nativas |
| **ORM** | SQLAlchemy 2.0 | ORM robusto con buen rendimiento |
| **LLM** | Google Gemini | Excelente rendimiento en español, precios competitivos |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) | Rápido, preciso, 384 dimensiones |

---

## Estructura del Proyecto

```
rag_presupuestos/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Punto de entrada FastAPI
│   ├── config.py                  # Configuración centralizada
│   ├── logging_config.py          # Configuración de logs
│   │
│   ├── api/                       # Capa de rutas/endpoints
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py       # Endpoints de documentos
│   │   │   ├── knowledge.py       # Endpoints de conocimiento
│   │   │   ├── rag.py            # Endpoints de consultas RAG
│   │   │   └── embeddings.py      # Endpoints de embeddings
│   │   └── dependencies.py       # Dependencias reutilizables
│   │
│   ├── core/                      # Lógica de negocio core
│   │   ├── __init__.py
│   │   ├── models/               # Modelos SQLAlchemy
│   │   │   ├── __init__.py
│   │   │   ├── document.py       # Modelo Documento
│   │   │   ├── chunk.py          # Modelo Chunk (texto extraído)
│   │   │   └── embedding.py      # Modelo Embedding
│   │   ├── schemas/             # Pydantic schemas (validación)
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── query.py
│   │   │   └── response.py
│   │   └── services/            # Lógica de negocio
│   │       ├── __init__.py
│   │       ├── document_service.py
│   │       ├── embedding_service.py
│   │       ├── vector_search_service.py
│   │       └── rag_service.py
│   │
│   ├── processors/               # Procesadores de documentos
│   │   ├── __init__.py
│   │   ├── base.py              # Clase abstracta Processor
│   │   ├── pdf_processor.py
│   │   ├── txt_processor.py
│   │   ├── csv_processor.py
│   │   └── docx_processor.py
│   │
│   ├── embeddings/               # Módulo de embeddings
│   │   ├── __init__.py
│   │   ├── encoder.py           # Wrapper para sentence-transformers
│   │   └── vectorizer.py        # Lógica de vectorización
│   │
│   ├── llm/                      # Módulo LLM - GOOGLE GEMINI
│   │   ├── __init__.py
│   │   ├── base.py              # Clase abstracta LLM
│   │   ├── gemini_client.py     # Implementación Google Gemini
│   │   └── factory.py           # Factory para crear clientes LLM
│   │
│   └── database/                 # Configuración de BD
│       ├── __init__.py
│       ├── connection.py        # Sesiones SQLAlchemy
│       ├── migrations/          # Alembic migrations
│       └── seeders/             # Datos iniciales
│
├── tests/                        # Tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── api/
│   ├── core/
│   └── processors/
│
├── docs/                         # Documentación
│   ├── api.md
│   ├── architecture.md
│   └── deployment.md
│
├── scripts/                      # Scripts utilitarios
│   ├── init_db.py
│   ├── seed_data.py
│   └── export_knowledge.py
│
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Endpoints de la API

### 📁 Documentos (Drag & Drop + Progreso)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload multi-archivo (PDF, TXT, CSV, DOCX) |
| GET | `/api/v1/documents` | Listar documentos subidos |
| GET | `/api/v1/documents/{id}` | Obtener metadata de documento |
| GET | `/api/v1/documents/{id}/status` | Estado de procesamiento (polling) |
| DELETE | `/api/v1/documents/{id}` | Eliminar documento del sistema |
| POST | `/api/v1/documents/{id}/reindex` | Re-indexar documento |

### 📚 Base de Conocimiento
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/knowledge/search` | Búsqueda semántica |
| GET | `/api/v1/knowledge/chunks` | Ver chunks de un documento |
| GET | `/api/v1/knowledge/stats` | Estadísticas de la base |

### 🤖 Consultas RAG
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/rag/query` | Realizar consulta al RAG |
| GET | `/api/v1/rag/history` | Historial de consultas |

### ⚙️ Sistema
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/embeddings/status` | Estado del pipeline |

---

## Sistema de Barra de Progreso

### Flujo de Trabajo

1. **Upload** → Retorna `job_id` inmediatamente
2. **Polling** → `GET /documents/{id}/status`
3. **Estados**: `pending` → `processing` → `completed` | `failed`
4. **Porcentaje**: `0%`, `25%`, `50%`, `75%`, `100%`

### Estados de Procesamiento

```json
{
  "document_id": "uuid",
  "status": "processing",
  "progress": 50,
  "message": "Generando embeddings...",
  "created_at": "2026-02-17T08:00:00Z",
  "updated_at": "2026-02-17T08:05:00Z"
}
```

---

## Tipos de Documentos Soportados

| Tipo | Extensiones | Procesador |
|------|-------------|------------|
| PDF | `.pdf` | pdfplumber + PyMuPDF |
| Texto | `.txt`, `.md` | Parser nativo |
| CSV | `.csv`, `.xlsx` | pandas |
| Word | `.docx` | python-docx |

---

## Metadatos para Presupuestos

Cada documento puede incluir:
- `tipo`: catálogo, precio_unitario, norma_tecnica, especificacion, otro
- `categoria`: residencial, comercial, industrial, infraestructura
- `fecha_vigencia`: fecha de vigencia de precios
- `unidad`: unidad de medida estándar
- `proveedor`: fuente del documento
- `version`: número de versión

---

## Búsqueda Híbrida

El sistema soportará:
- Búsqueda vectorial (semántica)
- Filtros por metadatos
- Combinación de ambos

---

## Lista de Tareas Completas

- [ ] Crear estructura del proyecto FastAPI modular
- [ ] Configurar PostgreSQL con extensión pgvector
- [ ] Implementar modelos SQLAlchemy con SQLAlchemy 2.0
- [ ] Crear processors para PDF, TXT, CSV, DOCX
- [ ] Implementar pipeline de embeddings con sentence-transformers
- [ ] Desarrollar endpoints REST con soporte drag & drop
- [ ] Implementar sistema de barra de progreso (polling + porcentaje)
- [ ] Desarrollar endpoints para consultas RAG con Gemini
- [ ] Implementar sistema de búsqueda híbrida (vector + metadatos)
- [ ] Agregar configuración con .env y validaciones
- [ ] Crear tests unitarios y de integración
- [ ] Documentar API con Swagger/OpenAPI
- [ ] Crear docker-compose para despliegue

---

## Configuración de Variables de Entorno

```env
# Base de datos
DATABASE_URL=postgresql://user:password@localhost:5432/rag_presupuestos

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-pro

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384

# API
API_HOST=0.0.0.0
API_PORT=8000
MAX_FILE_SIZE_MB=50
ALLOWED_EXTENSIONS=pdf,txt,csv,docx,xlsx

# Procesamiento
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

---

## Recomendaciones Adicionales

1. **Versionado de documentos**: Mantener historial de versiones de catálogos de precios
2. **Endpoints especializados**: Crear endpoints para estimaciones de presupuesto
3. **Métricas de uso**: Documentos indexados, consultas realizadas, tokens utilizados
4. **Caché**: Implementar caché para consultas frecuentes

---

*Documento generado el 17/02/2026*
