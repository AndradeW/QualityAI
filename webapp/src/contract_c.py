"""Contract C: Code Generator → Functional Tester.

Define el schema de salida del Agente 3 (Code Generator).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.contract_b import QualityCharacteristic, ReviewStatus


class MeasurementStatus(str, Enum):
    MEASURED = "measured"
    REQUIRES_HUMAN_JUDGMENT = "requires_human_judgment"
    NOT_APPLICABLE = "not_applicable"


class ComplexityBand(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class TraceabilityStatus(str, Enum):
    COVERED = "covered"
    ORPHAN_FORWARD = "orphan_forward"
    ORPHAN_BACKWARD = "orphan_backward"


class SecuritySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GeneratedCodeModule(BaseModel):
    filename: str = Field(..., min_length=3)
    source_code: str = Field(..., min_length=10)
    description: str = Field(...)
    user_story_id: str = Field(...)


class GeneratedTest(BaseModel):
    test_name: str = Field(..., min_length=5)
    source_code: str = Field(..., min_length=10)
    scenario_ids: list[str] = Field(default_factory=list)
    target_module: str = Field(...)


class FunctionMetrics(BaseModel):
    function_name: str = Field(...)
    module: str = Field(...)
    cyclomatic_complexity: int = Field(..., ge=1)
    cognitive_complexity: int = Field(..., ge=0)
    cc_band: ComplexityBand = Field(...)
    nesting_depth: int = Field(default=0, ge=0)
    exceeds_threshold: bool = Field(default=False)


class SecurityFinding(BaseModel):
    test_id: str = Field(...)
    severity: SecuritySeverity = Field(...)
    module: str = Field(...)
    line_number: int = Field(..., ge=1)
    description: str = Field(...)


class QualityCharacteristicResult(BaseModel):
    characteristic: QualityCharacteristic = Field(...)
    status: MeasurementStatus = Field(...)
    metrics_used: list[str] = Field(default_factory=list)
    verdict: Optional[str] = Field(default=None)


class QualityReport(BaseModel):
    function_metrics: list[FunctionMetrics] = Field(default_factory=list)
    maintainability_index: Optional[float] = Field(default=None)
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    iso_25010_coverage: list[QualityCharacteristicResult] = Field(default_factory=list)
    functions_exceeding_threshold: int = Field(default=0, ge=0)


class ScenarioTraceability(BaseModel):
    scenario_id: str = Field(...)
    scenario_name: str = Field(...)
    covering_tests: list[str] = Field(default_factory=list)
    status: TraceabilityStatus = Field(...)


class TestTraceability(BaseModel):
    test_name: str = Field(...)
    justifying_scenarios: list[str] = Field(default_factory=list)
    status: TraceabilityStatus = Field(...)


class TraceabilityMatrix(BaseModel):
    forward: list[ScenarioTraceability] = Field(default_factory=list)
    backward: list[TestTraceability] = Field(default_factory=list)
    requirements_coverage_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    tests_justified_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    orphan_scenarios: list[str] = Field(default_factory=list)
    orphan_tests: list[str] = Field(default_factory=list)
    cmmi_l3_compliant: bool = Field(default=False)


class CoverageReport(BaseModel):
    branch_coverage_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    line_coverage_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    meets_threshold: bool = Field(default=False)
    uncovered_modules: list[str] = Field(default_factory=list)


class ReviewChange(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    reviewer: str = Field(..., min_length=1)
    action: str = Field(...)
    target: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class ReviewMetadata(BaseModel):
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING_REVIEW)
    version: int = Field(default=1, ge=1)
    approved_by: Optional[str] = Field(default=None)
    approved_at: Optional[datetime] = Field(default=None)
    reviewer_feedback: Optional[str] = Field(default=None)
    change_history: list[ReviewChange] = Field(default_factory=list)


class CodeGenerationResult(BaseModel):
    pipeline_run_id: str = Field(...)
    agent_name: str = Field(default="code_generator")
    agent_version: str = Field(default="0.1.0")
    created_at: datetime = Field(default_factory=datetime.now)
    source_contract_b_id: str = Field(...)
    generated_code: list[GeneratedCodeModule] = Field(..., min_length=1)
    generated_tests: list[GeneratedTest] = Field(..., min_length=1)
    quality_report: Optional[QualityReport] = Field(default=None)
    traceability_matrix: Optional[TraceabilityMatrix] = Field(default=None)
    coverage_report: Optional[CoverageReport] = Field(default=None)
    review: ReviewMetadata = Field(default_factory=ReviewMetadata)
    total_modules: int = Field(default=0, ge=0)
    total_tests: int = Field(default=0, ge=0)
