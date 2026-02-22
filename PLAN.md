# RAG para Presupuestos de Obra - Plan Tecnico v2.0

## Vision General

Sistema RAG (Retrieval Augmented Generation) para crear presupuestos de obra. La base de conocimiento se alimenta con documentos PDF, TXT, CSV, DOCX, XLSX y BC3/FIEBDC-3. El sistema responde con informacion precisa sobre precios, materiales y normas del sector construccion en Espana. Cuando no encuentra informacion en la BD, genera estimaciones de precio de mercado desglosadas y justificadas con aviso claro al usuario.

---

## Stack Tecnologico

| Componente | Tecnologia | Justificacion |
|------------|------------|---------------|
| **API Framework** | FastAPI | Async, documentacion automatica con Swagger |
| **Base de Datos** | PostgreSQL + pgvector 0.2.5 | Capacidades vectoriales nativas |
| **ORM** | SQLAlchemy 2.0 (async) | ORM robusto con soporte asyncpg |
| **LLM** | Google Gemini 2.5 Flash (configurable en .env) | Buen rendimiento en espanol, equilibrio coste/calidad |
| **Busqueda** | pgvector + PostgreSQL FTS + RRF | Busqueda hibrida: semantica + exacta |
| **Embeddings** | sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2) | Multilingue, 384 dimensiones, optimizado para espanol |
| **Migraciones** | Alembic | Migraciones idempotentes para reinicios seguros |
| **Contenedores** | Docker Compose | PyTorch CPU-only, hot-reload, mem_limit 3g |

---

## Estructura del Proyecto

```
RAG_construccion/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Punto de entrada FastAPI
│   ├── config.py                  # Configuracion centralizada (pydantic-settings)
│   ├── logging_config.py          # Configuracion de loguru
│   │
│   ├── api/                       # Capa de rutas/endpoints
│   │   ├── __init__.py
│   │   ├── dependencies.py        # Dependencias reutilizables (sesion BD)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── documents.py       # Endpoints de documentos (upload, CRUD)
│   │       ├── knowledge.py       # Endpoints de conocimiento (busqueda, stats)
│   │       └── rag.py             # Endpoints RAG + generacion BC3
│   │
│   ├── core/                      # Logica de negocio core
│   │   ├── __init__.py
│   │   ├── models/               # Modelos SQLAlchemy
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Base, UUIDMixin, TimestampMixin
│   │   │   ├── document.py       # Modelo Document
│   │   │   ├── chunk.py          # Modelo Chunk (texto extraido)
│   │   │   └── embedding.py      # Modelo Embedding (pgvector)
│   │   ├── schemas/              # Pydantic schemas (validacion)
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── query.py          # Incluye schemas BC3
│   │   │   └── response.py
│   │   ├── session_store.py       # Store in-memory para conversaciones (TTL 2h)
│   │   └── services/             # Logica de negocio
│   │       ├── __init__.py
│   │       ├── document_service.py      # Gestion y procesamiento de documentos
│   │       ├── vector_search_service.py # Busqueda hibrida (vector + FTS + RRF)
│   │       ├── rag_service.py           # Orquestacion RAG + estimacion mercado
│   │       └── bc3_generator.py         # Generacion BC3 + enriquecimiento LLM
│   │
│   ├── processors/               # Procesadores de documentos
│   │   ├── __init__.py           # Registry de procesadores
│   │   ├── base.py              # Clase abstracta Processor
│   │   ├── pdf_processor.py     # PDF (pdfplumber, tablas markdown, filtro boilerplate)
│   │   ├── txt_processor.py     # TXT, MD
│   │   ├── csv_processor.py     # CSV, XLSX (pandas)
│   │   ├── docx_processor.py    # DOCX (python-docx)
│   │   └── bc3_processor.py     # BC3/FIEBDC-3 (parser propio)
│   │
│   ├── embeddings/               # Modulo de embeddings
│   │   ├── __init__.py
│   │   └── encoder.py           # Wrapper para sentence-transformers
│   │
│   ├── llm/                      # Modulo LLM - Google Gemini
│   │   ├── __init__.py
│   │   ├── base.py              # Clase abstracta LLMClient
│   │   ├── gemini_client.py     # Implementacion Gemini (retry 429)
│   │   └── factory.py           # Factory para crear clientes LLM
│   │
│   └── database/                 # Configuracion de BD
│       ├── __init__.py
│       └── connection.py        # Sesiones async/sync SQLAlchemy
│
├── alembic/                      # Migraciones de base de datos
│   ├── env.py
│   ├── script.py.mako
│   ├── versions/
│   │   ├── 001_initial_migration.py       # Migracion idempotente
│   │   ├── 002_add_fts_search.py          # FTS: tsvector, GIN index, trigger
│   │   └── 003_add_geo_year_to_documents.py  # Zona geo + anio precio
│   └── README.md
│
├── alembic.ini
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── README.md
└── PLAN.md
```

---

## Endpoints de la API

### Documentos
| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload multi-archivo (PDF, TXT, CSV, DOCX, BC3) max 10 |
| GET | `/api/v1/documents` | Listar documentos subidos |
| GET | `/api/v1/documents/{id}` | Obtener metadata de documento |
| GET | `/api/v1/documents/{id}/status` | Estado de procesamiento (polling) |
| DELETE | `/api/v1/documents/{id}` | Eliminar documento del sistema |
| POST | `/api/v1/documents/{id}/reindex` | Re-indexar documento |

### Base de Conocimiento
| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/v1/knowledge/search` | Busqueda semantica (sin LLM) |
| GET | `/api/v1/knowledge/chunks/{document_id}` | Ver chunks de un documento |
| GET | `/api/v1/knowledge/stats` | Estadisticas de la base |

### Consultas RAG
| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| POST | `/api/v1/rag/query` | Consulta RAG con Gemini |
| POST | `/api/v1/rag/generate-bc3` | Generar BC3 desde partidas buscadas |
| POST | `/api/v1/rag/download-bc3` | Descargar archivo BC3 generado |

### Sistema
| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/health` | Health check |

---

## Tipos de Documentos Soportados

| Tipo | Extensiones | Procesador | Estrategia de chunking |
|------|-------------|------------|------------------------|
| PDF | `.pdf` | pdfplumber | Por pagina, tablas como markdown, filtro boilerplate |
| Texto | `.txt`, `.md` | Parser nativo | Por tamano (chunk_size/chunk_overlap) |
| CSV/Excel | `.csv`, `.xlsx`, `.xls` | pandas | 1 fila = 1 chunk |
| Word | `.docx` | python-docx | Por parrafo |
| BC3 | `.bc3` | Parser FIEBDC-3 propio | 1 concepto = 1 chunk |

---

## Flujo RAG

1. **Upload** - El usuario sube documentos via API (con metadatos opcionales: zona geo, anio precio)
2. **Procesamiento** (background) - Se extrae texto segun el tipo de archivo
3. **Chunking** - Se divide en fragmentos de 1000 chars con overlap de 100 (pagina, fila, codigo BC3)
4. **Embeddings** - Se generan vectores con paraphrase-multilingual-MiniLM-L12-v2
5. **FTS** - Se genera tsvector automaticamente via trigger PostgreSQL
6. **Almacenamiento** - Vectores en PostgreSQL + pgvector, tsvector con indice GIN
7. **Consulta** - El usuario hace una pregunta (con session_id para memoria)
8. **Busqueda hibrida** - Vector (semantica) + FTS (exacta) fusionadas con RRF (k=60)
9. **Filtrado por score** - Solo resultados con score >= min_score (default 0.5)
10. **Si hay resultados**: Contexto + LLM a temperature 0.1 → respuesta precisa
11. **Si NO hay resultados**: LLM genera estimacion de mercado a temperature 0.15 + disclaimer
12. **Memoria** - Se guarda el intercambio en el historial de sesion (in-memory, TTL 2h)
13. **Respuesta** - Se devuelve respuesta + fuentes + session_id al usuario

---

## Flujo BC3

### Importacion (BC3 -> RAG)
1. Upload de archivo `.bc3` por endpoint normal de documentos
2. Parser lee el archivo (latin-1/cp1252) y extrae registros ~C, ~D, ~T, ~L
3. Formato ~C: `~C|CODIGO|UNIDAD|RESUMEN|PRECIO|FECHA|FLAGS|`
4. Cada concepto genera 1 chunk con texto estructurado: codigo, unidad, precio, descripcion y descomposicion
5. Se generan embeddings normalmente
6. Verificado con preciarios reales (854 conceptos -> 854 chunks)

### Generacion (RAG -> BC3)
1. El usuario envia lista de partidas a buscar
2. Se busca cada partida por busqueda hibrida (vector + FTS)
3. Se extraen codigo, precio, unidad de cada resultado
4. Codigos duplicados se resuelven con sufijo numerico automatico
5. Partidas sin precio se enriquecen con estimacion LLM en paralelo
6. Se genera archivo BC3 valido compatible con Presto:
   - Registros ~V (version), ~K (coeficientes), ~C (conceptos), ~T (textos), ~M (mediciones), ~D (descomposicion)
   - Jerarquia: PROY## > CAP01# > partidas (con ~D para cada nivel)
   - Encoding Latin-1 (ISO-8859-1) + line endings CRLF
   - Caracteres unicode (²,³) reemplazados a ASCII (2,3)
7. La descarga genera un filename descriptivo: `{proyecto}_{fecha}.bc3`

---

## Lista de Tareas

- [x] Crear estructura del proyecto FastAPI modular
- [x] Configurar PostgreSQL con extension pgvector
- [x] Implementar modelos SQLAlchemy con SQLAlchemy 2.0
- [x] Crear processors para PDF, TXT, CSV, DOCX
- [x] Implementar pipeline de embeddings con sentence-transformers
- [x] Desarrollar endpoints REST con soporte drag & drop
- [x] Implementar sistema de barra de progreso (polling + porcentaje)
- [x] Desarrollar endpoints para consultas RAG con Gemini
- [x] Implementar sistema de busqueda semantica (vector + metadatos)
- [x] Agregar configuracion con .env y validaciones
- [x] Documentar API con Swagger/OpenAPI
- [x] Crear docker-compose para despliegue
- [x] Cambiar modelo de embeddings a multilingue (paraphrase-multilingual-MiniLM-L12-v2)
- [x] Mejorar extraccion PDF (tablas markdown, filtro boilerplate)
- [x] Implementar retry con backoff para Gemini (429 rate limit)
- [x] Hacer migraciones Alembic idempotentes
- [x] Implementar parser BC3/FIEBDC-3
- [x] Implementar generacion de archivos BC3 desde consultas RAG
- [x] Implementar estimacion de precio de mercado (fallback sin contexto)
- [x] Implementar busqueda hibrida (vectorial + FTS + RRF)
- [x] Implementar memoria de conversacion por sesion (in-memory)
- [x] Enriquecer BC3 con LLM para partidas sin precio
- [x] Metadatos extendidos (zona geografica + anio de precio)
- [x] Temperature baja para precios consistentes
- [x] Chunk size optimizado (1000 chars, overlap 100)
- [x] Crear tests unitarios (172 tests: config, schemas, session, processors, BC3, RRF)
- [x] BC3 compatible con Presto (registros ~K, ~M, ~D raiz, CRLF, Latin-1, sin duplicados)
- [ ] Implementar autenticacion (API Keys / JWT)

---

## Configuracion de Variables de Entorno

```env
# Base de datos
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/rag_presupuestos
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:postgres@db:5432/rag_presupuestos

# Google Gemini (modelo SOLO se cambia aqui)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_TOKENS=8192

# Embeddings
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSIONS=384
DEVICE=cpu

# API
API_HOST=0.0.0.0
API_PORT=8000
MAX_FILE_SIZE_MB=50
ALLOWED_EXTENSIONS=pdf,txt,csv,docx,xlsx,bc3

# Procesamiento
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
```

---

*Documento actualizado el 21/02/2026*
