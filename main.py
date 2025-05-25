from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, String, Integer, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
import pandas as pd
import shutil, os
from fuzzywuzzy import fuzz
from docx import Document

app = FastAPI()

# Database setup
engine = create_engine("sqlite:///./database.db", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True)
    doi = Column(String, unique=True)
    title = Column(String)
    url = Column(String)
    hardness = Column(Boolean, default=False)
    whc = Column(Boolean, default=False)

Base.metadata.create_all(engine)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def similar_doi(existing_doi, new_doi):
    return fuzz.partial_ratio(existing_doi.lower(), new_doi.lower()) > 90

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/check_article")
async def check_article(doi: str = Form(...), title: str = Form(""), url: str = Form(""),
                        hardness: bool = Form(False), whc: bool = Form(False)):
    session = Session()
    existing_articles = session.query(Article).all()
    for article in existing_articles:
        if similar_doi(article.doi, doi):
            session.close()
            return JSONResponse({"status": "duplicate", "message": "Duplicate DOI detected."})

    new_article = Article(doi=doi, title=title, url=url, hardness=hardness, whc=whc)
    session.add(new_article)
    session.commit()
    session.close()
    return JSONResponse({"status": "new", "message": "Article saved successfully."})

@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    file_location = f"{upload_dir}/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    session = Session()
    df = pd.read_excel(file_location) if file.filename.endswith('.xlsx') else pd.read_csv(file_location)

    added, duplicates = 0, 0
    for _, row in df.iterrows():
        doi, title = row.get('doi', ''), row.get('title', '')
        exists = any(similar_doi(article.doi, doi) for article in session.query(Article).all())
        if not exists:
            session.add(Article(doi=doi, title=title))
            added += 1
        else:
            duplicates += 1
    session.commit()
    session.close()
    os.remove(file_location)
    return {"added": added, "duplicates": duplicates}

@app.get("/export")
def export_data():
    session = Session()
    articles = session.query(Article).all()
    data = [(a.doi, a.title, a.hardness, a.whc) for a in articles]
    df = pd.DataFrame(data, columns=['DOI', 'Title', 'Hardness', 'WHC'])
    export_path = "uploads/export.csv"
    df.to_csv(export_path, index=False)
    session.close()
    return FileResponse(export_path, media_type='text/csv', filename='export.csv')
