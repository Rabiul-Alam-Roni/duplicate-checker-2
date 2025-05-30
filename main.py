import os
import io
import pandas as pd
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Mount static files (for CSS/JS if any)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global data storage and stats
data_df = None               # Will hold the DataFrame of the last uploaded file (if any)
existing_titles = set()      # Titles seen (from file and any added via single check)
existing_dois = set()        # DOIs seen (from file and any added via single check)
stats = {"total": 0, "duplicates": 0}  # Statistics to display

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    """Serve the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/check_article")
async def check_article(request: Request):
    """
    Check a single DOI or title for duplicates against the current dataset.
    Returns JSON with {"duplicate": bool} or an error message.
    """
    global data_df, existing_titles, existing_dois, stats
    try:
        # Extract the article query from JSON or form data
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            body = await request.json()
            query = body.get("article") or body.get("doi") or body.get("title")
        else:
            form = await request.form()
            query = form.get("article") or form.get("doi") or form.get("title")
        if not query:
            # No input provided
            raise HTTPException(status_code=400, detail="No article title/DOI provided")

        query = query.strip()
        # Determine if this looks like a DOI (simplistic check: starts with "10.")
        is_doi = query.lower().startswith("10.")

        # Check against existing records
        duplicate = False
        if data_df is not None:
            # If a file has been uploaded, check in that data first
            if is_doi and "DOI" in data_df.columns:
                # Check DOI column for a case-insensitive match
                match = data_df["DOI"].astype(str).str.lower() == query.lower()
                if match.any():
                    duplicate = True
            if (not is_doi) and "Title" in data_df.columns:
                match = data_df["Title"].astype(str).str.lower() == query.lower()
                if match.any():
                    duplicate = True

        # Also check in any articles added via this endpoint (stored in sets)
        if is_doi:
            if query.lower() in existing_dois:
                duplicate = True
            else:
                # If not duplicate, prepare to add to DOI set
                pass
        else:
            if query.lower() in existing_titles:
                duplicate = True
            else:
                # If not duplicate, prepare to add to title set
                pass

        # Update stats and sets if needed
        if duplicate:
            # Found a duplicate entry
            stats["duplicates"] += 1
        else:
            # New unique entry
            stats["total"] += 1
            if is_doi:
                existing_dois.add(query.lower())
            else:
                existing_titles.add(query.lower())

        return {"duplicate": duplicate}
    except HTTPException as he:
        # Known error (bad input)
        raise he
    except Exception as e:
        # Log the exception (for debugging) and return generic error
        # print(f"Error in /check_article: {e}")
        return {"error": "Unknown error occurred"}

@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    """
    Process an uploaded CSV or XLSX file to find duplicate entries.
    Returns a JSON message with stats or an error.
    """
    global data_df, existing_titles, existing_dois, stats
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")

        # Read file content
        content = await file.read()
        # Determine file type by extension and read into DataFrame
        if file.filename.lower().endswith(".xlsx"):
            # Ensure openpyxl is installed for Excel
            data_df = pd.read_excel(io.BytesIO(content))
        elif file.filename.lower().endswith(".csv"):
            # Assume UTF-8 CSV
            data_df = pd.read_csv(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a .csv or .xlsx file.")

        # If DataFrame is empty or invalid:
        if data_df is None or data_df.shape[0] == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty or unreadable")

        # Identify duplicates in the DataFrame
        if "DOI" in data_df.columns and data_df["DOI"].dropna().shape[0] > 0:
            # Use DOI to find duplicates if DOI column exists and has values
            data_df["Duplicate"] = data_df.duplicated(subset=["DOI"], keep=False)
        elif "Title" in data_df.columns:
            # Otherwise use Title to find duplicates
            data_df["Duplicate"] = data_df.duplicated(subset=["Title"], keep=False)
        else:
            # If neither DOI nor Title columns exist, fall back to full row duplicate check
            data_df["Duplicate"] = data_df.duplicated(keep=False)

        # Calculate stats
        total_records = int(data_df.shape[0])
        # Count duplicate entries beyond the first occurrence in each group:
        if "Duplicate" in data_df.columns:
            # 'Duplicate' True means an entry has at least one duplicate (including itself).
            # We want the count of entries that are duplicates beyond the unique ones:
            duplicate_entries = int(data_df.duplicated(keep='first').sum())
        else:
            duplicate_entries = 0

        # Update global stats
        stats["total"] = total_records
        stats["duplicates"] = duplicate_entries

        # Update the sets of existing titles/DOIs for single-check use
        existing_titles.clear()
        existing_dois.clear()
        if "Title" in data_df.columns:
            for t in data_df["Title"].astype(str).dropna().unique():
                existing_titles.add(t.strip().lower())
        if "DOI" in data_df.columns:
            for d in data_df["DOI"].astype(str).dropna().unique():
                existing_dois.add(d.strip().lower())

        # Ensure exports directory exists and save the results file
        os.makedirs("exports", exist_ok=True)
        output_path = ""
        if file.filename.lower().endswith(".xlsx"):
            output_path = os.path.join("exports", "results.xlsx")
            data_df.to_excel(output_path, index=False)
        else:
            output_path = os.path.join("exports", "results.csv")
            data_df.to_csv(output_path, index=False)

        # Enable download (the file is saved on server side)
        return {"message": "File processed successfully", "total": total_records, "duplicates": duplicate_entries}
    except HTTPException as he:
        # Known errors (bad input, unsupported format, etc.)
        return JSONResponse(content={"error": he.detail}, status_code=he.status_code)
    except Exception as e:
        # Log the error for debugging and return failure
        # print(f"Error in /upload_file: {e}")
        return JSONResponse(content={"error": "File processing failed"}, status_code=500)

@app.get("/export")
async def export_file():
    """
    Endpoint to download the processed results file (CSV or Excel).
    """
    # Determine which file to send (prefer Excel if exists, else CSV)
    csv_path = os.path.join("exports", "results.csv")
    xlsx_path = os.path.join("exports", "results.xlsx")
    if os.path.exists(xlsx_path):
        # Return Excel file
        return FileResponse(xlsx_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="results.xlsx")
    elif os.path.exists(csv_path):
        # Return CSV file
        return FileResponse(csv_path, media_type="text/csv", filename="results.csv")
    else:
        # No file available to download
        raise HTTPException(status_code=404, detail="No results file available for download")

@app.get("/api/stats")
async def get_stats():
    """Return the current statistics as JSON."""
    return stats
