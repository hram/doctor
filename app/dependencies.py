from app.services.analyses import AnalysisService
from app.services.documents import DocumentStore, build_document_store
from app.services.illnesses import IllnessService
from app.services.markers import MarkerService
from app.services.people import PersonService
from app.services.visits import VisitService

# Фабрики сервисов как FastAPI-зависимости. Вынесены отдельно, чтобы тесты могли
# переопределять их через ``app.dependency_overrides``.


def get_person_service() -> PersonService:
    return PersonService()


def get_analysis_service() -> AnalysisService:
    return AnalysisService()


def get_marker_service() -> MarkerService:
    return MarkerService()


def get_visit_service() -> VisitService:
    return VisitService()


def get_illness_service() -> IllnessService:
    return IllnessService()


def get_document_store() -> DocumentStore:
    return build_document_store()
