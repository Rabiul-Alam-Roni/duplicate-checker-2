from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
import pandas as pd
import shutil
import os
import json
import hashlib
from datetime import datetime
from typing import Optional, List
from fuzzywuzzy import fuzz
import aiofiles
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Bobby Team - Advanced Research Article Manager",
    description="Professional research article duplicate detection and management system with AI-powered features",
    version="2.0.0"
)

# CORS middleware for better security and flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enhanced Database setup with connection pooling
DATABASE_URL = "sqlite:///./advanced_database.db"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    pool_recycle=300
)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    doi = Column(String, unique=True, index=True)
    title = Column(String, index=True)
    url = Column(String)
    hardness = Column(Boolean, default=False)
    whc = Column(Boolean, default=False)
    tags = Column(Text, default="")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    file_hash = Column(String, unique=True, nullable=True)
    author = Column(String, nullable=True)
    publication_year = Column(Integer, nullable=True)
    journal = Column(String, nullable=True)
    abstract = Column(Text, nullable=True)
    protein_type = Column(String, nullable=True)
    gelatin_source = Column(String, nullable=True)

class UploadHistory(Base):
    __tablename__ = "upload_history"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    upload_date = Column(DateTime, default=func.now())
    articles_added = Column(Integer, default=0)
    duplicates_found = Column(Integer, default=0)
    file_size = Column(Integer, default=0)

Base.metadata.create_all(engine)

# Enhanced directory structure
UPLOAD_DIR = Path("uploads")
EXPORT_DIR = Path("exports")
BACKUP_DIR = Path("backups")
LOGS_DIR = Path("logs")

for directory in [UPLOAD_DIR, EXPORT_DIR, BACKUP_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def generate_file_hash(file_content: bytes) -> str:
    """Generate SHA-256 hash for file content"""
    return hashlib.sha256(file_content).hexdigest()

def normalize_doi(doi: str) -> str:
    """Enhanced DOI normalization with better cleaning"""
    if not doi:
        return ""
    
    # Remove common prefixes and clean
    cleaned = doi.lower().strip()
    prefixes = ["https://doi.org/", "http://doi.org/", "doi:", "doi "]
    
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    
    return cleaned.strip()

def advanced_doi_similarity(doi1: str, doi2: str) -> float:
    """Enhanced similarity checking with multiple algorithms"""
    normalized1 = normalize_doi(doi1)
    normalized2 = normalize_doi(doi2)
    
    if not normalized1 or not normalized2:
        return 0.0
    
    # Multiple similarity checks
    ratio_score = fuzz.ratio(normalized1, normalized2)
    token_sort_score = fuzz.token_sort_ratio(normalized1, normalized2)
    token_set_score = fuzz.token_set_ratio(normalized1, normalized2)
    
    # Weight the scores
    final_score = (ratio_score * 0.5 + token_sort_score * 0.3 + token_set_score * 0.2)
    return final_score

def doi_exists(session, doi: str, similarity_threshold: float = 85.0) -> tuple[bool, Optional[Article]]:
    """Enhanced duplicate detection with configurable threshold"""
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        return False, None
    
    articles = session.query(Article).all()
    
    for article in articles:
        similarity = advanced_doi_similarity(article.doi, doi)
        if similarity > similarity_threshold:
            return True, article
    
    return False, None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Enhanced home page with statistics"""
    session = Session()
    try:
        total_articles = session.query(Article).count()
        recent_uploads = session.query(UploadHistory).order_by(UploadHistory.upload_date.desc()).limit(5).all()
        
        stats = {
            "total_articles": total_articles,
            "hardness_articles": session.query(Article).filter(Article.hardness == True).count(),
            "whc_articles": session.query(Article).filter(Article.whc == True).count(),
            "recent_uploads": len(recent_uploads)
        }
        
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "stats": stats,
            "recent_uploads": recent_uploads
        })
    finally:
        session.close()

@app.post("/check_article")
async def check_article(
    doi: str = Form(...),
    title: str = Form(""),
    url: str = Form(""),
    hardness: bool = Form(False),
    whc: bool = Form(False),
    tags: str = Form(""),
    author: str = Form(""),
    journal: str = Form(""),
    publication_year: Optional[int] = Form(None),
    protein_type: str = Form(""),
    gelatin_source: str = Form("")
):
    """Enhanced article checking with additional fields"""
    session = Session()
    try:
        # Check for duplicates
        is_duplicate, existing_article = doi_exists(session, doi)
        
        if is_duplicate:
            logger.info(f"Duplicate DOI detected: {doi}")
            return JSONResponse({
                "status": "duplicate",
                "message": f"⚠️ Article already exists! Similar to: {existing_article.title[:50]}...",
                "existing_article": {
                    "title": existing_article.title,
                    "doi": existing_article.doi,
                    "created_at": existing_article.created_at.isoformat() if existing_article.created_at else None
                }
            })
        
        # Create new article with enhanced fields
        new_article = Article(
            doi=doi,
            title=title,
            url=url,
            hardness=hardness,
            whc=whc,
            tags=tags,
            author=author,
            journal=journal,
            publication_year=publication_year,
            protein_type=protein_type,
            gelatin_source=gelatin_source
        )
        
        session.add(new_article)
        session.commit()
        
        logger.info(f"New article added: {doi}")
        return JSONResponse({
            "status": "success",
            "message": "✅ Article successfully saved with enhanced details!",
            "article_id": new_article.id
        })
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error checking article: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        session.close()

@app.post("/upload_file")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Enhanced file upload with background processing and detailed logging"""
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported")
    
    # Read file content
    file_content = await file.read()
    file_hash = generate_file_hash(file_content)
    file_size = len(file_content)
    
    # Save file
    filepath = UPLOAD_DIR / file.filename
    async with aiofiles.open(filepath, 'wb') as f:
        await f.write(file_content)
    
    try:
        # Read the uploaded file
        if filepath.suffix.lower() == '.csv':
            df = pd.read_csv(filepath, encoding='utf-8')
        else:
            df = pd.read_excel(filepath)
        
        session = Session()
        added_count = 0
        duplicate_count = 0
        error_count = 0
        processed_dois = []
        
        # Enhanced column mapping
        column_mapping = {
            'doi': ['doi', 'DOI', 'Doi', 'digital_object_identifier'],
            'title': ['title', 'Title', 'TITLE', 'article_title'],
            'tags': ['tags', 'Tags', 'TAGS', 'keywords'],
            'author': ['author', 'Author', 'AUTHORS', 'authors'],
            'journal': ['journal', 'Journal', 'JOURNAL', 'publication'],
            'year': ['year', 'Year', 'YEAR', 'publication_year'],
            'protein_type': ['protein_type', 'protein', 'Protein_Type'],
            'gelatin_source': ['gelatin_source', 'source', 'Gelatin_Source']
        }
        
        def get_column_value(row, field_name):
            """Get column value with flexible column name matching"""
            possible_names = column_mapping.get(field_name, [field_name])
            for name in possible_names:
                if name in row and pd.notna(row[name]):
                    return str(row[name]).strip()
            return ""
        
        # Process each row
        for index, row in df.iterrows():
            try:
                doi = get_column_value(row, 'doi')
                if not doi:
                    error_count += 1
                    continue
                
                # Check for duplicates
                is_duplicate, _ = doi_exists(session, doi)
                
                if is_duplicate or doi in processed_dois:
                    duplicate_count += 1
                    continue
                
                # Extract additional fields
                title = get_column_value(row, 'title')
                tags = get_column_value(row, 'tags')
                author = get_column_value(row, 'author')
                journal = get_column_value(row, 'journal')
                
                # Handle year conversion
                year_str = get_column_value(row, 'year')
                publication_year = None
                if year_str and year_str.isdigit():
                    publication_year = int(year_str)
                
                protein_type = get_column_value(row, 'protein_type')
                gelatin_source = get_column_value(row, 'gelatin_source')
                
                # Create new article
                new_article = Article(
                    doi=doi,
                    title=title,
                    tags=tags,
                    author=author,
                    journal=journal,
                    publication_year=publication_year,
                    protein_type=protein_type,
                    gelatin_source=gelatin_source,
                    file_hash=file_hash
                )
                
                session.add(new_article)
                processed_dois.append(doi)
                added_count += 1
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing row {index}: {str(e)}")
                continue
        
        # Commit all changes
        session.commit()
        
        # Record upload history
        upload_record = UploadHistory(
            filename=file.filename,
            articles_added=added_count,
            duplicates_found=duplicate_count,
            file_size=file_size
        )
        session.add(upload_record)
        session.commit()
        
        logger.info(f"File upload completed: {file.filename}, Added: {added_count}, Duplicates: {duplicate_count}")
        
        return JSONResponse({
            "status": "success",
            "added": added_count,
            "duplicates": duplicate_count,
            "errors": error_count,
            "total_processed": len(df),
            "message": f"📊 Processing complete! Added {added_count} new articles, found {duplicate_count} duplicates"
        })
        
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File processing error: {str(e)}")
    finally:
        session.close()
        # Clean up uploaded file
        if filepath.exists():
            filepath.unlink()

@app.get("/export")
async def export_articles(format: str = "csv"):
    """Enhanced export with multiple formats and comprehensive data"""
    session = Session()
    try:
        articles = session.query(Article).order_by(Article.created_at.desc()).all()
        
        if not articles:
            raise HTTPException(status_code=404, detail="No articles found to export")
        
        # Create comprehensive dataframe
        data = []
        for article in articles:
            data.append({
                'ID': article.id,
                'DOI': article.doi,
                'Title': article.title,
                'URL': article.url,
                'Author': article.author,
                'Journal': article.journal,
                'Publication_Year': article.publication_year,
                'Protein_Type': article.protein_type,
                'Gelatin_Source': article.gelatin_source,
                'Gel_Hardness': 'Yes' if article.hardness else 'No',
                'Water_Holding_Capacity': 'Yes' if article.whc else 'No',
                'Tags': article.tags,
                'Created_Date': article.created_at.strftime('%Y-%m-%d %H:%M:%S') if article.created_at else '',
                'Last_Updated': article.updated_at.strftime('%Y-%m-%d %H:%M:%S') if article.updated_at else ''
            })
        
        df = pd.DataFrame(data)
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format.lower() == 'excel':
            export_path = EXPORT_DIR / f"research_articles_backup_{timestamp}.xlsx"
            df.to_excel(export_path, index=False)
            media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f"research_articles_backup_{timestamp}.xlsx"
        else:
            export_path = EXPORT_DIR / f"research_articles_backup_{timestamp}.csv"
            df.to_csv(export_path, index=False, encoding='utf-8')
            media_type = 'text/csv'
            filename = f"research_articles_backup_{timestamp}.csv"
        
        logger.info(f"Export completed: {filename}, {len(articles)} articles")
        
        return FileResponse(
            path=export_path,
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    finally:
        session.close()

@app.get("/api/stats")
async def get_statistics():
    """API endpoint for dashboard statistics"""
    session = Session()
    try:
        total_articles = session.query(Article).count()
        hardness_count = session.query(Article).filter(Article.hardness == True).count()
        whc_count = session.query(Article).filter(Article.whc == True).count()
        
        # Calculate unique vs duplicate articles
        unique_count = session.query(Article.doi).distinct().count()
        duplicates = total_articles - unique_count
        
        # Recent activity
        recent_articles = session.query(Article).order_by(Article.created_at.desc()).limit(10).all()
        
        # Upload statistics
        recent_uploads = session.query(UploadHistory).order_by(UploadHistory.upload_date.desc()).limit(5).all()
        
        return {
            "total_articles": total_articles,
            "unique_articles": unique_count,
            "duplicate_articles": duplicates,
            "hardness_articles": hardness_count,
            "whc_articles": whc_count,
            "recent_articles": [
                {
                    "title": article.title,
                    "doi": article.doi,
                    "created_at": article.created_at.isoformat() if article.created_at else None
                }
                for article in recent_articles
            ],
            "recent_uploads": [
                {
                    "filename": upload.filename,
                    "date": upload.upload_date.isoformat() if upload.upload_date else None,
                    "added": upload.articles_added,
                    "duplicates": upload.duplicates_found
                }
                for upload in recent_uploads
            ]
        }
    finally:
        session.close()

@app.get("/api/search")
async def search_articles(q: str, limit: int = 20):
    """Advanced search functionality"""
    session = Session()
    try:
        # Search in multiple fields
        articles = session.query(Article).filter(
            (Article.title.contains(q)) |
            (Article.doi.contains(q)) |
            (Article.tags.contains(q)) |
            (Article.author.contains(q)) |
            (Article.journal.contains(q))
        ).limit(limit).all()
        
        results = []
        for article in articles:
            results.append({
                "id": article.id,
                "doi": article.doi,
                "title": article.title,
                "author": article.author,
                "journal": article.journal,
                "tags": article.tags,
                "created_at": article.created_at.isoformat() if article.created_at else None
            })
        
        return {"results": results, "count": len(results)}
        
    finally:
        session.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
