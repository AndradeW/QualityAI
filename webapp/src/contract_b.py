"""Contract B: Test Architect → Code Generator.

Define el schema de salida del Agente 2 (Test Architect).
Transforma criterios de aceptación en casos de prueba Gherkin (BDD)
completos, con escenarios positivos, negativos y de borde.

Principios de diseño:
- Cada criterio de aceptación genera al menos 1 escenario Gherkin
- Los escenarios usan Scenario Outline + Examples para datos parametrizados
- Se incluyen tags para categorización (@smoke, @regression, @negative, etc.)
- El Gherkin generado debe ser parseable por cualquier runner BDD estándar
- Cada escenario se mapea a una característica de calidad ISO 25010
- El bucle de revisión humana del analista vive DENTRO del contrato (ReviewMetadata),
  formalizando al humano como parte del pipeline (ADR-M2-002)

Versión 0.2.0:
- Agrega ReviewMetadata para HITL del analista de calidad
- Agrega QualityCharacteristic (ISO 25010) por escenario

Versión 0.2.1:
- Mueve la serialización a texto .feature al paquete serializers/.
  Este archivo ahora contiene SOLO el schema (separación de concerns).
  Ver: modulo2_test_architect.serializers.gherkin_writer
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================
class ScenarioType(str, Enum):
    """Tipo de escenario Gherkin desde la perspectiva de testing."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    EDGE_CASE = "edge_case"
    ERROR_HANDLING = "error_handling"


class QualityCharacteristic(str, Enum):
    """Las 8 características de calidad de software según ISO 25010.

    Cada escenario Gherkin debe etiquetarse con la característica que valida.
    Esto permite construir matrices de cobertura por característica de calidad
    y detectar gaps (ej: AC marca performance pero no hay escenarios de carga).
    """

    FUNCTIONAL_SUITABILITY = "functional_suitability"  # ¿hace lo que debe?
    PERFORMANCE_EFFICIENCY = "performance_efficiency"  # ¿rendimiento adecuado?
    COMPATIBILITY = "compatibility"                    # ¿funciona en distintos entornos?
    USABILITY = "usability"                           # ¿es fácil de usar?
    RELIABILITY = "reliability"                       # ¿es estable y resiliente?
    SECURITY = "security"                             # ¿está protegido?
    MAINTAINABILITY = "maintainability"              # ¿es fácil de modificar?
    PORTABILITY = "portability"                       # ¿se puede mover de entorno?


class ReviewStatus(str, Enum):
    """Estado de revisión del Test Suite por parte del analista de calidad.

    El bucle Human-in-the-Loop está formalizado dentro del contrato
    (ADR-M2-002): el analista debe aprobar antes de que el suite avance al
    Módulo 3 (Code Generator).
    """

    PENDING_REVIEW = "pending_review"  # Recién generado, aún no revisado
    APPROVED = "approved"              # Aprobado, listo para Módulo 3
    REJECTED = "rejected"              # Rechazado, no avanza al Módulo 3
    NEEDS_CHANGES = "needs_changes"    # Aprobación condicional con cambios


# ============================================================
# REVIEW METADATA — Bucle de revisión humana
# ============================================================
class ReviewChange(BaseModel):
    """Una entrada en el historial de revisión.

    Cada acción del analista (aprobar, rechazar, comentar) genera un registro
    auditable para CMMI-DEV L3.
    """

    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Cuándo ocurrió la acción",
    )
    reviewer: str = Field(
        ...,
        description="Identificador del analista que realizó la acción",
        min_length=1,
    )
    action: str = Field(
        ...,
        description="Acción realizada: approved | rejected | comment_added | changes_requested",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Notas o comentarios del analista para esta acción",
    )


class ReviewMetadata(BaseModel):
    """Metadata del bucle de revisión humana del analista de calidad.

    Formaliza al analista como parte del contrato, no como anexo externo
    (ADR-M2-002). Sin esta aprobación, el suite NO debe avanzar al Módulo 3.
    """

    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING_REVIEW,
        description="Estado actual de la revisión",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Versión del suite (incrementa con cada revisión que solicita cambios)",
    )
    approved_by: Optional[str] = Field(
        default=None,
        description="Identificador del analista que aprobó (vacío si aún no aprobado)",
    )
    approved_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp de la aprobación (vacío si aún no aprobado)",
    )
    analyst_feedback: Optional[str] = Field(
        default=None,
        description="Comentario libre del analista sobre el suite completo",
    )
    change_history: list[ReviewChange] = Field(
        default_factory=list,
        description="Historial de acciones del analista para auditoría CMMI L3",
    )


# ============================================================
# GHERKIN PRIMITIVES
# ============================================================
class GherkinStep(BaseModel):
    """Un paso individual de un escenario Gherkin."""

    keyword: str = Field(
        ...,
        description="Keyword Gherkin: Given, When, Then, And, But",
        pattern=r"^(Given|When|Then|And|But)$",
    )
    text: str = Field(
        ...,
        description="Texto del paso sin el keyword",
        min_length=5,
    )
    data_table: Optional[list[dict]] = Field(
        default=None,
        description="Tabla de datos asociada al paso (si aplica)",
    )
    doc_string: Optional[str] = Field(
        default=None,
        description="Doc string asociado al paso (si aplica)",
    )


class ExamplesTable(BaseModel):
    """Tabla de ejemplos para Scenario Outline."""

    headers: list[str] = Field(..., description="Nombres de las columnas")
    rows: list[list[str]] = Field(..., description="Filas de datos", min_length=1)


# ============================================================
# GHERKIN SCENARIO
# ============================================================
class GherkinScenario(BaseModel):
    """Un escenario Gherkin completo.

    Cada escenario está mapeado a:
    - El criterio de aceptación que valida (acceptance_criterion_id)
    - La historia de usuario origen (user_story_id)
    - La característica de calidad ISO 25010 que evalúa (quality_characteristic)
    """

    name: str = Field(..., description="Nombre descriptivo del escenario", min_length=10)
    scenario_type: ScenarioType = Field(default=ScenarioType.POSITIVE)
    quality_characteristic: QualityCharacteristic = Field(
        default=QualityCharacteristic.FUNCTIONAL_SUITABILITY,
        description=(
            "Característica ISO 25010 que el escenario valida. "
            "Permite construir matrices de cobertura por característica de calidad."
        ),
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags del escenario (@smoke, @regression, etc.)",
    )
    steps: list[GherkinStep] = Field(
        ...,
        description="Pasos del escenario en orden",
        min_length=3,  # Mínimo Given, When, Then
    )
    is_outline: bool = Field(
        default=False,
        description="True si es un Scenario Outline con Examples",
    )
    examples: Optional[ExamplesTable] = Field(
        default=None,
        description="Tabla de ejemplos (solo si is_outline=True)",
    )

    # Trazabilidad
    acceptance_criterion_id: str = Field(
        ...,
        description="ID del criterio de aceptación que valida (ej: AC-001)",
    )
    user_story_id: str = Field(
        ...,
        description="ID de la historia de usuario origen (ej: US-001)",
    )


class GherkinFeature(BaseModel):
    """Un archivo .feature completo con sus escenarios."""

    name: str = Field(..., description="Nombre de la feature", min_length=10)
    description: str = Field(
        ...,
        description="Descripción de la feature (narrativa de negocio)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags de la feature",
    )
    background: Optional[list[GherkinStep]] = Field(
        default=None,
        description="Pasos de Background comunes a todos los escenarios",
    )
    scenarios: list[GherkinScenario] = Field(
        ...,
        description="Escenarios de la feature",
        min_length=1,
    )
    user_story_id: str = Field(
        ...,
        description="ID de la historia de usuario que cubre esta feature",
    )

    # NOTA: la serialización a texto .feature se realiza vía
    # modulo2_test_architect.serializers.gherkin_writer.feature_to_gherkin_text(feature).
    # Mantenemos el schema (este archivo) limpio de lógica de serialización
    # para respetar la separación de concerns.


# ============================================================
# COVERAGE MATRIX
# ============================================================
class CoverageMatrix(BaseModel):
    """Matriz de cobertura: qué criterios están cubiertos por qué escenarios."""

    user_story_id: str
    criterion_id: str
    scenario_names: list[str] = Field(
        ...,
        description="Escenarios que cubren este criterio",
        min_length=1,
    )
    coverage_type: list[ScenarioType] = Field(
        ...,
        description="Tipos de cobertura logrados",
    )
    quality_characteristics_covered: list[QualityCharacteristic] = Field(
        default_factory=list,
        description=(
            "Características ISO 25010 cubiertas para este criterio. "
            "Permite detectar gaps: si un AC toca security pero no hay escenarios "
            "con quality_characteristic=security, queda visible en la matriz."
        ),
    )


# ============================================================
# GHERKIN TEST SUITE — el contrato completo
# ============================================================
class GherkinTestSuite(BaseModel):
    """Contract B: Salida del Agente 2, entrada del Agente 3.

    Contiene todos los archivos .feature generados a partir de las historias
    de usuario refinadas, junto con la matriz de cobertura y la metadata
    del bucle de revisión humana.

    El campo `review` formaliza al analista de calidad humano como parte del
    contrato (no como anexo externo). Sin `review.review_status == APPROVED`,
    el suite NO debería avanzar al Módulo 3.
    """

    # Metadata del pipeline
    pipeline_run_id: str = Field(..., description="ID único de la ejecución del pipeline")
    agent_name: str = Field(default="test_architect")
    agent_version: str = Field(default="0.2.1")
    created_at: datetime = Field(default_factory=datetime.now)

    # Features generadas
    features: list[GherkinFeature] = Field(
        ...,
        description="Archivos .feature generados",
        min_length=1,
    )

    # Matriz de cobertura (trazabilidad AC → Escenarios)
    coverage_matrix: list[CoverageMatrix] = Field(
        ...,
        description="Mapeo de criterios de aceptación a escenarios",
    )

    # Bucle de revisión humana (HITL del analista de calidad)
    review: ReviewMetadata = Field(
        default_factory=ReviewMetadata,
        description=(
            "Metadata del bucle de revisión humana. "
            "Por defecto inicia en PENDING_REVIEW; el analista lo actualiza vía CLI."
        ),
    )

    # Métricas
    total_scenarios: int = Field(default=0)
    total_positive: int = Field(default=0)
    total_negative: int = Field(default=0)
    total_boundary: int = Field(default=0)
    uncovered_criteria: list[str] = Field(
        default_factory=list,
        description="IDs de criterios sin cobertura (debería estar vacío)",
    )

    # ISO 25010: matriz global de cobertura por característica de calidad (V3+)
    # En V1/V2 queda vacío. En V3 se puebla con conteo de escenarios por
    # QualityCharacteristic. Permite responder "¿cuántos escenarios cubren
    # security?" al stakeholder sin recorrer la lista de escenarios.
    coverage_by_characteristic: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Conteo de escenarios por característica ISO 25010 (V3+). "
            "Llave: nombre del enum QualityCharacteristic. Valor: cantidad. "
            "Vacío en V1/V2 — V3 lo puebla a partir de las clasificaciones del LLM."
        ),
    )
