# backend/routers/evaluate.py
"""
The core evaluation endpoint — /v1/evaluate
This is what companies call on every login.
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from models.schemas import EvaluateRequest, EvaluateResponse, Decision
from middleware.api_key_auth import verify_api_key
from middleware.rate_limiter import check_rate_limit
from middleware.tenant_context import set_tenant
from engines.feature_pipeline import build_features
from engines.ml_engine import ml_engine
from engines.dna_engine import DNAEngine
from engines.risk_engine import RiskEngine
from engines.llm_explainer import LLMExplainer
from services.tenant_service import TenantService
from services.usage_service import UsageService
from services.webhook_service import WebhookService
from utils.hashing import generate_request_id
from datetime import datetime
import time
import asyncio

router = APIRouter(prefix="/v1", tags=["Risk Evaluation"])


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_login(
    request: Request,
    payload: EvaluateRequest,
    tenant: dict = Depends(verify_api_key)
):
    """
    🛡️ Evaluate a login attempt for risk.
    
    Send user signals (IP, device fingerprint, etc.) and receive:
    - **decision**: ALLOW / OTP / STEPUP / BLOCK
    - **score**: 0-100 risk score
    - **explanation**: Human-readable reason (powered by Mistral AI)
    - **risk_factors**: Detailed breakdown of risk contributors
    
    Companies should call this on every login attempt.
    
    **Response time target: <300ms**
    """
    start_time = time.time()
    request_id = generate_request_id()
    tenant_id = tenant["tenant_id"]

    # Set tenant context for this request
    set_tenant(tenant_id)

    # Check rate limit
    await check_rate_limit(request)

    try:
        # === Step 1: Get user's DNA profile (tenant-scoped) ===
        dna_profile = await DNAEngine.get_or_create_profile(
            tenant_id, payload.user_id
        )
        is_new_user = dna_profile is None

        # === Step 2: Build features from raw signals ===
        pipeline_result = await build_features(
            user_id=payload.user_id,
            ip=payload.ip,
            device_fp=payload.device_fp,
            resource=payload.resource,
            failed_attempts=payload.failed_attempts,
            timestamp=payload.timestamp,
            user_agent=payload.user_agent,
            dna_profile=dna_profile
        )

        features = pipeline_result["features"]
        metadata = pipeline_result["metadata"]
        metadata["is_new_user"] = is_new_user

        # === Step 3: ML model inference ===
        ml_scores = ml_engine.predict(features)

        # === Step 4: DNA match score ===
        dna_match = DNAEngine.compute_match_score(
            dna_profile, features, metadata
        )

        # === Step 5: Risk scoring + decision ===
        score, decision, risk_factors = RiskEngine.compute_risk(
            ml_scores=ml_scores,
            dna_match=dna_match,
            graph_risk=0.0,  # Graph engine optional
            features=features,
            metadata=metadata
        )

        # === Step 6: LLM explanation (Mistral AI) ===
        explanation = await LLMExplainer.explain(
            score=score,
            decision=decision.value,
            risk_factors=risk_factors,
            metadata=metadata,
            dna_match=dna_match
        )

        # === Step 7: Update DNA profile (if not blocked) ===
        if decision != Decision.BLOCK:
            asyncio.create_task(
                DNAEngine.update_profile(
                    tenant_id, payload.user_id, metadata, features
                )
            )

        # === Step 8: Log the evaluation ===
        processing_time_ms = int((time.time() - start_time) * 1000)

        log_data = {
            "request_id": request_id,
            "user_id": payload.user_id,
            "ip": payload.ip,
            "device_fp": payload.device_fp,
            "resource": payload.resource,
            "score": score,
            "decision": decision.value,
            "explanation": explanation,
            "dna_match": dna_match,
            "country": metadata.get("country"),
            "city": metadata.get("city"),
            "is_new_user": is_new_user,
            "processing_time_ms": processing_time_ms,
            "ml_scores": ml_scores,
            "features": features
        }

        # Fire-and-forget: log + usage tracking
        asyncio.create_task(TenantService.store_login_log(tenant_id, log_data))
        asyncio.create_task(
            UsageService.log_usage(tenant_id, decision.value, processing_time_ms, score)
        )
        asyncio.create_task(TenantService.increment_api_calls(tenant_id))

        # === Step 9: Webhook for BLOCK/STEPUP/OTP ===
        if decision in (Decision.BLOCK, Decision.STEPUP, Decision.OTP):
            webhook_url = tenant.get("webhook_url")
            if webhook_url:
                event_type = f"risk.{decision.value.lower()}"
                webhook_payload = {
                    "user_id": payload.user_id,
                    "score": score,
                    "decision": decision.value,
                    "explanation": explanation,
                    "ip": payload.ip,
                    "country": metadata.get("country"),
                    "risk_factors": [
                        {"factor": f.factor, "contribution": f.contribution}
                        for f in risk_factors
                    ]
                }
                await WebhookService.fire_and_forget(
                    webhook_url, tenant_id, event_type, webhook_payload
                )

        # === Build response ===
        return EvaluateResponse(
            decision=decision,
            score=score,
            explanation=explanation,
            risk_factors=risk_factors,
            dna_match=dna_match,
            is_new_user=is_new_user,
            processing_time_ms=processing_time_ms,
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        print(f"❌ Evaluation error for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "evaluation_failed",
                "message": str(e),
                "request_id": request_id
            }
        )