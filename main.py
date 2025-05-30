from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
import pandas as pd
import os
from datetime import datetime
from typing import Optional
from fuzzywuzzy import fuzz
import logging
from pathlib import Path
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "sqlite:///./research_articles.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    doi = Column(String, index=True)
    title = Column(String, index=True)
    protein_name = Column(String, nullable=True)
    hardness = Column(Boolean, default=False)
    whc = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    file_hash = Column(String, nullable=True)
    source_file = Column(String, nullable=True)

class UploadHistory(Base):
    __tablename__ = "upload_history"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    upload_date = Column(DateTime, default=func.now())
    articles_added = Column(Integer, default=0)
    duplicates_found = Column(Integer, default=0)
    file_size = Column(Integer, default=0)
    total_rows = Column(Integer, default=0)

Base.metadata.create_all(engine)

UPLOAD_DIR = Path("uploads")
EXPORT_DIR = Path("exports")
STATIC_DIR = Path("static")
TEMPLATES_DIR = Path("templates")

for directory in [UPLOAD_DIR, EXPORT_DIR, STATIC_DIR, TEMPLATES_DIR]:
    directory.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def normalize_doi(doi: str) -> str:
    if not doi:
        return ""
    doi = str(doi).strip().lower()
    for prefix in ["https://doi.org/", "http://doi.org/", "doi:", "doi "]:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip()

def advanced_doi_similarity(doi1: str, doi2: str) -> float:
    n1, n2 = normalize_doi(doi1), normalize_doi(doi2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 100.0
    r = fuzz.ratio(n1, n2)
    ts = fuzz.token_sort_ratio(n1, n2)
    tset = fuzz.token_set_ratio(n1, n2)
    return (r * 0.5 + ts * 0.3 + tset * 0.2)

def doi_exists_in_db(session, doi: str, threshold: float = 85.0):
    norm = normalize_doi(doi)
    if not norm:
        return False, None
    for art in session.query(Article).all():
        if art.doi and advanced_doi_similarity(art.doi, norm) > threshold:
            return True, art
    return False, None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    session = Session()
    try:
        stats = {
            "total_articles": session.query(Article).count(),
            "hardness_articles": session.query(Article).filter(Article.hardness == True).count(),
            "whc_articles": session.query(Article).filter(Article.whc == True).count(),
            "unique_dois": session.query(Article.doi).distinct().count()
        }
        return templates.TemplateResponse("index.html", {"request": request, "stats": stats, "recent_uploads": []})
    finally:
        session.close()

@app.post("/check_article")
async def check_article(
    request: Request,
    doi: Optional[str] = Form(None),
    title: Optional[str] = Form(""),
    protein_name: Optional[str] = Form(""),
    hardness: Optional[bool] = Form(False),
    whc: Optional[bool] = Form(False)
):
    session = Session()
    try:
        # Try JSON body as fallback if DOI is missing
        if not doi:
            try:
                data = await request.json()
                doi = data.get("doi", "")
                title = data.get("title", "")
                protein_name = data.get("protein_name", data.get("protein", ""))
                hardness = bool(data.get("hardness", False))
                whc = bool(data.get("whc", False))
            except Exception:
                pass

        if not doi or not normalize_doi(doi):
            return JSONResponse({"status": "error", "message": "❌ DOI is required and must be valid."}, status_code=400)

        is_dup, existing = doi_exists_in_db(session, doi)
        if is_dup:
            return JSONResponse({
                "status": "duplicate",
                "message": f"🔴 Already exists: {existing.title or existing.doi}",
            })
        article = Article(
            doi=normalize_doi(doi),
            title=title.strip() if title else "",
            protein_name=protein_name.strip() if protein_name else "",
            hardness=bool(hardness),
            whc=bool(whc),
            source_file="manual_entry"
        )
        session.add(article)
        session.commit()
        return JSONResponse({"status": "success", "message": "✅ Article successfully saved!", "article_id": article.id})
    except Exception as e:
        session.rollback()
        logger.error(traceback.format_exc())
        return JSONResponse({"status": "error", "message": "❌ Database error: "+str(e)}, status_code=500)
    finally:
        session.close()

@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    session = Session()
    filepath = None
    try:
        if not file.filename:
            return JSONResponse({"status": "error", "message": "❌ No file provided"}, status_code=400)
        ext = file.filename.lower().split('.')[-1]
        if ext not in ['csv', 'xlsx', 'xls']:
            return JSONResponse({"status": "error", "message": "❌ Only CSV/Excel supported"}, status_code=400)
        file_content = await file.read()
        if not file_content:
            return JSONResponse({"status": "error", "message": "❌ File is empty"}, status_code=400)
        filepath = UPLOAD_DIR / file.filename
        with open(filepath, 'wb') as f:
            f.write(file_content)
        if ext == 'csv':
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        if df.empty:
            return JSONResponse({"status": "error", "message": "❌ File contains no data"}, status_code=400)
        def find_col(df, names):
            for n in names:
                for col in df.columns:
                    if col.lower().strip() == n.lower().strip():
                        return col
            return None
        doi_col = find_col(df, ['doi'])
        if not doi_col:
            return JSONResponse({"status": "error", "message": "❌ 'DOI' column not found"}, status_code=400)
        title_col = find_col(df, ['title'])
        protein_col = find_col(df, ['protein_name', 'protein'])
        hardness_col = find_col(df, ['hardness'])
        whc_col = find_col(df, ['whc'])

        added, dup, err = 0, 0, 0
        for idx, row in df.iterrows():
            try:
                doi = row[doi_col]
                if not doi or not normalize_doi(doi):
                    err += 1
                    continue
                if doi_exists_in_db(session, doi)[0]:
                    dup += 1
                    continue
                title = row[title_col] if title_col else ""
                protein = row[protein_col] if protein_col else ""
                hard = bool(row[hardness_col]) if hardness_col else False
                whc = bool(row[whc_col]) if whc_col else False
                session.add(Article(
                    doi=normalize_doi(doi),
                    title=title,
                    protein_name=protein,
                    hardness=hard,
                    whc=whc,
                    file_hash=None,
                    source_file=file.filename
                ))
                added += 1
                if added % 50 == 0:
                    session.commit()
            except Exception:
                err += 1
        session.commit()
        session.add(UploadHistory(filename=file.filename, articles_added=added, duplicates_found=dup, file_size=len(file_content), total_rows=len(df)))
        session.commit()
        return JSONResponse({
            "status": "success", "added": added, "duplicates": dup, "errors": err,
            "message": f"📊 Added {added}, {dup} duplicates skipped, {err} errors"
        })
    except Exception as e:
        session.rollback()
        logger.error(traceback.format_exc())
        return JSONResponse({"status": "error", "message": f"❌ File processing error: {e}"}, status_code=500)
    finally:
        session.close()
        if filepath and os.path.exists(filepath):
            os.remove(filepath)

@app.get("/export")
async def export_articles(format: str = "csv"):
    session = Session()
    try:
        arts = session.query(Article).order_by(Article.created_at.desc()).all()
        if not arts:
            raise HTTPException(status_code=404, detail="No articles to export")
        data = [{
            "DOI": a.doi or "",
            "Title": a.title or "",
            "Protein_Name": a.protein_name or "",
            "Gel_Hardness": "Yes" if a.hardness else "No",
            "Water_Holding_Capacity": "Yes" if a.whc else "No"
        } for a in arts]
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if format == 'excel':
            export_path = EXPORT_DIR / f"research_articles_{timestamp}.xlsx"
            df.to_excel(export_path, index=False)
            media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = export_path.name
        else:
            export_path = EXPORT_DIR / f"research_articles_{timestamp}.csv"
            df.to_csv(export_path, index=False, encoding='utf-8')
            media_type = 'text/csv'
            filename = export_path.name
        return FileResponse(str(export_path), media_type=media_type, filename=filename)
    finally:
        session.close()

@app.get("/api/stats")
async def get_statistics():
    session = Session()
    try:
        total = session.query(Article).count()
        hardness = session.query(Article).filter(Article.hardness == True).count()
        whc = session.query(Article).filter(Article.whc == True).count()
        unique = session.query(Article.doi).distinct().count()
        return JSONResponse({
            "total_articles": total,
            "hardness_articles": hardness,
            "whc_articles": whc,
            "unique_dois": unique,
            "duplicate_articles": total - unique,
            "unique_articles": unique
        })
    finally:
        session.close()

@app.get("/health")
async def health_check():
    try:
        session = Session()
        session.execute("SELECT 1")
        session.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
