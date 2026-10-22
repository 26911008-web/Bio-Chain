"""Skema request/response Engine ⑤ Route Optimizer (CVRP berbatas volume).

`computation_details` wajib ada di setiap respons: langkah, rumus, hasil antara, dan waktu
eksekusi tiap tahap, sehingga frontend bisa menampilkan "kenapa rutenya begini".
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..params import P

SolverMode = Literal["auto", "heuristic", "exact"]


class RouteRequest(BaseModel):
    mill_ids: list[str] | None = None
    vehicle_m3: float = Field(default_factory=lambda: P("logistik.vehicle_m3"), gt=0, le=1_000,
                              description="Volume bak kendaraan (default: menu Parameter)")
    bulk_density_kg_m3: float = Field(default_factory=lambda: P("logistik.bulk_density_kg_m3"), gt=0, le=1_000)
    cost_per_km: float = Field(default_factory=lambda: P("logistik.cost_per_km"), ge=0,
                               description="Rp/km (BBM + sopir + penyusutan)")
    mode: SolverMode = Field(
        "auto",
        description="auto = exact bila titik ≤ EXACT_AUTO_MAX, selain itu heuristic. "
                    "exact = DP set-partitioning (maks EXACT_HARD_MAX titik).",
    )
    time_budget_ms: int = Field(default_factory=lambda: int(P("logistik.time_budget_ms")), ge=10, le=2_000,
                                description="Anggaran waktu end-to-end (heuristic)")


class Stop(BaseModel):
    id: str
    name: str
    m3: float
    ton: float


class Route(BaseModel):
    stops: list[Stop]
    path: list[list[float]]
    km: float
    load_m3: float
    load_ton: float
    utilization_pct: float


class RouteSummary(BaseModel):
    mills: int
    total_ton: float
    vehicles_trips: int
    total_km: float
    total_cost: int
    cost_per_ton: int
    baseline_km: float
    saving_pct: float
    max_ton_per_trip: float
    algorithm: str


class ComputationStep(BaseModel):
    step: int
    name: str
    explanation: str
    formula: str | None = None
    complexity: str | None = None
    result: dict[str, Any] = {}
    elapsed_ms: float


class SolutionQuality(BaseModel):
    objective_km: float = Field(description="Total jarak rute hasil solver")
    lower_bound_km: float = Field(description="Batas bawah teoritis; solusi optimal tidak mungkin lebih pendek")
    gap_upper_bound_pct: float = Field(description="Selisih maksimum terhadap optimal: (objektif − LB) / objektif")
    proven_optimal: bool


class ComputationDetails(BaseModel):
    problem: dict[str, Any]
    mode_requested: SolverMode
    mode_used: Literal["exact", "heuristic", "trivial"]
    mode_reason: str
    steps: list[ComputationStep]
    quality: SolutionQuality
    references: list[str]
    total_elapsed_ms: float


class RouteResponse(BaseModel):
    routes: list[Route]
    summary: RouteSummary
    computation_details: ComputationDetails
