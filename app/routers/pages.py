from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.dependencies import get_person_service
from app.repositories.relations import RelationRepository
from app.services.people import PersonService
from app.templating import templates

router = APIRouter(tags=["pages"])


def _age(birth: date | None) -> int | None:
    if not birth:
        return None
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


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
