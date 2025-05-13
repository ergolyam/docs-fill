from pathlib import Path
import datetime, uuid, shutil, subprocess, os, tempfile
from typing import cast
from io import BytesIO
import re, zipfile, yaml, json
from functools import lru_cache

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile
from docxtpl import DocxTemplate

trans_file = Path(__file__).parent / "translations.json"
with trans_file.open("r", encoding="utf-8") as f:
    trans = json.load(f)

available_langs = ["en", "ru"]
default_lang = "en"

docs_dir = Path(__file__).parent / "docx_templates"

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/templates", StaticFiles(directory=Path(__file__).parent / "templates"), name="templates")


def get_lang(request: Request) -> str:
    lang_cookie = request.cookies.get('lang')
    if lang_cookie and lang_cookie in available_langs:
        return lang_cookie

    accept_language = request.headers.get("Accept-Language", "")
    if accept_language:
        first_lang = accept_language.split(",")[0].lower()
        for lang_code in available_langs:
            if first_lang.startswith(lang_code):
                return lang_code

    return default_lang


@app.get("/set_lang", name="set_lang")
def set_lang(request: Request, lang: str = "ru"):
    if lang not in available_langs:
        lang = default_lang
    referer = request.headers.get("referer") or "/"
    response = RedirectResponse(url=referer)
    response.set_cookie(key="lang", value=lang, max_age=3600*24*365)
    return response


def _extract_vars_from_docx(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode()
    return set(re.findall(r"{{\s*([a-zA-Z0-9_]+)\s*}}", xml))


@lru_cache
def get_vars(template_name: str) -> set[str]:
    path = docs_dir / template_name
    doc = DocxTemplate(path)
    try:
        return doc.get_undeclared_template_variables()
    except AttributeError:
        return _extract_vars_from_docx(path)


def load_yaml_meta(template_name: str) -> dict:
    yml = docs_dir / f"{Path(template_name).stem}.yaml"
    if yml.exists():
        with yml.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def build_field_defs(template_name: str) -> list[dict]:
    vars_ = get_vars(template_name)
    meta = load_yaml_meta(template_name)
    fields: list[dict] = []
    for v in sorted(vars_):
        m = meta.get(v, {})
        fields.append({
            "name": v,
            "label": m.get("label", v),
            "type": m.get("type", "string"),
            "choices": m.get("choices", []),
        })
    return fields


def convert_to_pdf(docx_path: Path) -> Path:
    pdf_path = docx_path.with_suffix(".pdf")
    try:
        from docx2pdf import convert
        convert(str(docx_path), str(pdf_path))
        return pdf_path
    except (ImportError, NotImplementedError):
        pass
    soffice = (
        os.environ.get("SOFFICE_PATH")
        or shutil.which("soffice")
        or shutil.which("libreoffice")
    )
    if soffice is None:
        raise HTTPException(500, "LibreOffice not found")
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf",
         "--outdir", str(docx_path.parent), str(docx_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        raise HTTPException(500, result.stderr.decode())
    return pdf_path


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    files = [p.name for p in docs_dir.glob("*.docx")]
    current_lang = get_lang(request)
    t = trans[current_lang]
    return templates.TemplateResponse(
        "index.html",
        {"request": request,
         "files": files,
         "t": t}
    )


@app.get("/fill/{tpl}", response_class=HTMLResponse)
async def fill(request: Request, tpl: str):
    fields = build_field_defs(tpl)
    current_lang = get_lang(request)
    t = trans[current_lang]
    return templates.TemplateResponse(
        "fill.html",
        {"request": request,
         "tpl": tpl,
         "fields": fields,
         "t": t}
    )


@app.post("/generate")
async def generate(request: Request):
    form = await request.form()
    data: dict[str, str] = {
        k: (v if isinstance(v, str)
            else cast(UploadFile, v).filename or "")
        for k, v in form.items()
    }
    tpl = data.pop("tpl")
    fmt = data.pop("fmt", "docx").lower()

    ctx: dict[str, object] = {}
    for f in build_field_defs(tpl):
        raw = data.get(f["name"], "")
        match f["type"]:
            case "date":
                ctx[f["name"]] = datetime.datetime.strptime(
                    raw, "%Y-%m-%d"
                ).strftime("%d.%m.%Y")
            case "int":
                ctx[f["name"]] = int(raw)
            case "float":
                ctx[f["name"]] = float(raw.replace(",", "."))
            case "bool":
                ctx[f["name"]] = raw.lower() in {"yes", "true", "1"}
            case _:
                ctx[f["name"]] = raw

    with tempfile.TemporaryDirectory() as tmpdirname:
        work_dir = Path(tmpdirname)
        docx_path = work_dir / f"{uuid.uuid4().hex}.docx"
        template = DocxTemplate(docs_dir / tpl)
        template.render(ctx)
        template.save(docx_path)

        if fmt == "pdf":
            file_path = convert_to_pdf(docx_path)
            media = "application/pdf"
        else:
            file_path = docx_path
            media = ("application/vnd.openxmlformats-officedocument."
                     "wordprocessingml.document")

        with file_path.open("rb") as f:
            buf = BytesIO(f.read())
        buf.seek(0)

    headers = {"Content-Disposition": f'attachment; filename="{file_path.name}"'}
    return StreamingResponse(buf, media_type=media, headers=headers)


if __name__ == '__main__':
    import uvicorn
    port = os.getenv("PORT", "8000")
    reload = os.getenv("RELOAD", "False")
    uvicorn.run("main:app", host="::", port=int(port), reload=bool(reload))
