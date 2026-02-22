"""
Servicio de gestión de documentos.
Maneja la subida, procesamiento y almacenamiento de documentos.
"""
import json
import os
import re
import uuid
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.models import Document, Chunk, Embedding
from app.processors import get_processor
from app.embeddings import get_encoder
from loguru import logger


class SecurityError(Exception):
    """Excepción para errores de seguridad."""
    pass


class DocumentService:
    """
    Servicio para gestionar documentos.
    """

    # Tipos MIME permitidos
    ALLOWED_MIME_TYPES = {
        "pdf": "application/pdf",
        "txt": "text/plain",
        "csv": "text/csv",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "bc3": "application/octet-stream",
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitiza el nombre del archivo para prevenir Path Traversal.
        
        Args:
            filename: Nombre del archivo a sanitizar.
            
        Returns:
            Nombre de archivo sanitizado.
            
        Raises:
            SecurityError: Si el filename es sospechoso.
        """
        # Eliminar cualquier path relativo
        filename = filename.replace("..", "")
        filename = filename.replace("/", "")
        filename = filename.replace("\\", "")
        
        # Eliminar caracteres peligrosos
        filename = re.sub(r'[<>:"|?*]', '', filename)
        
        # Eliminar espacios al inicio/final
        filename = filename.strip()
        
        # Verificar que no esté vacío después de sanitizar
        if not filename:
            raise SecurityError("Nombre de archivo inválido")
        
        # Longitud máxima
        if len(filename) > 255:
            filename = filename[:255]
        
        return filename

    def _validate_mime_type(self, extension: str, content_type: str) -> bool:
        """
        Valida que el tipo MIME coincida con la extensión.
        
        Args:
            extension: Extensión del archivo.
            content_type: Tipo MIME declarado.
            
        Returns:
            True si es válido.
        """
        expected_mime = self.ALLOWED_MIME_TYPES.get(extension.lower())
        if not expected_mime:
            return False
        
        # Verificar coincidencia exacta o tipo genérico
        if content_type == expected_mime:
            return True

        # Para text/plain y text/csv aceptamos variaciones
        if expected_mime.startswith("text/") and content_type.startswith("text/"):
            return True

        # BC3 puede llegar como octet-stream o text/plain
        if extension.lower() == "bc3" and content_type in (
            "application/octet-stream", "text/plain",
        ):
            return True

        return False

    def _validate_file_size(self, content: bytes) -> None:
        """
        Valida el tamaño del archivo para prevenir DoS.
        
        Args:
            content: Contenido del archivo.
            
        Raises:
            SecurityError: Si el archivo es demasiado grande.
        """
        max_bytes = self.settings.max_file_size_bytes
        if len(content) > max_bytes:
            raise SecurityError(
                f"Archivo demasiado grande. Máximo: {self.settings.max_file_size_mb}MB"
            )
        
        # Validar tamaño mínimo (archivo no vacío)
        if len(content) == 0:
            raise SecurityError("Archivo vacío")

    async def create_document(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> Document:
        """
        Crea un nuevo documento a partir de un archivo.

        Args:
            filename: Nombre original del archivo.
            content: Contenido del archivo en bytes.
            content_type: Tipo MIME del archivo.
            metadata: Metadatos opcionales del documento.

        Returns:
            Documento creado.
        """
        # 1. Sanitizar filename para prevenir Path Traversal
        safe_filename = self._sanitize_filename(filename)

        # 2. Determinar extensión
        extension = Path(safe_filename).suffix.lower().lstrip(".")

        # 3. Validar extensión
        if extension not in self.settings.allowed_extensions_list:
            raise ValueError(
                f"Extensión no permitida: {extension}. "
                f"Permitidas: {', '.join(self.settings.allowed_extensions_list)}"
            )

        # 4. Validar tipo MIME
        if not self._validate_mime_type(extension, content_type):
            logger.warning(f"Tipo MIME sospechoso: {content_type} para archivo {extension}")

        # 5. Validar tamaño para prevenir DoS
        self._validate_file_size(content)

        # 6. Generar nombre único de archivo (ya usa UUID - seguro)
        storage_filename = f"{uuid.uuid4()}.{extension}"

        # 7. Crear directorio de uploads de forma segura
        upload_dir = Path(self.settings.upload_dir).resolve()
        
        # Verificar que el directorio está dentro del proyecto
        project_root = Path.cwd().resolve()
        if not str(upload_dir).startswith(str(project_root)):
            raise SecurityError("Directorio de upload no permitido")
        
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 8. Guardar archivo
        file_path = upload_dir / storage_filename
        
        # Escribir archivo de forma segura
        try:
            with open(file_path, "wb") as f:
                # Escribir en chunks para archivos grandes
                chunk_size = 8192
                for i in range(0, len(content), chunk_size):
                    f.write(content[i:i+chunk_size])
        except Exception as e:
            if file_path.exists():
                file_path.unlink()
            raise SecurityError(f"Error al guardar archivo: {str(e)}")

        # 9. Crear registro en BD
        document = Document(
            filename=safe_filename,
            storage_filename=storage_filename,
            file_path=str(file_path),
            content_type=content_type,
            file_extension=extension,
            file_size=len(content),
            status="pending",
            progress=0,
        )

        # 10. Agregar metadatos de forma segura
        if metadata:
            # Sanitizar valores de metadatos
            safe_metadata = {}
            for key, value in metadata.items():
                if value and isinstance(value, str):
                    # Limitar longitud y sanitizar
                    safe_value = value[:500].strip()
                    if safe_value:
                        safe_metadata[key] = safe_value
            
            if "tipo" in safe_metadata:
                document.document_type = safe_metadata["tipo"]
            if "categoria" in safe_metadata:
                document.category = safe_metadata["categoria"]
            if "fecha_vigencia" in safe_metadata:
                document.effective_date = safe_metadata["fecha_vigencia"]
            if "proveedor" in safe_metadata:
                document.supplier = safe_metadata["proveedor"]
            if "zona_geografica" in safe_metadata:
                document.geographic_zone = safe_metadata["zona_geografica"]
            if "anio_precio" in safe_metadata:
                try:
                    document.price_year = int(safe_metadata["anio_precio"])
                except (ValueError, TypeError):
                    pass

            document.metadata_json = json.dumps(safe_metadata)

        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)

        logger.info(f"Documento creado: {document.id}")
        return document

    async def get_document(self, document_id: UUID) -> Optional[Document]:
        """
        Obtiene un documento por su ID.

        Args:
            document_id: ID del documento.

        Returns:
            Documento o None si no existe.
        """
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[Document], int]:
        """
        Lista documentos con paginación.

        Args:
            skip: Número de registros a omitir.
            limit: Número máximo de registros.
            status: Filtrar por estado (opcional).

        Returns:
            Tupla (lista de documentos, total).
        """
        query = select(Document)

        if status:
            # Validar status contra valores permitidos
            allowed_statuses = {"pending", "processing", "completed", "failed"}
            if status not in allowed_statuses:
                raise ValueError(f"Status inválido. Permitidos: {allowed_statuses}")
            query = query.where(Document.status == status)

        # Contar total
        from sqlalchemy import func

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar()

        # Obtener documentos
        query = query.order_by(Document.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        documents = list(result.scalars().all())

        return documents, total

    async def update_document_status(
        self,
        document_id: UUID,
        status: str,
        progress: int = 0,
        message: Optional[str] = None,
    ) -> Document:
        """
        Actualiza el estado de procesamiento de un documento.

        Args:
            document_id: ID del documento.
            status: Nuevo estado.
            progress: Porcentaje de progreso (0-100).
            message: Mensaje de estado.

        Returns:
            Documento actualizado.
        """
        # Validar status
        allowed_statuses = {"pending", "processing", "completed", "failed"}
        if status not in allowed_statuses:
            raise ValueError(f"Status inválido: {status}")
        
        # Validar progress
        if not (0 <= progress <= 100):
            raise ValueError("Progress debe estar entre 0 y 100")

        document = await self.get_document(document_id)
        if not document:
            raise ValueError(f"Documento no encontrado: {document_id}")

        document.status = status
        document.progress = progress
        if message:
            # Limitar longitud del mensaje
            document.status_message = message[:500]

        await self.session.commit()
        await self.session.refresh(document)

        return document

    async def delete_document(self, document_id: UUID) -> bool:
        """
        Elimina un documento y sus chunks asociados.

        Args:
            document_id: ID del documento.

        Returns:
            True si se eliminó correctamente.
        """
        document = await self.get_document(document_id)
        if not document:
            return False

        # Eliminar archivo físico de forma segura
        try:
            file_path = Path(document.file_path).resolve()
            # Verificar que el archivo está dentro del directorio de uploads
            upload_dir = Path(self.settings.upload_dir).resolve()
            if file_path.exists() and str(file_path).startswith(str(upload_dir)):
                file_path.unlink()
        except Exception as e:
            logger.error(f"Error al eliminar archivo: {e}")
            # Continuar aunque no se pueda eliminar el archivo físico

        # Eliminar de BD (los chunks se eliminan en cascada)
        await self.session.delete(document)
        await self.session.commit()

        logger.info(f"Documento eliminado: {document_id}")
        return True

    async def process_document(self, document_id: UUID) -> Document:
        """
        Procesa un documento: extrae texto y genera embeddings.

        Args:
            document_id: ID del documento.

        Returns:
            Documento procesado.
        """
        document = await self.get_document(document_id)
        if not document:
            raise ValueError(f"Documento no encontrado: {document_id}")

        try:
            # Actualizar estado a processing
            await self.update_document_status(
                document_id, "processing", 10, "Extrayendo texto..."
            )

            # Obtener procesador
            processor = get_processor(document.file_extension)

            # Procesar archivo
            file_path = Path(document.file_path)
            raw_chunks = processor.process(file_path)

            # Validar que se generaron chunks
            if not raw_chunks:
                raise ValueError("No se pudo extraer contenido del documento")

            # Subdividir chunks grandes según CHUNK_SIZE y CHUNK_OVERLAP
            chunk_size = self.settings.chunk_size
            chunk_overlap = self.settings.chunk_overlap
            split_chunks = []
            for raw_chunk in raw_chunks:
                content = raw_chunk["content"]
                metadata = raw_chunk.get("metadata", {})
                if len(content) <= chunk_size:
                    split_chunks.append(raw_chunk)
                else:
                    # Dividir respetando saltos de línea cuando sea posible
                    start = 0
                    while start < len(content):
                        end = start + chunk_size
                        if end < len(content):
                            # Buscar un salto de línea cercano para cortar limpio
                            newline_pos = content.rfind("\n", start + chunk_size // 2, end)
                            if newline_pos != -1:
                                end = newline_pos + 1
                        fragment = content[start:end].strip()
                        if fragment:
                            split_chunks.append({
                                "content": fragment,
                                "metadata": metadata.copy(),
                            })
                        start = end - chunk_overlap
            raw_chunks = split_chunks

            # Limitar número de chunks para prevenir DoS
            max_chunks = 10000
            if len(raw_chunks) > max_chunks:
                logger.warning(f"Documento muy largo, limitando chunks de {len(raw_chunks)} a {max_chunks}")
                raw_chunks = raw_chunks[:max_chunks]

            # Actualizar progreso
            await self.update_document_status(
                document_id, "processing", 30, "Generando chunks..."
            )

            # Crear chunks en BD
            chunks = []
            for idx, raw_chunk in enumerate(raw_chunks):
                chunk = Chunk(
                    document_id=document.id,
                    chunk_index=idx,
                    content=raw_chunk["content"][:50000],  # Limitar tamaño de chunk
                    metadata_json=json.dumps(raw_chunk.get("metadata", {})),
                    char_count=len(raw_chunk["content"]),
                    token_count=processor.estimate_tokens(raw_chunk["content"]),
                    source_page=raw_chunk.get("metadata", {}).get("page"),
                    source_row=raw_chunk.get("metadata", {}).get("row"),
                )
                chunks.append(chunk)

            self.session.add_all(chunks)
            await self.session.commit()

            # Actualizar conteo
            document.chunk_count = len(chunks)

            # Actualizar progreso
            await self.update_document_status(
                document_id, "processing", 60, "Generando embeddings..."
            )

            # Generar embeddings en batches para evitar consumo excesivo de memoria
            encoder = get_encoder()
            embedding_records = []
            batch_size = 100
            
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                contents = [chunk.content for chunk in batch]
                
                # Verificar que no exceda la memoria
                if len(contents) > batch_size:
                    contents = contents[:batch_size]
                
                embeddings = encoder.encode(contents)
                
                for chunk, embedding_vector in zip(batch, embeddings):
                    embedding_record = Embedding(
                        chunk_id=chunk.id,
                        vector=embedding_vector.tolist(),
                        embedding_model=self.settings.embedding_model,
                        dimensions=len(embedding_vector),
                    )
                    embedding_records.append(embedding_record)
                    chunk.has_embedding = True
                
                # Commit por batch para no consumir mucha memoria
                self.session.add_all(embedding_records)
                await self.session.commit()
                embedding_records = []

            # Actualizar conteo de embeddings
            document.embedding_count = sum(1 for c in chunks if c.has_embedding)

            # Marcar como completado
            await self.update_document_status(
                document_id, "completed", 100, "Procesamiento completado"
            )

            logger.info(
                f"Documento procesado: {document_id}, "
                f"chunks: {len(chunks)}, embeddings: {document.embedding_count}"
            )

            return document

        except Exception as e:
            logger.error(f"Error al procesar documento {document_id}: {e}")
            await self.update_document_status(
                document_id, "failed", 0, str(e)[:500]
            )
            raise
