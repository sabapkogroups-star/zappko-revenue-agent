from typing import List, Optional

from pydantic import BaseModel


class DiscoveryRequest(BaseModel):
    industry: str
    city: str
    country: str
    limit: int = 20
    page: int = 1  # 1-based pagination


class AuditResult(BaseModel):
    websiteScore: int
    issues: List[str]
    recommendedService: List[str]


class LeadScore(BaseModel):
    opportunityScore: int
    dealValue: str
    hotLeadScore: int


class ProposalRequest(BaseModel):
    company: str
    website: str
    decisionMaker: Optional[str] = ""
    title: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    websiteScore: int
    opportunityScore: int
    hotLeadScore: int = 0
    dealValue: str
    issues: List[str]
    recommendedService: List[str]


class FollowUpRequest(BaseModel):
    company: str
    website: str
    decisionMaker: Optional[str] = ""
    title: Optional[str] = ""
    websiteScore: int
    dealValue: str
    issues: List[str]
    recommendedService: List[str]


class FollowUpMessage(BaseModel):
    label: str
    dayOffset: int
    subject: str
    body: str


class FollowUpResponse(BaseModel):
    followUps: List[FollowUpMessage]


class RecommendationRequest(BaseModel):
    leads: List[dict]


class Recommendation(BaseModel):
    priority: str
    action: str
    company: str
    reason: str
    expectedValue: str


class PipelineHealthModel(BaseModel):
    score: int
    label: str
    staleLeads: int
    dueFollowUps: int
    hotLeads: int


class RecommendationResponse(BaseModel):
    recommendations: List[Recommendation]
    pipelineHealth: PipelineHealthModel


class LeadResult(BaseModel):
    company: str
    website: str
    decisionMaker: Optional[str] = ""
    title: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    linkedinUrl: Optional[str] = ""
    contactConfidence: Optional[float] = 0.0
    # Data quality flags
    emailVerified: Optional[bool] = False
    phoneVerified: Optional[bool] = False
    # Discovery metadata
    source: Optional[str] = ""
    confidence: Optional[float] = 0.0
    discoveredAt: Optional[str] = ""
    # Audit results
    websiteScore: int
    opportunityScore: int
    hotLeadScore: int
    dealValue: str
    issues: List[str]
    recommendedService: List[str]
    emailDraft: str
    whatsappDraft: str
