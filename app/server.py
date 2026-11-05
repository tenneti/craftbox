"""Local API. Bound to 127.0.0.1 by default; not hardened for public hosting (no authentication)."""
import json
import platform
import sys
import time
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import ai_adapters, assetstore, config
from app.core import all_crafts, execute, get_craft, get_fixture
from app.crafts.direction import approaches as direction_approaches
from app.experiments import Conflict, ExperimentService, InvalidInput, NotFound
from app.art import ArtService
from app.light import LightService
from app.lab import LabService
from app.logging_setup import configure as configure_logging, log
from app.validation import SchemaNotFound, get_schema, list_schemas

static = Path(__file__).parent / "static"


class ExperimentIn(BaseModel):
    craft_id: str
    name: str
    input: Optional[dict] = None
    notes: str = ""
    run_now: bool = False
    parent_experiment_id: Optional[str] = None


class ExperimentPatch(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None


class DuplicateIn(BaseModel):
    name: Optional[str] = None
    input: Optional[dict] = None


class ScreenplayIn(BaseModel):
    screenplay: dict


class FountainIn(BaseModel):
    text: str
    project_id: Optional[str] = None
    title: Optional[str] = None


class DraftIn(BaseModel):
    screenplay_experiment_id: str
    scene_id: str
    name: str
    approach: Optional[dict] = None
    parent_experiment_id: Optional[str] = None
    note: str = ""


class PlanSaveIn(BaseModel):
    base_experiment_id: str
    plan: dict
    name: str
    note: str = ""


class PlanAnalyzeIn(BaseModel):
    base_experiment_id: str
    plan: dict


class RebaseIn(BaseModel):
    against_experiment_id: Optional[str] = None
    name: Optional[str] = None


class ArtDraftIn(BaseModel):
    screenplay_experiment_id: str
    scene_id: str
    name: str
    preset: str = "blank"
    plan_experiment_id: Optional[str] = None
    style_experiment_id: Optional[str] = None
    parent_experiment_id: Optional[str] = None
    note: str = ""


class LightDraftIn(BaseModel):
    screenplay_experiment_id: str
    art_experiment_id: str
    name: str
    preset: str = "blank"
    plan_experiment_id: Optional[str] = None
    setup_experiment_id: Optional[str] = None
    parent_experiment_id: Optional[str] = None


class LightSaveIn(BaseModel):
    base_experiment_id: str
    light: dict
    name: str
    note: str = ""


class LightAnalyzeIn(BaseModel):
    base_experiment_id: str
    light: dict


class LightSetupIn(BaseModel):
    plan_experiment_id: str
    setup_id: str
    name: str
    summary: str = ""
    parent_experiment_id: Optional[str] = None


class ArtSaveIn(BaseModel):
    base_experiment_id: str
    art: dict
    name: str
    note: str = ""


class ArtAnalyzeIn(BaseModel):
    base_experiment_id: str
    art: dict


class ArtRebaseIn(BaseModel):
    name: Optional[str] = None


class PathIn(BaseModel):
    path: str


class ReviewIn(BaseModel):
    reviewer: Optional[str] = None
    note: Optional[str] = None


def create_app(data_dir=None, log_to_file=True):
    data = Path(data_dir) if data_dir else config.data_dir()
    configure_logging(data / "logs" if log_to_file else None)
    service = ExperimentService(data / "craftbox.db")
    app = FastAPI(title="Craftbox", version=config.VERSION,
                  description="Standalone craft experiment lab. Local only; no AI calls.")
    app.state.service = service
    lab = LabService(service)
    app.state.lab = lab
    art = ArtService(service, lab, data)
    app.state.art = art
    light = LightService(service, lab, art, data)
    app.state.light = light
    app.mount("/static", StaticFiles(directory=static), name="static")
    log("app.started", version=config.VERSION, data_dir=str(data), db_schema=service.db.version())

    @app.middleware("http")
    async def guard(request: Request, call_next):
        request_id = uuid4().hex[:12]
        started = time.perf_counter()
        length = request.headers.get("content-length")
        limit = assetstore.MAX_BYTES + 1000 if request.url.path == "/api/assets/upload" else config.MAX_BODY_BYTES
        if length and length.isdigit() and int(length) > limit:
            response = JSONResponse({"detail": f"request body exceeds {limit} bytes"}, status_code=413)
        else:
            try:
                response = await call_next(request)
            except Exception:
                log("request.unhandled_error", level="exception", request_id=request_id,
                    method=request.method, path=request.url.path)
                response = JSONResponse({"detail": "internal error", "request_id": request_id}, status_code=500)
        response.headers["X-Request-ID"] = request_id
        if not request.url.path.startswith("/static"):
            log("request", request_id=request_id, method=request.method, path=request.url.path,
                status=response.status_code, ms=round((time.perf_counter() - started) * 1000, 1))
        return response

    @app.exception_handler(NotFound)
    async def _not_found(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(Conflict)
    async def _conflict(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(InvalidInput)
    async def _invalid(_, exc):
        return JSONResponse({"detail": {"message": str(exc), "errors": exc.errors}}, status_code=422)

    @app.exception_handler(ai_adapters.AdapterDisabled)
    async def _adapter_disabled(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    # ---- existing, unchanged routes ------------------------------------------------------
    @app.get("/")
    def root():
        return FileResponse(static / "index.html")

    @app.get("/health")
    def health():
        try:
            database = "ok" if service.db.integrity() == "ok" else "error"
        except Exception:
            database = "error"
        return {"status": "ok" if database == "ok" else "degraded", "standalone": True,
                "module_count": len(all_crafts()), "app": "craftbox", "version": config.VERSION,
                "database": database}

    @app.get("/api/crafts")
    def crafts():
        return all_crafts()

    @app.get("/api/crafts/{craft_id}")
    def craft(craft_id: str):
        try:
            return get_craft(craft_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/crafts/{craft_id}/fixture")
    def fixture(craft_id: str, name: Optional[str] = None):
        try:
            return get_fixture(craft_id, name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/crafts/{craft_id}/run")
    def run(craft_id: str, payload: dict = Body(...)):
        """Stateless run (CB-prototype behavior). Nothing is saved; use /api/experiments to keep history."""
        try:
            return execute(craft_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except NotImplementedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # ---- schemas and system --------------------------------------------------------------
    @app.get("/api/schemas")
    def schemas():
        return list_schemas()

    @app.get("/api/schemas/{schema_id}")
    def schema(schema_id: str):
        try:
            return get_schema(schema_id)
        except SchemaNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/system")
    def system():
        return {"app": "craftbox", "version": config.VERSION, "python": sys.version.split()[0],
                "platform": platform.platform(), "data_dir": str(data), "db_path": str(service.db.path),
                "db_schema_version": service.db.version(), "db_integrity": service.db.integrity(),
                "counts": service.stats(), "ai_calls": False, "network_required": False}

    # ---- experiments ---------------------------------------------------------------------
    @app.post("/api/experiments", status_code=201)
    def create_experiment(body: ExperimentIn):
        exp = service.create_experiment(body.craft_id, body.name, body.input, body.notes, parent=body.parent_experiment_id)
        if body.run_now:
            run_record = service.run_experiment(exp["id"])
            exp = service.get_experiment(exp["id"])
            exp["latest_run"] = run_record
        return exp

    @app.get("/api/experiments")
    def list_experiments(craft_id: Optional[str] = None, approval_status: Optional[str] = None,
                         limit: int = 50, offset: int = 0):
        return service.list_experiments(craft_id, approval_status, limit, offset)

    @app.get("/api/experiments/{experiment_id}")
    def get_experiment(experiment_id: str):
        return service.get_experiment(experiment_id)

    @app.patch("/api/experiments/{experiment_id}")
    def patch_experiment(experiment_id: str, body: ExperimentPatch):
        return service.update_experiment(experiment_id, body.name, body.notes)

    @app.post("/api/experiments/{experiment_id}/run", status_code=201)
    def run_experiment(experiment_id: str):
        return service.run_experiment(experiment_id)

    @app.post("/api/experiments/{experiment_id}/duplicate", status_code=201)
    def duplicate_experiment(experiment_id: str, body: DuplicateIn = DuplicateIn()):
        return service.duplicate_experiment(experiment_id, body.name, body.input)

    # ---- runs, review and export ---------------------------------------------------------
    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        return service.get_run(run_id)

    @app.get("/api/runs/{run_id}/events")
    def run_events(run_id: str):
        return service.run_events(run_id)

    @app.post("/api/runs/{run_id}/verify")
    def verify(run_id: str):
        return service.verify_run(run_id)

    @app.post("/api/runs/{run_id}/submit-review")
    def submit_review(run_id: str, body: ReviewIn = ReviewIn()):
        return service.submit_for_review(run_id, body.reviewer, body.note)

    @app.post("/api/runs/{run_id}/approve")
    def approve(run_id: str, body: ReviewIn):
        return service.approve(run_id, body.reviewer, body.note)

    @app.post("/api/runs/{run_id}/reject")
    def reject(run_id: str, body: ReviewIn):
        return service.reject(run_id, body.reviewer, body.note)

    @app.post("/api/runs/{run_id}/export")
    def export_run(run_id: str):
        return service.export_run(run_id)

    @app.get("/api/runs/{run_id}/manifest")
    def manifest(run_id: str):
        data_ = service.get_manifest(run_id)
        return Response(json.dumps(data_, indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{data_["manifest_id"]}.manifest.json"'})

    @app.get("/api/compare")
    def compare(run_a: str, run_b: str):
        return service.compare_runs(run_a, run_b)

    # ---- CB1 Scene Lab: screenplay + direction ---------------------------------------------------------
    @app.get("/api/lab/projects")
    def lab_projects():
        return lab.projects()

    @app.get("/api/lab/projects/{project_id}")
    def lab_project(project_id: str):
        return lab.overview(project_id)

    @app.get("/api/lab/approaches")
    def lab_approaches():
        return [{**direction_approaches.public(a), "tone": a["tone"], "motifs": a["motifs"]} for a in direction_approaches.PRESETS.values()]

    @app.post("/api/lab/idea")
    def lab_idea(idea: dict = Body(...)):
        return lab.idea(idea)

    @app.post("/api/lab/analyze/screenplay")
    def lab_analyze_screenplay(body: ScreenplayIn):
        return lab.analyze_screenplay(body.screenplay)

    @app.post("/api/lab/import/fountain")
    def lab_import_fountain(body: FountainIn):
        return lab.import_script(body.text, body.project_id, body.title)

    @app.post("/api/lab/export/fountain")
    def lab_export_fountain(body: ScreenplayIn):
        return Response(lab.export_script(body.screenplay), media_type="text/plain; charset=utf-8")

    @app.post("/api/lab/direction/draft", status_code=201)
    def lab_draft(body: DraftIn):
        return lab.draft_plan(body.screenplay_experiment_id, body.scene_id, body.approach, body.name, body.parent_experiment_id, body.note)

    @app.post("/api/lab/direction/save", status_code=201)
    def lab_save_plan(body: PlanSaveIn):
        return lab.save_plan(body.base_experiment_id, body.plan, body.name, body.note)

    @app.post("/api/lab/direction/analyze")
    def lab_analyze_plan(body: PlanAnalyzeIn):
        return lab.analyze_plan(body.base_experiment_id, body.plan)

    @app.get("/api/lab/plans/{experiment_id}/impact")
    def lab_impact(experiment_id: str, against: Optional[str] = None):
        return lab.impact(experiment_id, against)

    @app.post("/api/lab/plans/{experiment_id}/rebase", status_code=201)
    def lab_rebase(experiment_id: str, body: RebaseIn = RebaseIn()):
        return lab.rebase(experiment_id, body.against_experiment_id, body.name)

    @app.get("/api/lab/compare-plans")
    def lab_compare_plans(run_a: str, run_b: str):
        return lab.compare_plans(run_a, run_b)

    @app.post("/api/runs/{run_id}/exports/{kind}")
    def run_export(run_id: str, kind: str, override: List[str] = Query(default=[])):
        craft = service.get_run(run_id)["craft_id"]
        exporter = art if craft == "art_direction" else (light if craft == "lighting" else lab)
        out = exporter.export(run_id, kind, override)
        headers = {"Content-Disposition": f'attachment; filename="{out["filename"]}"', "X-Craftbox-Existing": str(bool(out.get("existing"))).lower()}
        if "text" in out:
            return Response(out["text"], media_type=out["media_type"] + "; charset=utf-8", headers=headers)
        return Response(json.dumps(out["data"], indent=2, ensure_ascii=False), media_type="application/json", headers=headers)

    # ---- CB2B Lighting Lab ------------------------------------------------------------------------------------
    @app.get("/api/light/presets")
    def light_presets():
        return light.presets()

    @app.get("/api/light/projects/{project_id}")
    def light_overview(project_id: str):
        return light.overview(project_id)

    @app.post("/api/light/draft", status_code=201)
    def light_draft(body: LightDraftIn):
        return light.draft(body.screenplay_experiment_id, body.art_experiment_id, body.preset, body.name, body.plan_experiment_id, body.setup_experiment_id, body.parent_experiment_id)

    @app.post("/api/light/save", status_code=201)
    def light_save(body: LightSaveIn):
        return light.save(body.base_experiment_id, body.light, body.name, body.note)

    @app.post("/api/light/analyze")
    def light_analyze(body: LightAnalyzeIn):
        return light.analyze(body.base_experiment_id, body.light)

    @app.get("/api/light/plans/{experiment_id}/impact")
    def light_impact(experiment_id: str):
        return light.impact(experiment_id)

    @app.post("/api/light/plans/{experiment_id}/rebase", status_code=201)
    def light_rebase(experiment_id: str, body: ArtRebaseIn = ArtRebaseIn()):
        return light.rebase(experiment_id, body.name)

    @app.get("/api/light/compare")
    def light_compare(run_a: str, run_b: str):
        return light.compare(run_a, run_b)

    @app.get("/api/light/setups")
    def light_setups(project_id: str):
        return light.setups(project_id)

    @app.post("/api/light/setups", status_code=201)
    def light_save_setup(body: LightSetupIn):
        return light.save_setup(body.plan_experiment_id, body.setup_id, body.name, body.summary, body.parent_experiment_id)

    # ---- CB2A Art Direction Lab ---------------------------------------------------------------------------------
    @app.get("/api/art/presets")
    def art_presets():
        return art.presets()

    @app.get("/api/art/projects/{project_id}")
    def art_overview(project_id: str):
        return art.overview(project_id)

    @app.post("/api/art/draft", status_code=201)
    def art_draft(body: ArtDraftIn):
        return art.draft(body.screenplay_experiment_id, body.scene_id, body.preset, body.name, body.plan_experiment_id, body.style_experiment_id, body.parent_experiment_id, body.note)

    @app.post("/api/art/save", status_code=201)
    def art_save(body: ArtSaveIn):
        return art.save(body.base_experiment_id, body.art, body.name, body.note)

    @app.post("/api/art/analyze")
    def art_analyze(body: ArtAnalyzeIn):
        return art.analyze(body.base_experiment_id, body.art)

    @app.get("/api/art/treatments/{experiment_id}/impact")
    def art_impact(experiment_id: str):
        return art.impact(experiment_id)

    @app.post("/api/art/treatments/{experiment_id}/rebase", status_code=201)
    def art_rebase(experiment_id: str, body: ArtRebaseIn = ArtRebaseIn()):
        return art.rebase(experiment_id, body.name)

    @app.get("/api/art/compare")
    def art_compare(run_a: str, run_b: str):
        return art.compare(run_a, run_b)

    @app.get("/api/art/styles")
    def art_styles(project_id: str):
        return art.styles(project_id)

    @app.get("/api/art/assets")
    def art_assets(project_id: str):
        return art.register_view(project_id)

    @app.post("/api/assets/upload", status_code=201)
    async def asset_upload(request: Request, filename: str = ""):
        data_ = await request.body()
        try:
            return art.upload(data_, filename)
        except assetstore.AssetError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/assets/from-path", status_code=201)
    def asset_from_path(body: PathIn):
        try:
            return art.from_path(body.path)
        except assetstore.AssetError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/assets/{sha}/file")
    def asset_file(sha: str):
        found = assetstore.find(data, sha)
        if not found:
            raise HTTPException(status_code=404, detail="no such asset file")
        path, mime = found
        return FileResponse(path, media_type=mime, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"})

    @app.get("/api/ai/adapters")
    def ai_status():
        return {"network_calls": False, "adapters": ai_adapters.statuses()}

    @app.post("/api/ai/adapters/{name}/suggest")
    def ai_suggest(name: str, body: dict = Body(...)):
        try:
            adapter = ai_adapters.get(name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"proposal": adapter.suggest(body.get("task", ""), body.get("payload", {})), "applied": False}

    return app


_default_app = None


def __getattr__(name):
    """Lazily build ``app.server:app`` so importing this module (e.g. in tests) never touches ./data."""
    global _default_app
    if name == "app":
        if _default_app is None:
            _default_app = create_app()
        return _default_app
    raise AttributeError(name)
