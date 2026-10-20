from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class InvestigationRequest(StrictModel):
    question: str = Field(min_length=8, max_length=2000)
    mode: Literal["question", "discover"] = "question"

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        value = value.strip()
        if len(value) < 8:
            raise ValueError("Please provide a meaningful investigation question")
        return value


class DemoRequest(StrictModel):
    pack: Literal["supply", "margin"] = "supply"


class Decision(StrictModel):
    decision: Literal["approve", "reject"]


class AgentHypothesis(StrictModel):
    id: str = Field(pattern=r"^H[1-6]$")
    claim: str = Field(min_length=5, max_length=400)


class AgentStep(StrictModel):
    rationale: str = Field(min_length=5, max_length=500)
    hypotheses: list[AgentHypothesis] = Field(default_factory=list, max_length=6)
    tool: Literal[
        "detect_anomalies",
        "segment_performance",
        "get_inventory",
        "get_supplier_data",
        "get_deliveries",
        "get_customer_signals",
        "get_marketing",
        "get_margin_bridge",
        "get_delivery_costs",
        "get_supplier_costs",
        "search_documents",
        "finish",
    ]
    query: str = Field(default="", max_length=300)


class HypothesisVerdict(StrictModel):
    id: str = Field(pattern=r"^H[1-6]$")
    claim: str = Field(min_length=5, max_length=400)
    status: Literal["supported", "rejected", "inconclusive"]
    supporting_evidence: list[str] = Field(max_length=20)
    contradicting_evidence: list[str] = Field(max_length=20)
    explanation: str = Field(max_length=1000)


class AgentConclusion(StrictModel):
    root_cause: str = Field(min_length=10, max_length=2000)
    causal_chain: list[str] = Field(min_length=1, max_length=6)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    confidence: Literal["low", "medium", "high"]
    hypotheses: list[HypothesisVerdict] = Field(min_length=2, max_length=6)
    unknowns: list[str] = Field(min_length=1, max_length=10)
    recommended_action: str = Field(min_length=10, max_length=500)
