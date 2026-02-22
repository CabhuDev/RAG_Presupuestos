# Plan de Mejoras — RAG Presupuestos de Obra v2.0

*Documento generado tras auditoría técnica completa del sistema.*
*Versión API: 1.0.0 → 2.0.0*

---

## Resumen de mejoras implementadas

| Bloque | Mejora | Impacto |
|--------|--------|---------|
| 1 | Score mínimo en búsqueda + Precio crítico de mercado | Crítico |
| 2 | Temperature 0.1 para respuestas de precio | Alto |
| 3 | Memoria de conversación por sesión (in-memory) | Alto |
| 4 | Búsqueda híbrida: Vectorial + PostgreSQL FTS | Alto |
| 5 | Chunk size aumentado a 1000 caracteres | Medio |
| 6 | Metadatos extendidos: zona geográfica + año de precio | Medio |
| 7 | Enriquecimiento BC3 con LLM para partidas sin precio | Medio |
| 8 | Correcciones menores: asyncio, SQL, modelo Gemini | Bajo |

---

## BLOQUE 1 — Score mínimo + Precio crítico de mercado

**Problema resuelto:** El sistema devolvía "No se encontró información" y se detenía cuando no había contexto en la BD. La característica diferencial (estimación de mercado justificada) no estaba implementada.

**Archivos modificados:**
- `app/core/services/vector_search_service.py` — Parámetro `min_score` en `search()`
- `app/core/services/rag_service.py` — Fallback al modo estimación de mercado
- `app/llm/gemini_client.py` — Nuevo método `generate_market_price_estimate()`
- `app/core/schemas/query.py` — Campo `min_score` en `RAGQueryRequest`
- `app/api/routes/rag.py` — Propagación del campo

**Comportamiento nuevo:**
- Si los resultados vectoriales tienen score < `min_score` (default 0.5): se filtran
- Si no hay resultados útiles: el LLM genera una estimación de mercado a temperature=0.15
- La respuesta incluye un aviso claro: `⚠️ ESTIMACIÓN DE MERCADO` con disclaimer
- El campo `metadata.is_market_estimate: true` permite al frontend mostrar el aviso visualmente

---

## BLOQUE 2+8 — Correcciones de temperature, asyncio y modelo

**Problema resuelto:** Temperature 0.7 generaba precios inconsistentes entre consultas. El `asyncio.create_task` fallaba silenciosamente. Inconsistencia del modelo Gemini entre PLAN.md y config.

**Archivos modificados:**
- `app/llm/gemini_client.py` — Temperature por defecto en `generate_with_context()`: 0.7 → 0.1
- `app/api/routes/documents.py` — Callback de error en `asyncio.create_task()`
- `app/config.py` — Modelo Gemini: `gemini-2.5-flash-lite` → `gemini-2.5-flash`, versión API: `1.0.0` → `2.0.0`

---

## BLOQUE 3 — Memoria de conversación por sesión

**Problema resuelto:** Cada consulta era stateless. No era posible mantener un hilo de conversación ("dame el precio de cimentación" → "¿y si cambio a losa?").

**Archivos nuevos/modificados:**
- `app/core/session_store.py` *(nuevo)* — Store in-memory con TTL de 2 horas, máx. 20 mensajes por sesión
- `app/core/services/rag_service.py` — Lectura/escritura del historial
- `app/llm/gemini_client.py` — Historial incluido en el prompt
- `app/core/schemas/query.py` — Campo `session_id` en request y response
- `app/api/routes/rag.py` — Generación de `session_id` si no se proporciona

**Uso desde el frontend:**
1. Primera consulta: no enviar `session_id` → el backend genera uno y lo devuelve
2. Consultas siguientes: enviar el `session_id` recibido → el sistema mantiene contexto
3. El historial se pierde al reiniciar el servidor (diseño deliberado, simple)

---

## BLOQUE 4 — Búsqueda híbrida: Vectorial + PostgreSQL FTS

**Problema resuelto:** La búsqueda puramente vectorial era ciega a códigos BC3 exactos ("E02AM010") y términos técnicos específicos donde la similitud semántica falla.

**Archivos nuevos/modificados:**
- `alembic/versions/002_add_fts_search.py` *(nuevo)* — Columna `tsvector`, índice GIN, trigger automático
- `app/core/models/chunk.py` — Campo `search_vector` mapeado
- `app/core/services/vector_search_service.py` — Método `search_hybrid()` con RRF (Reciprocal Rank Fusion)

**Cómo funciona:**
1. Búsqueda vectorial (semántica) → ranking por coseno
2. FTS con `tsquery('spanish', query)` → ranking por `ts_rank`
3. Fusión RRF: `score = 1/(60 + rank_vectorial) + 1/(60 + rank_fts)`
4. Top N resultados ordenados por score combinado

---

## BLOQUE 5+6 — Chunk size + Metadatos geo/año

**Problema resuelto:** Chunks de 500 caracteres eran insuficientes para partidas de obra completas. Faltaba información de zona geográfica y año de precio para filtrado relevante.

**Archivos modificados:**
- `app/config.py` — `chunk_size`: 500 → 1000, `chunk_overlap`: 50 → 100
- `alembic/versions/003_add_geo_year.py` *(nuevo)* — Columnas `geographic_zone` y `price_year`
- `app/core/models/document.py` — Nuevos campos mapeados
- `app/core/schemas/document.py` — `zona_geografica` y `anio_precio` en `DocumentMetadata`
- `app/core/services/document_service.py` — Mapeo de nuevos campos

**Nota:** Los documentos ya indexados requieren re-indexación manual:
```
POST /api/v1/documents/{id}/reindex
```

**Zonas geográficas válidas:** `nacional`, `andalucia`, `madrid`, `cataluna`, `valencia`, `galicia`, `pais_vasco`, `aragon`, `castilla_leon`, `murcia`, `canarias`, `baleares`

---

## BLOQUE 7 — Enriquecimiento BC3 con LLM

**Problema resuelto:** El generador BC3 producía partidas con precio 0.0 cuando los chunks no tenían formato estructurado.

**Archivos modificados:**
- `app/core/services/bc3_generator.py` — Método `_enrich_item_with_llm()` para estimar precio vía LLM cuando `price == 0.0`

---

## Comandos para aplicar migraciones

```bash
# Dentro del contenedor Docker
docker-compose exec api alembic upgrade head

# O si usas el entorno local
alembic upgrade head
```

---

## Verificación de cambios

| Cambio | Cómo verificar |
|--------|---------------|
| Precio de mercado | Consultar algo NO en la BD → debe responder con desglose + aviso ⚠️ |
| Temperature | Misma consulta 3 veces → precios consistentes |
| Memoria chat | Consulta → seguimiento → debe recordar contexto |
| Búsqueda híbrida | Buscar código BC3 exacto → debe aparecer en resultados |
| Chunk size | Subir doc nuevo → chunks en `/knowledge/chunks/{id}` son más grandes |
| Metadatos | Upload con `zona_geografica: "andalucia"` → aparece en GET documento |
| BC3 LLM | Generar BC3 con partidas sin precio → precios estimados en resultado |

---

*Última actualización: febrero 2026*
