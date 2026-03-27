import os
import hashlib
import aiofiles
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.models.document import Document
from app.schemas.document import DocumentResponse, DocumentListResponse

router = APIRouter()


@router.post("/upload", response_model=List[DocumentResponse])
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    os.makedirs(settings.upload_dir, exist_ok=True)
    uploaded = []

    for file in files:
        content = await file.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File {file.filename} exceeds {settings.max_upload_size_mb}MB limit",
            )

        content_hash = hashlib.sha256(content).hexdigest()
        filepath = os.path.join(settings.upload_dir, f"{content_hash}_{file.filename}")

        async with aiofiles.open(filepath, "wb") as f:
            await f.write(content)

        doc = Document(
            filename=file.filename,
            filepath=filepath,
            file_type=file.content_type,
            file_size=len(content),
            content_hash=content_hash,
            status="uploaded",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        uploaded.append(doc)

    return uploaded


@router.get("/", response_model=DocumentListResponse)
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return DocumentListResponse(documents=docs, total=len(docs))


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if os.path.exists(doc.filepath):
        os.remove(doc.filepath)
    db.delete(doc)
    db.commit()
    return {"detail": "Document deleted"}
