from app.services.analyses import AnalysisService
from app.services.markers import MarkerService
from app.services.people import PersonService

# Фабрики сервисов как FastAPI-зависимости. Вынесены отдельно, чтобы тесты могли
# переопределять их через ``app.dependency_overrides``.


def get_person_service() -> PersonService:
    return PersonService()


def get_analysis_service() -> AnalysisService:
    return AnalysisService()


def get_marker_service() -> MarkerService:
    return MarkerService()
