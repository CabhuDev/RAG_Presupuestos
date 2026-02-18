# Migraciones Alembic

Este directorio contiene la configuración para las migraciones de base de datos usando Alembic.

## Estructura

```
alembic/
├── env.py              # Configuración del entorno de migraciones
├── script.py.mako     # Plantilla para nuevos archivos de migración
├── versions/          # Archivos de migración generados
└── README.md         # Este archivo
```

## Configuración

Las migraciones usan la variable de entorno `DATABASE_URL_SYNC` del archivo `.env` de la raíz del proyecto.

## Comandos

### Crear una nueva migración (auto-generate)
```bash
alembic revision --autogenerate -m "Descripción del cambio"
```

### Crear una migración vacía
```bash
alembic revision -m "Descripción del cambio"
```

### Aplicar todas las migraciones
```bash
alembic upgrade head
```

### Aplicar la siguiente migración
```bash
alembic upgrade +1
```

### Revertir la última migración
```bash
alembic downgrade -1
```

### Revertir todas las migraciones
```bash
alembic downgrade base
```

### Ver historial de migraciones
```bash
alembic history --verbose
```

### Ver estado actual
```bash
alembic current
```

## Notas

- La extensión `pgvector` se crea automáticamente en la primera migración
- Los modelos se detectan automáticamente gracias a los imports en `env.py`
