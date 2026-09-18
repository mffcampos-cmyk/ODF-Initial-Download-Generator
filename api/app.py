from __future__ import annotations
import io
import zipfile
from pathlib import Path
from fastapi import FastAPI, Query, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from generator.packs import PackNotReady, PackRegistry, UnknownPack
from generator.eventstructure import UnknownSquadSize
from generator.bundle import build_bundle
from generator.export import export_bundle, PROJECT_ROOT
from generator.overrides import Overrides
from generator.refdata import RefData

# Discovers every pack under the validator's Rules/ folder. A pack that cannot
# generate yet (no XSD, no codes, no disciplines, or an incomplete Games
# profile) is still listed, with the reasons, instead of crashing startup.
# Discovering no packs at all remains a hard failure.
REGISTRY = PackRegistry.discover()
WEB = Path(__file__).resolve().parent.parent / "web"
TEMPLATE = WEB / "templates" / "index.html"

app = FastAPI(title="ODF Message Generator")
# The page's CSS and JS. Serving them as files (rather than inlining them in
# the template) is what lets tests/web/app.test.mjs import app.js directly.
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


@app.exception_handler(UnknownSquadSize)
def _unknown_squad_size(request, exc: UnknownSquadSize) -> JSONResponse:
    """A discipline the generator deliberately refuses to build.

    Not a bug and not a bad request: the operator asked for something the
    reference data cannot answer. 422 with the reason verbatim -- it names the
    event and the file to edit -- rather than a 500 and a traceback in the
    service window.
    """
    return JSONResponse(status_code=422, content={"error": str(exc)})


@app.exception_handler(RequestValidationError)
def _validation_error(request, exc: RequestValidationError) -> JSONResponse:
    """Reshape FastAPI's 422 body into the {"error": ...} the client reads.

    Every hand-written error in this app returns {"error": str}; FastAPI's own
    validation failures return {"detail": [{...}]}, which the client's
    requestJson() cannot read -- it falls through to the bare status line and
    the operator sees "Error: 422 Unprocessable Entity" with no clue which
    field was wrong. That gap only started mattering when the count and seed
    bounds gave the operator a realistic way to trigger it.
    """
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        parts.append(f"{field}: {err.get('msg', 'invalid value')}"
                     if field else err.get("msg", "invalid value"))
    return JSONResponse(status_code=422,
                        content={"error": "; ".join(parts) or "invalid request"})


def resolve(pack_name: str | None, *, require_ready: bool = True) -> tuple[str, RefData]:
    """The resolved pack name and its RefData for a request, defaulting to
    the startup default.

    Raises ``UnknownPack`` if ``pack_name`` (or, when omitted, ``ODF_GAMES``)
    names a pack that was never discovered, and ``PackNotReady`` if the
    resolved pack was discovered but cannot generate yet. Callers must catch
    both and route them through ``_pack_error``.

    ``require_ready=False`` (used for read-only listing, see
    ``/api/disciplines``) relaxes that last check to "has usable content" --
    a pack with no matching Games profile still lists its disciplines fine;
    it just can't build a message yet. A pack with no content at all (empty
    ruleset, or ingestion itself failed) still raises ``PackNotReady``
    either way."""
    name = pack_name if pack_name is not None else REGISTRY.default_name()
    refdata = REGISTRY.peek(name) if not require_ready else REGISTRY.get(name)
    return name, refdata


def _resolve_default() -> tuple[str | None, str | None]:
    """The configured default pack name, or the error naming a bad one.

    Never raises. ``REGISTRY.default_name()`` raises ``UnknownPack`` when
    ``ODF_GAMES`` names a pack that was never discovered; that is correct
    there, but a second raise here — from code that only exists to *report*
    on a request that already failed — would escape any handler and turn
    into a bare 500. Callers that need a name to label a response (rather
    than a pack to resolve against) call this instead of
    ``REGISTRY.default_name()`` directly."""
    try:
        return REGISTRY.default_name(), None
    except UnknownPack as e:
        return None, str(e)


def _pack_error(exc: Exception, pack_name: str | None) -> JSONResponse:
    """The JSON error body for a pack that is unknown or cannot generate.

    This deliberately returns ``str(exc)`` verbatim, and pack load failures
    embed the exception type and message (see ``PackRegistry``), because the
    audience is a single operator on 127.0.0.1 who needs to know exactly which
    file failed to parse. That is a stack-trace-exposure trade-off which only
    holds while the service stays on loopback -- see ``Launch-ODF-Generator.bat``.
    Binding this to 0.0.0.0 means sanitising these bodies first."""
    if pack_name is not None:
        name = pack_name
    else:
        name, _ = _resolve_default()
    if isinstance(exc, UnknownPack):
        return JSONResponse(status_code=400,
                            content={"error": str(exc), "pack": name,
                                     "known": REGISTRY.names()})
    status = REGISTRY.status(name)
    return JSONResponse(status_code=409,
                        content={"error": str(exc), "pack": name,
                                 "reasons": status.to_dict()["reasons"]})


# Upper bound on the entry-count overrides. These are loop counts: every unit
# builds participants, and build_bundle retries up to 5 seeds, so an unbounded
# value is a memory/CPU exhaustion primitive rather than a big request.
# Measured: athletes=10000 -> an 8.6MB bundle, and name collisions begin as the
# per-NOC name pool (~180 combinations) runs out. 5000 is comfortably past any
# real delegation and well short of either problem.
MAX_COUNT = 5000
# Seeds are only ever used to seed random.Random; the ceiling exists so the
# value stays a plausible int rather than an arbitrarily large one.
MAX_SEED = 1_000_000


class GenerateRequest(BaseModel):
    discipline: str
    pack: str | None = None
    seed: int = Field(default=1, ge=0, le=MAX_SEED)
    # header overrides (optional)
    competition_code: str | None = None
    source: str | None = None
    gen: str | None = None
    sport: str | None = None
    codes: str | None = None
    status: str | None = None
    # entry-count overrides (optional; blank = discipline default).
    # Bounded, and negatives rejected at the boundary rather than silently
    # mapped to None inside Overrides.normalize() -- a typo should be an
    # error, not an ignored field.
    athletes: int | None = Field(default=None, ge=0, le=MAX_COUNT)
    teams: int | None = Field(default=None, ge=0, le=MAX_COUNT)
    coaches: int | None = Field(default=None, ge=0, le=MAX_COUNT)
    # live-operations realism options (all default off = codes-driven)
    realistic_entries: bool = False
    seeded_heats: bool = False
    victory_ceremonies: bool = False
    historical_athletes: bool = False

    def overrides(self) -> Overrides:
        return Overrides(
            competition_code=self.competition_code, source=self.source,
            gen=self.gen, sport=self.sport, codes=self.codes,
            status=self.status, athletes=self.athletes, teams=self.teams,
            coaches=self.coaches,
            realistic_entries=self.realistic_entries,
            seeded_heats=self.seeded_heats,
            victory_ceremonies=self.victory_ceremonies,
            historical_athletes=self.historical_athletes)


@app.get("/api/packs")
def packs():
    default, error = _resolve_default()
    content = {"default": default,
               "packs": [s.to_dict() for s in REGISTRY.statuses()]}
    if error is not None:
        content["default_error"] = error
    return content


@app.get("/api/disciplines")
def disciplines(pack: str | None = None):
    try:
        name, refdata = resolve(pack, require_ready=False)
    except (UnknownPack, PackNotReady) as e:
        return _pack_error(e, pack)
    return {"pack": name, "disciplines": refdata.disciplines()}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    try:
        name, refdata = resolve(req.pack)
    except (UnknownPack, PackNotReady) as e:
        return _pack_error(e, req.pack)
    if req.discipline not in refdata.disciplines():
        return JSONResponse(status_code=400,
                            content={"error": f"unknown discipline: {req.discipline}"})
    bundle = build_bundle(refdata, req.discipline, req.seed,
                          overrides=req.overrides())
    # 200 even when the bundle is not clean: the readout is built to show
    # per-message findings, and hiding a dirty bundle behind an error would
    # remove the operator's only view of what is wrong. But say so explicitly
    # -- `clean` is a single field a script can check, where previously the
    # only signal was digging through messages[*].errors.
    #
    # `seed` is the seed that actually produced this data, which is not
    # necessarily req.seed: build_bundle retries with seed+1..+4 when a
    # message has findings. Reproducing a bundle needs the real one.
    return {
        "pack": name,
        "discipline": req.discipline,
        "seed": bundle.seed_used,
        "seed_requested": req.seed,
        "clean": bundle.clean,
        "messages": {
            doc_type: {"xml": xml.decode("utf-8"), "errors": errs}
            for doc_type, (xml, errs) in bundle.items()
        },
    }


@app.post("/api/save")
def save(req: GenerateRequest):
    try:
        _name, refdata = resolve(req.pack)
    except (UnknownPack, PackNotReady) as e:
        return _pack_error(e, req.pack)
    if req.discipline not in refdata.disciplines():
        return JSONResponse(status_code=400,
                            content={"error": f"unknown discipline: {req.discipline}"})
    try:
        written = export_bundle(refdata, req.discipline, req.seed,
                                overrides=req.overrides())
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    try:
        rel = [str(p.relative_to(PROJECT_ROOT)) for p in written]
    except ValueError:
        rel = [str(p) for p in written]
    return {"discipline": req.discipline, "saved": rel, "count": len(written)}


@app.get("/", response_class=HTMLResponse)
def index():
    return TEMPLATE.read_text(encoding="utf-8")


@app.get("/api/generate.zip")
def generate_zip(discipline: str,
                 seed: int = Query(1, ge=0, le=MAX_SEED),
                 pack: str | None = None,
                 competition_code: str | None = None, source: str | None = None,
                 gen: str | None = None, sport: str | None = None,
                 codes: str | None = None, status: str | None = None,
                 # Bounded like GenerateRequest, and it matters more here: this
                 # is a GET, so a cross-origin page can trigger it with a plain
                 # <img src> -- no preflight, no need to read the response.
                 # Unbounded counts made that a one-tag denial of service
                 # against the operator's own machine.
                 athletes: int | None = Query(None, ge=0, le=MAX_COUNT),
                 teams: int | None = Query(None, ge=0, le=MAX_COUNT),
                 coaches: int | None = Query(None, ge=0, le=MAX_COUNT),
                 realistic_entries: bool = False, seeded_heats: bool = False,
                 victory_ceremonies: bool = False,
                 historical_athletes: bool = False):
    try:
        _name, refdata = resolve(pack)
    except (UnknownPack, PackNotReady) as e:
        return _pack_error(e, pack)
    if discipline not in refdata.disciplines():
        return JSONResponse(status_code=400,
                            content={"error": f"unknown discipline: {discipline}"})
    ov = Overrides(competition_code=competition_code, source=source, gen=gen,
                   sport=sport, codes=codes, status=status, athletes=athletes,
                   teams=teams, coaches=coaches,
                   realistic_entries=realistic_entries,
                   seeded_heats=seeded_heats,
                   victory_ceremonies=victory_ceremonies,
                   historical_athletes=historical_athletes)
    bundle = build_bundle(refdata, discipline, seed, overrides=ov)
    if not bundle.clean:
        return JSONResponse(status_code=422, content=bundle.errors)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc_type, (xml, _errs) in bundle.items():
            zf.writestr(f"{doc_type}.xml", xml)
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition":
                             f'attachment; filename="{discipline}_bundle.zip"'})
