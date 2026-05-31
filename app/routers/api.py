from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_marker_service, get_person_service
from app.schemas import Marker, Person, TimelineEvent
from app.services.markers import MarkerService
from app.services.people import PersonService

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/people", response_model=list[Person])
def list_people(service: PersonService = Depends(get_person_service)) -> list[Person]:
    return service.list_people()


@router.get("/person/{person_id}/timeline", response_model=list[TimelineEvent])
def person_timeline(
    person_id: int,
    service: PersonService = Depends(get_person_service),
) -> list[TimelineEvent]:
    if service.get_person(person_id) is None:
        raise HTTPException(status_code=404, detail="Человек не найден")
    return service.get_timeline(person_id)


@router.get("/person/{person_id}/markers")
def person_markers(
    person_id: int,
    people: PersonService = Depends(get_person_service),
    markers: MarkerService = Depends(get_marker_service),
) -> list[dict[str, Any]]:
    """Ряды числовых показателей для графиков динамики (задел под следующий этап)."""
    if people.get_person(person_id) is None:
        raise HTTPException(status_code=404, detail="Человек не найден")
    return markers.series_for_person(person_id)


@router.get("/markers", response_model=list[Marker])
def list_markers(service: MarkerService = Depends(get_marker_service)) -> list[Marker]:
    return service.list_markers()
