# RAG para Presupuestos de Obra

Sistema RAG (Retrieval Augmented Generation) para crear presupuestos de obra con base de conocimiento.

## Descripcion

Este proyecto permite crear un sistema de conocimiento para presupuestos de construccion. Los usuarios pueden subir documentos (PDF, TXT, CSV, DOCX, BC3) que se procesan para generar embeddings y permitir busquedas semanticas.

El sistema usa **Google Gemini** como LLM para generar respuestas precisas basadas en los documentos subidos, actuando como un arquitecto tecnico colegiado con experiencia en el sector de la construccion en Espana.

## Caracteristicas

- Upload de archivos con soporte drag & drop (max 10 por subida)
- Procesamiento automatico de documentos (PDF, TXT, CSV, DOCX, BC3/FIEBDC-3)
- Extraccion de tablas de PDF como markdown
- Filtrado de boilerplate en PDFs para mejorar calidad de embeddings
- Busqueda semantica usando embeddings vectoriales multilingues
- Consultas RAG con Google Gemini (retry automatico ante rate limiting)
- Generacion de archivos BC3 a partir de consultas RAG
- Barra de progreso en tiempo real
- API REST completa con FastAPI
- Docker para despliegue con hot-reload en desarrollo

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| API | FastAPI |
| Base de datos | PostgreSQL + pgvector 0.2.5 |
| ORM | SQLAlchemy 2.0 (async) |
| LLM | Google Gemini (modelo configurable en .env) |
| Embeddings | sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2) |
| Migraciones | Alembic (idempotentes) |
| Contenedores | Docker Compose |

## Estructura del Proyecto

```
RAG_construccion/
├── app/
│   ├── api/
│   │   ├── dependencies.py        # Dependencias FastAPI (sesion BD)
│   │   └── routes/
│   │       ├── documents.py       # Endpoints de documentos
│   │       ├── rag.py             # Endpoints RAG + generacion BC3
│   │       └── knowledge.py       # Busqueda y estadisticas
│   ├── core/
│   │   ├── models/                # Modelos SQLAlchemy
│   │   │   ├── base.py            # Base, UUIDMixin, TimestampMixin
│   │   │   ├── document.py        # Modelo Document
│   │   │   ├── chunk.py           # Modelo Chunk
│   │   │   └── embedding.py       # Modelo Embedding (pgvector)
│   │   ├── schemas/               # Schemas Pydantic
│   │   │   ├── document.py        # Schemas de documentos
│   │   │   ├── query.py           # Schemas de consultas y BC3
│   │   │   └── response.py        # Schemas de respuestas
│   │   └── services/              # Logica de negocio
│   │       ├── document_service.py      # Procesamiento de documentos
│   │       ├── vector_search_service.py # Busqueda vectorial
│   │       ├── rag_service.py           # Orquestacion RAG
│   │       └── bc3_generator.py         # Generacion de archivos BC3
│   ├── database/
│   │   └── connection.py          # Conexion async/sync SQLAlchemy
│   ├── embeddings/
│   │   └── encoder.py             # Wrapper sentence-transformers
│   ├── llm/
│   │   ├── base.py                # Clase abstracta LLMClient
│   │   ├── gemini_client.py       # Implementacion Google Gemini
│   │   └── factory.py             # Factory para clientes LLM
│   ├── processors/
│   │   ├── base.py                # Clase abstracta Processor
│   │   ├── pdf_processor.py       # Procesador PDF (tablas + boilerplate)
│   │   ├── txt_processor.py       # Procesador TXT/MD
│   │   ├── csv_processor.py       # Procesador CSV/XLSX
│   │   ├── docx_processor.py      # Procesador DOCX
│   │   └── bc3_processor.py       # Procesador BC3/FIEBDC-3
│   ├── config.py                  # Configuracion (pydantic-settings)
│   ├── logging_config.py          # Configuracion de loguru
│   └── main.py                    # Punto de entrada FastAPI
├── alembic/                       # Migraciones de BD (idempotentes)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_migration.py
├── alembic.ini                    # Configuracion Alembic
├── docker-compose.yml             # Orquestacion Docker
├── Dockerfile                     # Imagen de la API (PyTorch CPU-only)
├── requirements.txt               # Dependencias Python
├── .env.example                   # Plantilla de variables de entorno
└── PLAN.md                        # Plan tecnico del proyecto
```

## Inicio Rapido

### Prerrequisitos

- Python 3.11+
- PostgreSQL con extension pgvector
- Docker y Docker Compose (recomendado)
- API Key de Google Gemini

### Instalacion con Docker

1. Clonar el repositorio
2. Configurar `.env`:
```env
GEMINI_API_KEY=tu_api_key_de_gemini
```

3. Ejecutar:
```bash
docker-compose up -d --build
```

4. Verificar:
```bash
curl http://localhost:8000/health
```

**Nota:** El contenedor tiene hot-reload activado. Los cambios en codigo Python se aplican automaticamente. Solo necesitas reconstruir (`--build`) cuando cambies `requirements.txt` o `Dockerfile`.

### Instalacion Local

1. Crear entorno virtual:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

2. Instalar PyTorch CPU y dependencias:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

3. Configurar `.env` con tus credenciales

4. Iniciar PostgreSQL con pgvector

5. Aplicar migraciones:
```bash
alembic upgrade head
```

6. Ejecutar la API:
```bash
uvicorn app.main:app --reload
```

---

## Documentacion de la API

La API dispone de documentacion interactiva en:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints de Documentos

#### 1. Subir Documento

```
POST /api/v1/documents/upload
```

Sube uno o multiples archivos al sistema (max 10 por subida). El procesamiento se hace en background.

**Rate Limit:** 10 solicitudes por minuto

**Parametros (multipart/form-data):**

| Campo | Tipo | Requerido | Descripcion |
|-------|------|-----------|-------------|
| files | File | Si | Archivos a subir (max 10) |
| metadata | JSON | No | Metadatos del documento |

**Formatos soportados:** PDF, TXT, CSV, DOCX, XLSX, BC3

**Metadatos opcionales:**
```json
{
  "tipo": "catalogo|precio_unitario|norma_tecnica|especificacion",
  "categoria": "residencial|comercial|industrial|infraestructura",
  "fecha_vigencia": "2024-01-01",
  "proveedor": "Nombre del proveedor"
}
```

**Ejemplo:**
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "files=@documento.pdf" \
  -F "files=@precios.bc3"
```

**Response (200):**
```json
{
  "total": 2,
  "results": [
    {
      "document_id": "uuid-del-documento",
      "filename": "documento.pdf",
      "status": "pending",
      "message": "Documento subido. Procesamiento en background."
    },
    {
      "document_id": "uuid-del-documento-2",
      "filename": "precios.bc3",
      "status": "pending",
      "message": "Documento subido. Procesamiento en background."
    }
  ]
}
```

---

#### 2. Listar Documentos

```
GET /api/v1/documents
```

Lista documentos con paginacion.

**Rate Limit:** 30 solicitudes por minuto

**Parametros (query):**

| Campo | Tipo | Default | Descripcion |
|-------|------|---------|-------------|
| skip | int | 0 | Registros a omitir |
| limit | int | 20 | Limite de registros (max 100) |
| status | string | null | Filtrar por estado |

**Estados posibles:** `pending`, `processing`, `completed`, `failed`

---

#### 3. Obtener Documento

```
GET /api/v1/documents/{document_id}
```

Obtiene los detalles de un documento especifico.

---

#### 4. Estado de Procesamiento

```
GET /api/v1/documents/{document_id}/status
```

Obtiene el estado de procesamiento de un documento. Util para polling desde el frontend.

**Flujo de Estados:**
```
pending -> processing -> completed
                     \-> failed
```

---

#### 5. Eliminar Documento

```
DELETE /api/v1/documents/{document_id}
```

Elimina un documento y todos sus datos asociados (chunks, embeddings, archivo fisico).

**Rate Limit:** 10 solicitudes por minuto

---

#### 6. Re-indexar Documento

```
POST /api/v1/documents/{document_id}/reindex
```

Re-procesa un documento y regenera sus embeddings.

**Rate Limit:** 5 solicitudes por minuto

---

### Endpoints de Base de Conocimiento

#### 1. Busqueda Semantica

```
GET /api/v1/knowledge/search
```

Busca en la base de conocimiento sin usar LLM. Util para previsualizar que documentos serian recuperados.

**Rate Limit:** 30 solicitudes por minuto

**Parametros:**

| Campo | Tipo | Default | Descripcion |
|-------|------|---------|-------------|
| query | string | Requerido | Texto de busqueda |
| max_results | int | 10 | Max resultados (max 50) |

---

#### 2. Estadisticas

```
GET /api/v1/knowledge/stats
```

Obtiene estadisticas de la base de conocimiento (documentos, chunks, embeddings, por tipo y categoria).

---

#### 3. Ver Chunks de Documento

```
GET /api/v1/knowledge/chunks/{document_id}
```

Obtiene los chunks de un documento especifico.

---

### Endpoints RAG

#### 1. Consulta RAG

```
POST /api/v1/rag/query
```

Realiza una consulta al sistema RAG. El sistema busca fragmentos relevantes y genera una respuesta usando Google Gemini como un arquitecto tecnico colegiado.

**Rate Limit:** 20 solicitudes por minuto

**Request Body:**
```json
{
  "query": "precio del pavimento flotante laminado",
  "max_results": 5,
  "include_sources": true
}
```

**Parametros:**

| Campo | Tipo | Default | Descripcion |
|-------|------|---------|-------------|
| query | string | Requerido | Pregunta del usuario (max 5000 chars) |
| max_results | int | 5 | Documentos a recuperar (max 20) |
| filters | object | null | Filtros por metadatos |
| include_sources | bool | true | Incluir fragmentos fuente |

La respuesta incluye desglose de partidas (material, mano de obra, instalacion), sugerencias de alternativas cuando no se encuentra exactamente lo solicitado, y referencias a las normativas vigentes (CTE, LOE, RITE, RIPCI, RSIF, EHE-08, EAE, REBT).

---

#### 2. Generar BC3

```
POST /api/v1/rag/generate-bc3
```

Genera un archivo BC3/FIEBDC-3 a partir de partidas buscadas en la base de conocimiento.

**Rate Limit:** 10 solicitudes por minuto

**Request Body:**
```json
{
  "queries": [
    "pavimento flotante laminado",
    "tabiqueria de pladur",
    "instalacion electrica vivienda"
  ],
  "project_name": "Reforma vivienda",
  "max_results_per_query": 3
}
```

**Parametros:**

| Campo | Tipo | Default | Descripcion |
|-------|------|---------|-------------|
| queries | list[string] | Requerido | Partidas a buscar (max 50) |
| max_results_per_query | int | 3 | Resultados por busqueda (max 10) |
| project_name | string | "Presupuesto generado" | Nombre del proyecto en cabecera BC3 |

**Response:**
```json
{
  "bc3_content": "~V|FIEBDC-3/2020|...",
  "total_items": 5,
  "queries_processed": 3
}
```

---

#### 3. Descargar BC3

```
POST /api/v1/rag/download-bc3
```

Genera y descarga directamente un archivo `.bc3`. Mismos parametros que `generate-bc3` pero devuelve el archivo como descarga.

**Rate Limit:** 10 solicitudes por minuto

---

### Endpoints de Sistema

#### Health Check

```
GET /health
```

Verifica que la API este funcionando. Devuelve `{"status": "healthy", "version": "1.0.0"}`.

---

## Formatos de Documento Soportados

| Tipo | Extensiones | Procesador | Notas |
|------|-------------|------------|-------|
| PDF | `.pdf` | pdfplumber | Extrae texto + tablas como markdown, filtra boilerplate |
| Texto | `.txt`, `.md` | Parser nativo | UTF-8 y Latin-1 |
| CSV/Excel | `.csv`, `.xlsx`, `.xls` | pandas | 1 fila = 1 chunk |
| Word | `.docx` | python-docx | Extrae texto |
| BC3 | `.bc3` | Parser FIEBDC-3 | 1 concepto = 1 chunk con codigo, precio, descomposicion |

### Formato BC3/FIEBDC-3

El sistema soporta archivos BC3, el estandar espanol (FIEBDC-3) para intercambio de bases de datos de construccion. Compatible con archivos generados por Presto, Arquimedes, TCQ y otros programas de mediciones.

Registros soportados:

- `~V` - Version del formato y software origen
- `~C` - Conceptos: `~C|CODIGO|UNIDAD|RESUMEN|PRECIO|FECHA|FLAGS|`
- `~D` - Descomposicion de conceptos (componentes con cantidades)
- `~T` - Textos descriptivos largos
- `~L` - Jerarquia (capitulos/subcapitulos)
- `~K` - Configuracion (moneda, decimales)

Cada concepto se convierte en un chunk independiente con formato estructurado:
```
Codigo: 01003
Concepto: Demolicion de forjado metalico
Unidad: m2
Precio: 71.86 EUR
Descripcion: [texto largo del registro ~T]
Descomposicion:
  - MAT001 | Martillo neumatico | Cantidad: 0.5 | Precio: 12.30 EUR
  - MO001 | Peon especializado | Cantidad: 1.0 | Precio: 22.50 EUR
```

Esto permite que la busqueda semantica encuentre partidas tanto por nombre ("demolicion forjado") como por tipo de trabajo o material.

---

## Codigos de Estado HTTP

| Codigo | Descripcion |
|--------|-------------|
| 200 | Exito |
| 400 | Bad Request - Error en parametros o upload |
| 404 | No encontrado |
| 422 | Validation Error |
| 429 | Rate Limit excedido |
| 500 | Error interno del servidor |

---

## Rate Limits

| Endpoint | Limite |
|----------|--------|
| `/api/v1/documents/upload` | 10/min |
| `/api/v1/documents` (GET) | 30/min |
| `/api/v1/documents/{id}` (DELETE) | 10/min |
| `/api/v1/documents/{id}/reindex` | 5/min |
| `/api/v1/rag/query` | 20/min |
| `/api/v1/rag/generate-bc3` | 10/min |
| `/api/v1/rag/download-bc3` | 10/min |
| `/api/v1/knowledge/*` | 30/min |

---

## Configuracion

Variables de entorno principales (ver `.env.example` para la lista completa):

```env
# Base de datos
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/rag_presupuestos
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:postgres@db:5432/rag_presupuestos

# Google Gemini
GEMINI_API_KEY=tu_api_key
GEMINI_MODEL=gemini-2.5-pro
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_TOKENS=2048

# Embeddings
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSIONS=384

# Upload
MAX_FILE_SIZE_MB=50
ALLOWED_EXTENSIONS=pdf,txt,csv,docx,xlsx,bc3
```

**Importante:** El modelo de Gemini se define exclusivamente en el `.env`. El codigo siempre usa el modelo configurado ahi, sin excepciones.

---

## Licencia

MIT License
