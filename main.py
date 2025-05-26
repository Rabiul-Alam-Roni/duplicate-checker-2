from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, String, Integer, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
import pandas as pd
import shutil, os
from fuzzywuzzy import fuzz

app = FastAPI()

# Database setup
engine = create_engine("sqlite:///./database.db", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()

# Article model
class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True)
    doi = Column(String, unique=True)
    title = Column(String)
    url = Column(String)
    hardness = Column(Boolean, default=False)
    whc = Column(Boolean, default=False)
    tags = Column(String, default="")

Base.metadata.create_all(engine)

# Directory for file uploads
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mounting static files & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Helper function to normalize DOI
def normalize_doi(doi):
    return doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "").strip()

# Check if DOI already exists
def doi_exists(session, doi):
    normalized_new_doi = normalize_doi(doi)
    articles = session.query(Article).all()
    for article in articles:
        if fuzz.ratio(normalize_doi(article.doi), normalized_new_doi) > 90:
            return True
    return False

# Homepage
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Check single DOI entry
@app.post("/check_article")
def check_article(
    doi: str = Form(...), 
    title: str = Form(""), 
    url: str = Form(""), 
    hardness: bool = Form(False), 
    whc: bool = Form(False),
    tags: str = Form("")
):
    session = Session()
    if doi_exists(session, doi):
        session.close()
        return JSONResponse({"status": "duplicate", "message": "🔴 Article already downloaded."})

    new_article = Article(
        doi=doi, title=title, url=url, 
        hardness=hardness, whc=whc, tags=tags
    )
    session.add(new_article)
    session.commit()
    session.close()
    return JSONResponse({"status": "new", "message": "🟢 Article successfully saved."})

# Upload and check CSV/Excel files
@app.post("/upload_file")
def upload_file(file: UploadFile = File(...)):
    filepath = f"{UPLOAD_DIR}/{file.filename}"
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    df = pd.read_csv(filepath) if filepath.endswith('.csv') else pd.read_excel(filepath)
    session = Session()
    added, duplicates = 0, 0

    existing_dois = [normalize_doi(article.doi) for article in session.query(Article).all()]

    for _, row in df.iterrows():
        doi, title, tags = row.get('doi', ''), row.get('title', ''), row.get('tags', '')
        normalized_doi = normalize_doi(doi)

        if normalized_doi in existing_dois:
            duplicates += 1
        else:
            new_article = Article(doi=doi, title=title, tags=tags)
            session.add(new_article)
            existing_dois.append(normalized_doi)
            added += 1

    session.commit()
    session.close()

    return {"added": added, "duplicates": duplicates}

# List uploaded files
@app.get("/uploaded_files")
def uploaded_files():
    return os.listdir(UPLOAD_DIR)

# Delete uploaded file
@app.delete("/delete_file/{filename}")
def delete_file(filename: str):
    filepath = f"{UPLOAD_DIR}/{filename}"
    if os.path.exists(filepath):
        os.remove(filepath)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="File not found")

# Export database as CSV backup
@app.get("/export")
def export_articles():
    session = Session()
    articles = session.query(Article).all()
    df = pd.DataFrame(
        [(a.doi, a.title, a.hardness, a.whc, a.tags) for a in articles], 
        columns=['DOI', 'Title', 'Hardness', 'WHC', 'Tags']
    )
    export_path = f"{UPLOAD_DIR}/backup.csv"
    df.to_csv(export_path, index=False)
    session.close()
    return FileResponse(export_path, media_type='text/csv', filename='backup.csv')
