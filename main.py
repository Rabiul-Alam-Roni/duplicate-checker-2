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
import sqlite3
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Bobby Team - Advanced Research Article Manager",
    description="Professional research article duplicate detection and management system with AI-powered features",
    version="2.0.0"
)

# Fixed CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Enhanced Database setup with better error handling
DATABASE_URL = "sqlite:///./research_articles.db"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False
)
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

# Create tables with error handling
try:
    Base.metadata.create_all(engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Database setup error: {e}")
    raise

# Enhanced directory structure
UPLOAD_DIR = Path("uploads")
EXPORT_DIR = Path("exports")
STATIC_DIR = Path("static")
TEMPLATES_DIR = Path("templates")

for directory in [UPLOAD_DIR, EXPORT_DIR, STATIC_DIR, TEMPLATES_DIR]:
    directory.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def generate_file_hash(file_content: bytes) -> str:
    """Generate SHA-256 hash for file content"""
    return hashlib.sha256(file_content).hexdigest()

def normalize_doi(doi: str) -> str:
    """Enhanced DOI normalization with better cleaning"""
    if not doi or pd.isna(doi):
        return ""
    
    # Convert to string and clean
    cleaned = str(doi).lower().strip()
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
    
    # Exact match first
    if normalized1 == normalized2:
        return 100.0
    
    # Multiple similarity checks
    ratio_score = fuzz.ratio(normalized1, normalized2)
    token_sort_score = fuzz.token_sort_ratio(normalized1, normalized2)
    token_set_score = fuzz.token_set_ratio(normalized1, normalized2)
    
    # Weight the scores
    final_score = (ratio_score * 0.5 + token_sort_score * 0.3 + token_set_score * 0.2)
    return final_score

def doi_exists_in_db(session, doi: str, similarity_threshold: float = 85.0) -> tuple[bool, Optional[Article]]:
    """Enhanced duplicate detection with configurable threshold"""
    try:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return False, None
        
        articles = session.query(Article).all()
        
        for article in articles:
            if article.doi:
                similarity = advanced_doi_similarity(article.doi, doi)
                if similarity > similarity_threshold:
                    return True, article
        
        return False, None
    except Exception as e:
        logger.error(f"Error checking DOI existence: {e}")
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
            "recent_uploads": len(recent_uploads),
            "unique_dois": session.query(Article.doi).distinct().count()
        }
        
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "stats": stats,
            "recent_uploads": recent_uploads
        })
    except Exception as e:
        logger.error(f"Home page error: {e}")
        stats = {"total_articles": 0, "hardness_articles": 0, "whc_articles": 0, "recent_uploads": 0, "unique_dois": 0}
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "stats": stats,
            "recent_uploads": []
        })
    finally:
        session.close()

@app.post("/check_article")
async def check_article(
    doi: str = Form(...),
    title: str = Form(""),
    protein_name: str = Form(""),
    hardness: bool = Form(False),
    whc: bool = Form(False)
):
    """Enhanced article checking with better error handling"""
    session = Session()
    try:
        # Validate input
        if not doi or not doi.strip():
            return JSONResponse({
                "status": "error",
                "message": "❌ DOI is required!"
            }, status_code=400)
        
        # Normalize DOI
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return JSONResponse({
                "status": "error",
                "message": "❌ Invalid DOI format!"
            }, status_code=400)
        
        # Check for duplicates
        is_duplicate, existing_article = doi_exists_in_db(session, normalized_doi)
        
        if is_duplicate:
            logger.info(f"Duplicate DOI detected: {normalized_doi}")
            return JSONResponse({
                "status": "duplicate",
                "message": f"🔴 This article has already been downloaded! Similar to: {existing_article.title[:50] if existing_article.title else existing_article.doi}...",
                "existing_article": {
                    "title": existing_article.title,
                    "doi": existing_article.doi,
                    "created_at": existing_article.created_at.isoformat() if existing_article.created_at else None
                }
            })
        
        # Create new article
        new_article = Article(
            doi=normalized_doi,
            title=title.strip() if title else "",
            protein_name=protein_name.strip() if protein_name else "",
            hardness=bool(hardness),
            whc=bool(whc),
            source_file="manual_entry"
        )
        
        session.add(new_article)
        session.commit()
        
        logger.info(f"New article added: {normalized_doi}")
        return JSONResponse({
            "status": "success",
            "message": "✅ Article successfully saved!",
            "article_id": new_article.id
        })
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error checking article: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JSONResponse({
            "status": "error",
            "message": f"❌ Database error: {str(e)}"
        }, status_code=500)
    finally:
        session.close()

@app.post("/upload_file")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Enhanced file upload with robust error handling"""
    filepath = None
    session = Session()
    
    try:
        # Validate file
        if not file.filename:
            return JSONResponse({
                "status": "error",
                "message": "❌ No file provided"
            }, status_code=400)
        
        file_extension = file.filename.lower().split('.')[-1]
        if file_extension not in ['csv', 'xlsx', 'xls']:
            return JSONResponse({
                "status": "error",
                "message": "❌ Only CSV and Excel files (.csv, .xlsx, .xls) are supported"
            }, status_code=400)
        
        # Read file content
        file_content = await file.read()
        if not file_content:
            return JSONResponse({
                "status": "error",
                "message": "❌ File is empty"
            }, status_code=400)
        
        file_hash = generate_file_hash(file_content)
        file_size = len(file_content)
        
        # Save file temporarily
        filepath = UPLOAD_DIR / file.filename
        with open(filepath, 'wb') as f:
            f.write(file_content)
        
        # Read the uploaded file
        try:
            if file_extension == 'csv':
                # Try different encodings for CSV
                encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                df = None
                for encoding in encodings:
                    try:
                        df = pd.read_csv(filepath, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df is None:
                    return JSONResponse({
                        "status": "error",
                        "message": "❌ Unable to read CSV file with any supported encoding"
                    }, status_code=400)
            else:
                df = pd.read_excel(filepath)
            
            if df.empty:
                return JSONResponse({
                    "status": "error",
                    "message": "❌ File contains no data"
                }, status_code=400)
                
        except Exception as e:
            logger.error(f"File reading error: {e}")
            return JSONResponse({
                "status": "error",
                "message": f"❌ Error reading file: {str(e)}"
            }, status_code=400)
        
        # Initialize counters
        added_count = 0
        duplicate_count = 0
        error_count = 0
        processed_dois = set()
        
        # Enhanced column mapping
        def find_column(df, possible_names):
            """Find column with case-insensitive matching"""
            df_columns_lower = [col.lower().strip() for col in df.columns]
            for name in possible_names:
                name_lower = name.lower().strip()
                if name_lower in df_columns_lower:
                    actual_col = df.columns[df_columns_lower.index(name_lower)]
                    return actual_col
            return None
        
        # Find required columns
        doi_col = find_column(df, ['doi', 'DOI', 'digital_object_identifier', 'Digital Object Identifier'])
        title_col = find_column(df, ['title', 'Title', 'TITLE', 'article_title', 'Article Title'])
        protein_col = find_column(df, ['protein_name', 'protein', 'Protein', 'Protein_Name', 'protein_type'])
        hardness_col = find_column(df, ['hardness', 'Hardness', 'gel_hardness', 'Gel_Hardness', 'Gel Hardness'])
        whc_col = find_column(df, ['whc', 'WHC', 'water_holding_capacity', 'Water_Holding_Capacity', 'Water Holding Capacity'])
        
        if not doi_col:
            return JSONResponse({
                "status": "error",
                "message": "❌ DOI column not found. Please ensure your file has a 'DOI' column."
            }, status_code=400)
        
        logger.info(f"Processing file with {len(df)} rows")
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Get DOI
                doi_value = row[doi_col] if doi_col and pd.notna(row[doi_col]) else ""
                doi_normalized = normalize_doi(str(doi_value))
                
                if not doi_normalized:
                    error_count += 1
                    continue
                
                # Skip if already processed in this batch
                if doi_normalized in processed_dois:
                    duplicate_count += 1
                    continue
                
                # Check if exists in database
                is_duplicate, existing_article = doi_exists_in_db(session, doi_normalized)
                
                if is_duplicate:
                    duplicate_count += 1
                    continue
                
                # Extract other fields
                title = str(row[title_col]).strip() if title_col and pd.notna(row[title_col]) else ""
                protein_name = str(row[protein_col]).strip() if protein_col and pd.notna(row[protein_col]) else ""
                
                # Handle boolean fields
                hardness = False
                if hardness_col and pd.notna(row[hardness_col]):
                    hardness_val = str(row[hardness_col]).lower().strip()
                    hardness = hardness_val in ['true', 'yes', '1', 'y', 'hardness']
                
                whc = False
                if whc_col and pd.notna(row[whc_col]):
                    whc_val = str(row[whc_col]).lower().strip()
                    whc = whc_val in ['true', 'yes', '1', 'y', 'whc']
                
                # Create new article
                new_article = Article(
                    doi=doi_normalized,
                    title=title,
                    protein_name=protein_name,
                    hardness=hardness,
                    whc=whc,
                    file_hash=file_hash,
                    source_file=file.filename
                )
                
                session.add(new_article)
                processed_dois.add(doi_normalized)
                added_count += 1
                
                # Commit in batches
                if added_count % 100 == 0:
                    session.commit()
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing row {index + 1}: {str(e)}")
                continue
        
        # Final commit
        session.commit()
        
        # Record upload history
        upload_record = UploadHistory(
            filename=file.filename,
            articles_added=added_count,
            duplicates_found=duplicate_count,
            file_size=file_size,
            total_rows=len(df)
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
            "message": f"📊 Processing complete! Added {added_count} new articles, found {duplicate_count} duplicates, {error_count} errors"
        })
        
    except Exception as e:
        session.rollback()
        logger.error(f"File upload error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JSONResponse({
            "status": "error",
            "message": f"❌ File processing error: {str(e)}"
        }, status_code=500)
    finally:
        session.close()
        # Clean up uploaded file
        if filepath and filepath.exists():
            try:
                filepath.unlink()
            except Exception as e:
                logger.error(f"Error cleaning up file: {e}")

@app.get("/export")
async def export_articles(format: str = "csv"):
    """Enhanced export with better error handling"""
    session = Session()
    try:
        articles = session.query(Article).order_by(Article.created_at.desc()).all()
        
        if not articles:
            raise HTTPException(status_code=404, detail="No articles found to export")
        
        # Create simplified dataframe
        data = []
        for article in articles:
            data.append({
                'DOI': article.doi or '',
                'Title': article.title or '',
                'Protein_Name': article.protein_name or '',
                'Gel_Hardness': 'Yes' if article.hardness else 'No',
                'Water_Holding_Capacity': 'Yes' if article.whc else 'No'
            })
        
        df = pd.DataFrame(data)
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format.lower() == 'excel':
            export_path = EXPORT_DIR / f"research_articles_{timestamp}.xlsx"
            df.to_excel(export_path, index=False)
            media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f"research_articles_{timestamp}.xlsx"
        else:
            export_path = EXPORT_DIR / f"research_articles_{timestamp}.csv"
            df.to_csv(export_path, index=False, encoding='utf-8')
            media_type = 'text/csv'
            filename = f"research_articles_{timestamp}.csv"
        
        logger.info(f"Export completed: {filename}, {len(articles)} articles")
        
        return FileResponse(
            path=export_path,
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")
    finally:
        session.close()

@app.get("/api/stats")
async def get_statistics():
    """API endpoint for dashboard statistics with better error handling"""
    session = Session()
    try:
        total_articles = session.query(Article).count()
        hardness_count = session.query(Article).filter(Article.hardness == True).count()
        whc_count = session.query(Article).filter(Article.whc == True).count()
        unique_dois = session.query(Article.doi).distinct().count()
        
        # Recent articles
        recent_articles = session.query(Article).order_by(Article.created_at.desc()).limit(10).all()
        
        # Upload statistics
        recent_uploads = session.query(UploadHistory).order_by(UploadHistory.upload_date.desc()).limit(5).all()
        
        # Calculate duplicate percentage
        duplicate_percentage = 0
        if total_articles > 0:
            duplicate_percentage = round(((total_articles - unique_dois) / total_articles) * 100, 1)
        
        return JSONResponse({
            "total_articles": total_articles,
            "unique_articles": unique_dois,
            "duplicate_articles": total_articles - unique_dois,
            "duplicate_percentage": duplicate_percentage,
            "hardness_articles": hardness_count,
            "whc_articles": whc_count,
            "hardness_percentage": round((hardness_count / total_articles * 100), 1) if total_articles > 0 else 0,
            "whc_percentage": round((whc_count / total_articles * 100), 1) if total_articles > 0 else 0,
            "recent_articles": [
                {
                    "title": article.title or "No Title",
                    "doi": article.doi,
                    "protein_name": article.protein_name or "Not specified",
                    "created_at": article.created_at.isoformat() if article.created_at else None
                }
                for article in recent_articles
            ],
            "recent_uploads": [
                {
                    "filename": upload.filename,
                    "date": upload.upload_date.isoformat() if upload.upload_date else None,
                    "added": upload.articles_added,
                    "duplicates": upload.duplicates_found,
                    "total_rows": upload.total_rows
                }
                for upload in recent_uploads
            ]
        })
    except Exception as e:
        logger.error(f"Stats error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JSONResponse({
            "total_articles": 0,
            "unique_articles": 0,
            "duplicate_articles": 0,
            "duplicate_percentage": 0,
            "hardness_articles": 0,
            "whc_articles": 0,
            "hardness_percentage": 0,
            "whc_percentage": 0,
            "recent_articles": [],
            "recent_uploads": []
        })
    finally:
        session.close()

@app.get("/api/search")
async def search_articles(q: str, limit: int = 20):
    """Advanced search functionality with better error handling"""
    session = Session()
    try:
        # Search in multiple fields
        search_term = f"%{q}%"
        articles = session.query(Article).filter(
            (Article.title.like(search_term)) |
            (Article.doi.like(search_term)) |
            (Article.protein_name.like(search_term))
        ).limit(limit).all()
        
        results = []
        for article in articles:
            results.append({
                "id": article.id,
                "doi": article.doi,
                "title": article.title or "No Title",
                "protein_name": article.protein_name or "Not specified",
                "hardness": article.hardness,
                "whc": article.whc,
                "created_at": article.created_at.isoformat() if article.created_at else None
            })
        
        return JSONResponse({"results": results, "count": len(results)})
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return JSONResponse({"results": [], "count": 0})
    finally:
        session.close()

@app.delete("/api/articles/{article_id}")
async def delete_article(article_id: int):
    """Delete an article by ID with better error handling"""
    session = Session()
    try:
        article = session.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        session.delete(article)
        session.commit()
        
        return JSONResponse({"status": "success", "message": "Article deleted successfully"})
    except Exception as e:
        session.rollback()
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")
    finally:
        session.close()

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        session = Session()
        session.execute("SELECT 1")
        session.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
