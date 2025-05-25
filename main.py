from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

app = FastAPI()

# Database setup
DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Model
class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    doi = Column(String, unique=True, index=True)
    title = Column(String)
    url = Column(String)

Base.metadata.create_all(bind=engine)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/check_article")
async def check_article(doi: str = Form(...), title: str = Form(None), url: str = Form(None)):
    db = SessionLocal()
    existing_article = db.query(Article).filter(Article.doi == doi).first()
    
    if existing_article:
        db.close()
        return JSONResponse({"status": "duplicate", "message": f"Article already downloaded: {existing_article.title}"})
    else:
        new_article = Article(doi=doi, title=title or "No Title Provided", url=url or "")
        db.add(new_article)
        db.commit()
        db.close()
        return JSONResponse({"status": "new", "message": "Article saved successfully."})
