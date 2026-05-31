import mimetypes
from datetime import date
from pathlib import PurePosixPath
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.dependencies import (
    get_analysis_service,
    get_document_store,
    get_illness_service,
    get_person_service,
    get_visit_service,
)
from app.repositories.relations import RelationRepository
from app.schemas import AnalysisCreate, IllnessCreate, Person, VisitCreate
from app.services.analyses import AnalysisService
from app.services.documents import DocumentStore
from app.services.illnesses import IllnessService
from app.services.people import PersonService
from app.services.visits import VisitService
from app.templating import templates

router = APIRouter(tags=["pages"])


def _age(birth: date | None) -> int | None:
    if not birth:
        return None
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def _none(value: str | None) -> str | None:
    """Пустую строку из формы трактуем как отсутствие значения."""
    value = (value or "").strip()
    return value or None


def _parse_date(value: str) -> date:
    return date.fromisoformat(value.strip())


def _parse_date_opt(value: str | None) -> date | None:
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None


def _require_person(service: PersonService, person_id: int) -> Person:
    person = service.get_person(person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Человек не найден")
    return person


def _attach_scan(
    service: AnalysisService | VisitService,
    record_id: int,
    person_name: str,
    upload: UploadFile | None,
    inbox_name: str | None,
) -> None:
    """Привязать скан к записи: приоритет у загруженного файла, иначе из «входящих».

    Работает и для анализов, и для визитов — у обоих сервисов одинаковые методы
    ``attach_uploaded`` / ``attach_from_inbox``.
    """
    if upload is not None and upload.filename:
        data = upload.file.read()
        ext = PurePosixPath(upload.filename).suffix
        service.attach_uploaded(record_id, person_name, data, ext)
    elif inbox_name:
        service.attach_from_inbox(record_id, person_name, inbox_name)


def _redirect(person_id: int) -> RedirectResponse:
    return RedirectResponse(url=f"/person/{person_id}", status_code=303)


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    service: PersonService = Depends(get_person_service),
) -> HTMLResponse:
    people = service.list_people()
    rows = [{"person": p, "age": _age(p.birth_date)} for p in people]
    return templates.TemplateResponse(request, "index.html", {"people": rows})


@router.get("/person/{person_id}", response_class=HTMLResponse)
def person_page(
    person_id: int,
    request: Request,
    service: PersonService = Depends(get_person_service),
) -> HTMLResponse:
    person = service.get_person(person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Человек не найден")
    timeline = service.get_timeline(person_id)
    relations = RelationRepository().list_for_person(person_id)
    return templates.TemplateResponse(
        request,
        "person.html",
        {
            "person": person,
            "age": _age(person.birth_date),
            "timeline": timeline,
            "relations": relations,
        },
    )


@router.get("/documents/{analysis_id}")
def view_document(
    analysis_id: int,
    analyses: AnalysisService = Depends(get_analysis_service),
    store: DocumentStore = Depends(get_document_store),
) -> Response:
    """Отдать исходный документ анализа (inline). Источник истины — скан в хранилище.

    Байты читаются через бэкенд (local или smb), поэтому маршрут не зависит от
    того, лежит файл на диске или на сетевой шаре.
    """
    analysis = analyses.get(analysis_id)
    if analysis is None or not analysis.document_path:
        raise HTTPException(status_code=404, detail="Документ не привязан")
    data = store.read(analysis.document_path)
    if data is None:
        raise HTTPException(status_code=404, detail="Файл документа не найден в хранилище")
    name = analysis.document_path.rsplit("/", 1)[-1]
    media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=utf-8''{quote(name)}"},
    )


def _serve(document_path: str | None, store: DocumentStore) -> Response:
    """Отдать файл документа по относительному пути (inline)."""
    if not document_path:
        raise HTTPException(status_code=404, detail="Документ не привязан")
    data = store.read(document_path)
    if data is None:
        raise HTTPException(status_code=404, detail="Файл документа не найден в хранилище")
    name = document_path.rsplit("/", 1)[-1]
    media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=utf-8''{quote(name)}"},
    )


@router.get("/visit-documents/{visit_id}")
def view_visit_document(
    visit_id: int,
    visits: VisitService = Depends(get_visit_service),
    store: DocumentStore = Depends(get_document_store),
) -> Response:
    """Отдать исходный документ визита (inline)."""
    v = visits.get(visit_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Визит не найден")
    return _serve(v.document_path, store)


# ──────────────────────────── Анализы (CRUD) ────────────────────────────


@router.get("/person/{person_id}/analysis/new", response_class=HTMLResponse)
def new_analysis(
    person_id: int,
    request: Request,
    people: PersonService = Depends(get_person_service),
    store: DocumentStore = Depends(get_document_store),
) -> HTMLResponse:
    person = _require_person(people, person_id)
    return templates.TemplateResponse(
        request,
        "analysis_form.html",
        {"person": person, "obj": None, "action": f"/person/{person_id}/analysis",
         "inbox": store.list_inbox()},
    )


@router.post("/person/{person_id}/analysis")
def create_analysis(
    person_id: int,
    analysis_date: str = Form(..., alias="date"),
    title: str = Form(...),
    category: str = Form(""),
    lab: str = Form(""),
    notes: str = Form(""),
    inbox_name: str = Form(""),
    upload: UploadFile | None = File(None),
    people: PersonService = Depends(get_person_service),
    analyses: AnalysisService = Depends(get_analysis_service),
) -> RedirectResponse:
    person = _require_person(people, person_id)
    aid = analyses.create(
        person.id,
        AnalysisCreate(date=_parse_date(analysis_date), title=title, category=_none(category),
                       lab=_none(lab), notes=_none(notes)),
    )
    _attach_scan(analyses, aid, person.name, upload, _none(inbox_name))
    return _redirect(person.id)


@router.get("/analysis/{analysis_id}/edit", response_class=HTMLResponse)
def edit_analysis(
    analysis_id: int,
    request: Request,
    people: PersonService = Depends(get_person_service),
    analyses: AnalysisService = Depends(get_analysis_service),
    store: DocumentStore = Depends(get_document_store),
) -> HTMLResponse:
    a = analyses.get(analysis_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Анализ не найден")
    person = _require_person(people, a.person_id)
    return templates.TemplateResponse(
        request,
        "analysis_form.html",
        {"person": person, "obj": a, "action": f"/analysis/{analysis_id}",
         "inbox": store.list_inbox()},
    )


@router.post("/analysis/{analysis_id}")
def update_analysis(
    analysis_id: int,
    analysis_date: str = Form(..., alias="date"),
    title: str = Form(...),
    category: str = Form(""),
    lab: str = Form(""),
    notes: str = Form(""),
    inbox_name: str = Form(""),
    upload: UploadFile | None = File(None),
    analyses: AnalysisService = Depends(get_analysis_service),
    people: PersonService = Depends(get_person_service),
) -> RedirectResponse:
    a = analyses.get(analysis_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Анализ не найден")
    analyses.update(
        analysis_id,
        AnalysisCreate(date=_parse_date(analysis_date), title=title, category=_none(category),
                       lab=_none(lab), notes=_none(notes)),
    )
    person = _require_person(people, a.person_id)
    _attach_scan(analyses, analysis_id, person.name, upload, _none(inbox_name))
    return _redirect(a.person_id)


@router.post("/analysis/{analysis_id}/delete")
def delete_analysis(
    analysis_id: int,
    analyses: AnalysisService = Depends(get_analysis_service),
) -> RedirectResponse:
    a = analyses.get(analysis_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Анализ не найден")
    analyses.delete(analysis_id)
    return _redirect(a.person_id)


# ──────────────────────────── Визиты (CRUD) ────────────────────────────


@router.get("/person/{person_id}/visit/new", response_class=HTMLResponse)
def new_visit(
    person_id: int,
    request: Request,
    people: PersonService = Depends(get_person_service),
    store: DocumentStore = Depends(get_document_store),
) -> HTMLResponse:
    person = _require_person(people, person_id)
    return templates.TemplateResponse(
        request,
        "visit_form.html",
        {"person": person, "obj": None, "action": f"/person/{person_id}/visit",
         "inbox": store.list_inbox()},
    )


@router.post("/person/{person_id}/visit")
def create_visit(
    person_id: int,
    visit_date: str = Form(..., alias="date"),
    specialty: str = Form(""),
    doctor_name: str = Form(""),
    clinic: str = Form(""),
    conclusion: str = Form(""),
    notes: str = Form(""),
    inbox_name: str = Form(""),
    upload: UploadFile | None = File(None),
    people: PersonService = Depends(get_person_service),
    visits: VisitService = Depends(get_visit_service),
) -> RedirectResponse:
    person = _require_person(people, person_id)
    vid = visits.create(
        person.id,
        VisitCreate(date=_parse_date(visit_date), specialty=_none(specialty),
                    doctor_name=_none(doctor_name), clinic=_none(clinic),
                    conclusion=_none(conclusion), notes=_none(notes)),
    )
    _attach_scan(visits, vid, person.name, upload, _none(inbox_name))
    return _redirect(person.id)


@router.get("/visit/{visit_id}/edit", response_class=HTMLResponse)
def edit_visit(
    visit_id: int,
    request: Request,
    people: PersonService = Depends(get_person_service),
    visits: VisitService = Depends(get_visit_service),
    store: DocumentStore = Depends(get_document_store),
) -> HTMLResponse:
    v = visits.get(visit_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Визит не найден")
    person = _require_person(people, v.person_id)
    return templates.TemplateResponse(
        request,
        "visit_form.html",
        {"person": person, "obj": v, "action": f"/visit/{visit_id}",
         "inbox": store.list_inbox()},
    )


@router.post("/visit/{visit_id}")
def update_visit(
    visit_id: int,
    visit_date: str = Form(..., alias="date"),
    specialty: str = Form(""),
    doctor_name: str = Form(""),
    clinic: str = Form(""),
    conclusion: str = Form(""),
    notes: str = Form(""),
    inbox_name: str = Form(""),
    upload: UploadFile | None = File(None),
    visits: VisitService = Depends(get_visit_service),
    people: PersonService = Depends(get_person_service),
) -> RedirectResponse:
    v = visits.get(visit_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Визит не найден")
    visits.update(
        visit_id,
        VisitCreate(date=_parse_date(visit_date), specialty=_none(specialty),
                    doctor_name=_none(doctor_name), clinic=_none(clinic),
                    conclusion=_none(conclusion), notes=_none(notes)),
    )
    person = _require_person(people, v.person_id)
    _attach_scan(visits, visit_id, person.name, upload, _none(inbox_name))
    return _redirect(v.person_id)


@router.post("/visit/{visit_id}/delete")
def delete_visit(
    visit_id: int,
    visits: VisitService = Depends(get_visit_service),
) -> RedirectResponse:
    v = visits.get(visit_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Визит не найден")
    visits.delete(visit_id)
    return _redirect(v.person_id)


# ──────────────────────────── Болезни (CRUD) ────────────────────────────


@router.get("/person/{person_id}/illness/new", response_class=HTMLResponse)
def new_illness(
    person_id: int,
    request: Request,
    people: PersonService = Depends(get_person_service),
) -> HTMLResponse:
    person = _require_person(people, person_id)
    return templates.TemplateResponse(
        request,
        "illness_form.html",
        {"person": person, "obj": None, "action": f"/person/{person_id}/illness"},
    )


@router.post("/person/{person_id}/illness")
def create_illness(
    person_id: int,
    start_date: str = Form(...),
    title: str = Form(...),
    end_date: str = Form(""),
    status: str = Form(""),
    notes: str = Form(""),
    people: PersonService = Depends(get_person_service),
    illnesses: IllnessService = Depends(get_illness_service),
) -> RedirectResponse:
    person = _require_person(people, person_id)
    illnesses.create(
        person.id,
        IllnessCreate(start_date=_parse_date(start_date), title=title,
                      end_date=_parse_date_opt(end_date),
                      status=_none(status), notes=_none(notes)),
    )
    return _redirect(person.id)


@router.get("/illness/{illness_id}/edit", response_class=HTMLResponse)
def edit_illness(
    illness_id: int,
    request: Request,
    people: PersonService = Depends(get_person_service),
    illnesses: IllnessService = Depends(get_illness_service),
) -> HTMLResponse:
    i = illnesses.get(illness_id)
    if i is None:
        raise HTTPException(status_code=404, detail="Болезнь не найдена")
    person = _require_person(people, i.person_id)
    return templates.TemplateResponse(
        request,
        "illness_form.html",
        {"person": person, "obj": i, "action": f"/illness/{illness_id}"},
    )


@router.post("/illness/{illness_id}")
def update_illness(
    illness_id: int,
    start_date: str = Form(...),
    title: str = Form(...),
    end_date: str = Form(""),
    status: str = Form(""),
    notes: str = Form(""),
    illnesses: IllnessService = Depends(get_illness_service),
) -> RedirectResponse:
    i = illnesses.get(illness_id)
    if i is None:
        raise HTTPException(status_code=404, detail="Болезнь не найдена")
    illnesses.update(
        illness_id,
        IllnessCreate(start_date=_parse_date(start_date), title=title,
                      end_date=_parse_date_opt(end_date),
                      status=_none(status), notes=_none(notes)),
    )
    return _redirect(i.person_id)


@router.post("/illness/{illness_id}/delete")
def delete_illness(
    illness_id: int,
    illnesses: IllnessService = Depends(get_illness_service),
) -> RedirectResponse:
    i = illnesses.get(illness_id)
    if i is None:
        raise HTTPException(status_code=404, detail="Болезнь не найдена")
    illnesses.delete(illness_id)
    return _redirect(i.person_id)
