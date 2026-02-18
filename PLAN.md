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
RAG_construccion/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Punto de entrada FastAPI
│   ├── config.py                  # Configuración centralizada (pydantic-settings)
│   ├── logging_config.py          # Configuración de loguru
│   │
│   ├── api/                       # Capa de rutas/endpoints
│   │   ├── __init__.py
│   │   ├── dependencies.py        # Dependencias reutilizables (sesión BD)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── documents.py       # Endpoints de documentos
│   │       ├── knowledge.py       # Endpoints de conocimiento
│   │       └── rag.py             # Endpoints de consultas RAG
│   │
│   ├── core/                      # Lógica de negocio core
│   │   ├── __init__.py
│   │   ├── models/               # Modelos SQLAlchemy
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Base, UUIDMixin, TimestampMixin
│   │   │   ├── document.py       # Modelo Document
│   │   │   ├── chunk.py          # Modelo Chunk (texto extraído)
│   │   │   └── embedding.py      # Modelo Embedding (pgvector)
│   │   ├── schemas/              # Pydantic schemas (validación)
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── query.py
│   │   │   └── response.py
│   │   └── services/             # Lógica de negocio
│   │       ├── __init__.py
│   │       ├── document_service.py      # Gestión y procesamiento de documentos
│   │       ├── vector_search_service.py # Búsqueda vectorial con pgvector
│   │       └── rag_service.py           # Orquestación RAG
│   │
│   ├── processors/               # Procesadores de documentos
│   │   ├── __init__.py
│   │   ├── base.py              # Clase abstracta Processor
│   │   ├── pdf_processor.py     # PDF (pdfplumber + PyMuPDF)
│   │   ├── txt_processor.py     # TXT, MD
│   │   ├── csv_processor.py     # CSV, XLSX (pandas)
│   │   └── docx_processor.py   # DOCX (python-docx)
│   │
│   ├── embeddings/               # Módulo de embeddings
│   │   ├── __init__.py
│   │   └── encoder.py           # Wrapper para sentence-transformers
│   │
│   ├── llm/                      # Módulo LLM - Google Gemini
│   │   ├── __init__.py
│   │   ├── base.py              # Clase abstracta LLMClient
│   │   ├── gemini_client.py     # Implementación Google Gemini
│   │   └── factory.py           # Factory para crear clientes LLM
│   │
│   └── database/                 # Configuración de BD
│       ├── __init__.py
│       └── connection.py        # Sesiones async/sync SQLAlchemy
│
├── alembic/                      # Migraciones de base de datos
│   ├── env.py
│   ├── script.py.mako
│   ├── versions/
│   │   └── 001_initial_migration.py
│   └── README.md
│
├── alembic.ini                   # Configuración Alembic
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── README.md
├── PLAN.md
└── INFORME_AUDITORIA_SEGURIDAD.md
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
| GET | `/api/v1/knowledge/search` | Búsqueda semántica (sin LLM) |
| GET | `/api/v1/knowledge/chunks/{document_id}` | Ver chunks de un documento |
| GET | `/api/v1/knowledge/stats` | Estadísticas de la base |

### 🤖 Consultas RAG
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/rag/query` | Realizar consulta al RAG |

### ⚙️ Sistema
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Health check |

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

## Lista de Tareas

- [x] Crear estructura del proyecto FastAPI modular
- [x] Configurar PostgreSQL con extensión pgvector
- [x] Implementar modelos SQLAlchemy con SQLAlchemy 2.0
- [x] Crear processors para PDF, TXT, CSV, DOCX
- [x] Implementar pipeline de embeddings con sentence-transformers
- [x] Desarrollar endpoints REST con soporte drag & drop
- [x] Implementar sistema de barra de progreso (polling + porcentaje)
- [x] Desarrollar endpoints para consultas RAG con Gemini
- [x] Implementar sistema de búsqueda semántica (vector + metadatos)
- [x] Agregar configuración con .env y validaciones
- [x] Documentar API con Swagger/OpenAPI
- [x] Crear docker-compose para despliegue
- [ ] Crear tests unitarios y de integración
- [ ] Implementar autenticación (API Keys / JWT)

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
