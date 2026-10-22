import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Any
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from api.database import SessionLocal, init_db, RunModel
from api.models import RunCreate, RunResponse

from fastapi.encoders import jsonable_encoder

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Celesto Run Ledger API", lifespan=lifespan)

# Return HTTP 400 on validation errors as specifically required by the hackathon spec
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": jsonable_encoder(exc.errors())},
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health", status_code=200)
def health():
    return {"status": "ok"}

@app.get("/api/runs", response_model=List[RunResponse], status_code=200)
def get_runs(db: Session = Depends(get_db)):
    rows = db.query(RunModel).all()
    return [RunResponse(**row.to_dict()) for row in rows]

@app.post("/api/runs", response_model=RunResponse, status_code=201)
def create_run(run: RunCreate, db: Session = Depends(get_db)):
    # Check if run_id or sandbox_name already exists
    existing = db.query(RunModel).filter(
        (RunModel.run_id == run.run_id) | (RunModel.sandbox_name == run.sandbox_name)
    ).first()
    if existing:
        # Update or conflict
        existing.state = run.state
        existing.execution_target = run.execution_target
        existing.problem_id = run.problem_id
        db.commit()
        db.refresh(existing)
        return RunResponse(**existing.to_dict())

    new_run = RunModel(
        run_id=run.run_id,
        sandbox_name=run.sandbox_name,
        problem_id=run.problem_id,
        state=run.state,
        execution_target=run.execution_target,
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    return RunResponse(**new_run.to_dict())

# Serve report files for reviewers
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

@app.get("/reports/{filename}")
def get_report_file(filename: str):
    file_path = REPORTS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(file_path)
