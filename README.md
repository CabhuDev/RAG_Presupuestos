# 🏗️ RAG para Presupuestos de Obra

Sistema RAG (Retrieval Augmented Generation) para crear presupuestos de obra con base de conocimiento.

## 📋 Descripción

Este proyecto permite crear un sistema de conocimiento para presupuestos de construcción. Los usuarios pueden subir documentos (PDF, TXT, CSV, DOCX) que se procesan para generar embeddings y permitir búsquedas semánticas.

El sistema usa **Google Gemini** como LLM para generar respuestas precisas basadas en los documentos subidos.

## 🚀 Características

- 📤 **Upload de archivos** con soporte drag & drop
- 📊 **Procesamiento automático** de documentos (PDF, TXT, CSV, DOCX)
- 🔍 **Búsqueda semántica** usando embeddings vectoriales
- 🤖 **Consultas RAG** con Google Gemini
- 📈 **Barra de progreso** en tiempo real
- 🔄 **API REST** completa con FastAPI
- 🐳 **Docker** para despliegue

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| API | FastAPI |
| Base de datos | PostgreSQL + pgvector |
| ORM | SQLAlchemy 2.0 |
| LLM | Google Gemini |
| Embeddings | sentence-transformers |

## 📦 Estructura del Proyecto

```
RAG_construccion/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── documents.py    # Endpoints de documentos
│   │       ├── rag.py         # Endpoints RAG
│   │       └── knowledge.py   # Búsqueda y estadísticas
│   ├── core/
│   │   ├── models/            # Modelos SQLAlchemy
│   │   ├── schemas/           # Schemas Pydantic
│   │   └── services/          # Lógica de negocio
│   ├── database/              # Conexión a BD
│   ├── embeddings/            # Módulo de embeddings
│   ├── llm/                   # Cliente LLM
│   ├── processors/            # Procesadores de documentos
│   ├── config.py              # Configuración
│   └── main.py                # Punto de entrada
├── alembic/                   # Migraciones
├── scripts/                   # Scripts utilitarios
├── docker-compose.yml         # Orquestación Docker
├── Dockerfile                 # Imagen de la API
├── requirements.txt           # Dependencias Python
└── .env                       # Variables de entorno
```

## ⚡ Inicio Rápido

### Prerrequisitos

- Python 3.11+
- PostgreSQL con extensión pgvector
- Docker y Docker Compose (opcional)
- API Key de Google Gemini

### Instalación con Docker

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

### Instalación Local

1. Crear entorno virtual:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

2. Instalar dependencias:
```bash
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

## 📚 Documentación Completa de la API

La API dispone de documentación interactiva en:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 🔴 Endpoints de Documentos

#### 1. Subir Documento

```
POST /api/v1/documents/upload
```

**Descripción:** Sube uno o múltiples archivos al sistema. El procesamiento se hace en background.

**Rate Limit:** 10 solicitudes por minuto

**Parámetros (multipart/form-data):**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| files | File | Sí | Archivos a subir (máx 10) |
| metadata | JSON | No | Metadatos del documento |

**Metadatos opcionales:**
```json
{
  "tipo": "catalogo|precio_unitario|norma_tecnica|especificacion",
  "categoria": "residencial|comercial|industrial|infraestructura",
  "fecha_vigencia": "2024-01-01",
  "proveedor": "Nombre del proveedor"
}
```

**Ejemplo de Request:**
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "files=@documento.pdf" \
  -F 'metadata={"tipo": "catalogo", "categoria": "residencial"}'
```

**Response (200):**
```json
{
  "document_id": "uuid-del-documento",
  "filename": "documento.pdf",
  "status": "pending",
  "message": "Documento subido. Procesamiento en background."
}
```

---

#### 2. Listar Documentos

```
GET /api/v1/documents
```

**Descripción:** Lista documentos con paginación.

**Rate Limit:** 30 solicitudes por minuto

**Parámetros (query):**

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| skip | int | 0 | Registros a omitir |
| limit | int | 20 | Límite de registros (máx 100) |
| status | string | null | Filtrar por estado |

**Estados posibles:** `pending`, `processing`, `completed`, `failed`

**Ejemplo:**
```bash
curl "http://localhost:8000/api/v1/documents?limit=10&status=completed"
```

**Response (200):**
```json
{
  "total": 5,
  "items": [
    {
      "id": "uuid",
      "filename": "documento.pdf",
      "status": "completed",
      "progress": 100,
      "chunk_count": 45,
      "embedding_count": 45,
      "created_at": "2024-01-01T12:00:00Z"
    }
  ]
}
```

---

#### 3. Obtener Documento

```
GET /api/v1/documents/{document_id}
```

**Descripción:** Obtiene los detalles de un documento específico.

**Ejemplo:**
```bash
curl http://localhost:8000/api/v1/documents/{uuid}
```

---

#### 4. Estado de Procesamiento

```
GET /api/v1/documents/{document_id}/status
```

**Descripción:** Obtiene el estado de procesamiento de un documento. Útil para polling desde el frontend.

**Ejemplo de Response:**
```json
{
  "document_id": "uuid",
  "status": "processing",
  "progress": 50,
  "message": "Generando embeddings...",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:05:00Z"
}
```

**Flujo de Estados:**
```
pending → processing → completed
                    ↓
                  failed
```

---

#### 5. Eliminar Documento

```
DELETE /api/v1/documents/{document_id}
```

**Descripción:** Elimina un documento y todos sus datos asociados (chunks, embeddings).

**Ejemplo:**
```bash
curl -X DELETE http://localhost:8000/api/v1/documents/{uuid}
```

**Response (200):**
```json
{
  "document_id": "uuid",
  "message": "Documento eliminado correctamente"
}
```

---

#### 6. Re-indexar Documento

```
POST /api/v1/documents/{document_id}/reindex
```

**Descripción:** Re-procesa un documento y regenera sus embeddings.

**Rate Limit:** 5 solicitudes por minuto

---

### 🔵 Endpoints de Base de Conocimiento

#### 1. Búsqueda Semántica

```
GET /api/v1/knowledge/search
```

**Descripción:** Busca en la base de conocimiento sin usar LLM. Útil para previsualizar qué documentos serían recuperados.

**Parámetros:**

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| query | string | Requerido | Texto de búsqueda |
| max_results | int | 10 | Máx resultados (máx 50) |

**Ejemplo:**
```bash
curl "http://localhost:8000/api/v1/knowledge/search?query=precio%20cemento&max_results=5"
```

**Response:**
```json
{
  "query": "precio cemento",
  "total_results": 3,
  "results": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "filename": "catalogo_precios.pdf",
      "content": "Cemento Portland tipo I...",
      "score": 0.95,
      "source_page": 5
    }
  ]
}
```

---

#### 2. Estadísticas

```
GET /api/v1/knowledge/stats
```

**Descripción:** Obtiene estadísticas de la base de conocimiento.

**Response:**
```json
{
  "total_documents": 10,
  "total_chunks": 450,
  "total_embeddings": 450,
  "by_type": {
    "catalogo": 5,
    "precio_unitario": 3,
    "norma_tecnica": 2
  },
  "by_category": {
    "residencial": 6,
    "comercial": 4
  }
}
```

---

#### 3. Ver Chunks de Documento

```
GET /api/v1/knowledge/chunks/{document_id}
```

**Descripción:** Obtiene los chunks de un documento específico.

---

### 🟢 Endpoints RAG

#### 1. Consulta RAG

```
POST /api/v1/rag/query
```

**Descripción:** Realiza una consulta al sistema RAG. El sistema busca fragmentos relevantes y genera una respuesta usando Google Gemini.

**Rate Limit:** 20 solicitudes por minuto

**Request Body:**
```json
{
  "query": "¿Cuál es el precio del cemento tipo I?",
  "max_results": 5,
  "filters": {
    "document_type": "catalogo"
  },
  "include_sources": true
}
```

**Parámetros:**

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| query | string | Requerido | Pregunta del usuario (máx 5000 chars) |
| max_results | int | 5 | Documentos a recuperar (máx 20) |
| filters | object | null | Filtros por metadatos |
| include_sources | bool | true | Incluir fragmentos fuente |

**Ejemplo:**
```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "¿Cuál es el precio del cemento?", "max_results": 5}'
```

**Response:**
```json
{
  "query": "¿Cuál es el precio del cemento?",
  "answer": "Según el catálogo de precios 2024, el cemento Portland tipo I tiene un precio de $12.50 por saco de 50kg.",
  "sources": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "filename": "catalogo_precios_2024.pdf",
      "content": "Cemento Portland tipo I - Precio: $12.50/saco",
      "score": 0.92,
      "source_page": 15
    }
  ],
  "metadata": {
    "results_count": 5,
    "max_score": 0.92
  }
}
```

---

### ⚪ Endpoints de Sistema

#### Health Check

```
GET /health
```

**Descripción:** Verifica que la API esté funcionando.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## 📋 Códigos de Estado HTTP

| Código | Descripción |
|--------|-------------|
| 200 | Éxito |
| 201 | Creado |
| 400 | Bad Request - Error en parámetros |
| 404 | No encontrado |
| 422 | Validation Error |
| 429 | Rate Limit excedido |
| 500 | Error interno del servidor |

---

## 🛡️ Rate Limits

| Endpoint | Límite |
|----------|--------|
| `/api/v1/documents/upload` | 10/min |
| `/api/v1/documents` | 30/min |
| `/api/v1/rag/query` | 20/min |
| `/api/v1/knowledge/*` | 30/min |

---

## 🔧 Uso del Frontend

### Ejemplo: Upload con JavaScript

```javascript
// Subir archivo
async function uploadFile(file, metadata = {}) {
  const formData = new FormData();
  formData.append('files', file);
  
  if (Object.keys(metadata).length > 0) {
    formData.append('metadata', JSON.stringify(metadata));
  }
  
  const response = await fetch('/api/v1/documents/upload', {
    method: 'POST',
    body: formData
  });
  
  const result = await response.json();
  
  if (result.status === 'failed') {
    console.error('Error:', result.message);
    return null;
  }
  
  // Polling para estado
  return pollStatus(result.document_id);
}

// Polling de estado
async function pollStatus(documentId, onProgress) {
  while (true) {
    const response = await fetch(`/api/v1/documents/${documentId}/status`);
    const status = await response.json();
    
    onProgress(status);
    
    if (status.status === 'completed' || status.status === 'failed') {
      return status;
    }
    
    await new Promise(r => setTimeout(r, 2000));
  }
}

// Uso
const fileInput = document.querySelector('#file');
const file = fileInput.files[0];

await uploadFile(file, { tipo: 'catalogo', categoria: 'residencial' }, 
  (status) => console.log(`Progreso: ${status.progress}%`)
);
```

### Ejemplo: Consulta RAG

```javascript
async function askQuestion(question) {
  const response = await fetch('/api/v1/rag/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: question,
      max_results: 5,
      include_sources: true
    })
  });
  
  const result = await response.json();
  
  console.log('Respuesta:', result.answer);
  console.log('Fuentes:', result.sources);
  
  return result;
}

// Uso
const result = await askQuestion('¿Cuál es el precio del cemento?');
```

---

## 📝 Configuración

Ver `.env.example` para todas las variables de entorno:

```env
# Base de datos
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rag_presupuestos

# Google Gemini
GEMINI_API_KEY=tu_api_key
GEMINI_MODEL=gemini-1.5-pro
GEMINI_TEMPERATURE=0.7

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2

# API
MAX_FILE_SIZE_MB=50
ALLOWED_EXTENSIONS=pdf,txt,csv,docx,xlsx
```

---

## 📄 Licencia

MIT License
