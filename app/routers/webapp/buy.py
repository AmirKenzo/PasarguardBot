"""New-purchase flow: thin delegation to WebAppPurchaseService."""

from fastapi import APIRouter

from app.models.webapp import (
    WebAppBuyConfirmRequest,
    WebAppBuyConfirmResponse,
    WebAppBuyOptionsRequest,
    WebAppBuyOptionsResponse,
    WebAppBuyPlansRequest,
    WebAppBuyPlansResponse,
    WebAppBuyPreviewRequest,
    WebAppBuyPreviewResponse,
    WebAppBuyUsernameRequest,
    WebAppBuyUsernameResponse,
)
from app.routers.webapp.auth import authenticate_user
from app.services.webapp_purchase import WebAppPurchaseService

router = APIRouter()


@router.post("/webapp/buy/options", response_model=WebAppBuyOptionsResponse)
async def get_buy_options(request: WebAppBuyOptionsRequest) -> WebAppBuyOptionsResponse:
    """Get buyable VPN panels and high-level buy flow options."""
    try:
        await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payload = await WebAppPurchaseService().get_buy_options()
        return WebAppBuyOptionsResponse(**payload)
    except ValueError as e:
        return WebAppBuyOptionsResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppBuyOptionsResponse(ok=False, error=str(e))


@router.post("/webapp/buy/plans", response_model=WebAppBuyPlansResponse)
async def get_buy_plans(request: WebAppBuyPlansRequest) -> WebAppBuyPlansResponse:
    """Get available plans for a selected panel, respecting duration-first panels."""
    try:
        await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payload = await WebAppPurchaseService().get_panel_plans(
            panel_code=request.panel_code,
            duration=request.duration,
        )
        return WebAppBuyPlansResponse(**payload)
    except ValueError as e:
        return WebAppBuyPlansResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppBuyPlansResponse(ok=False, error=str(e))


@router.post("/webapp/buy/username", response_model=WebAppBuyUsernameResponse)
async def generate_buy_username(request: WebAppBuyUsernameRequest) -> WebAppBuyUsernameResponse:
    """Generate an available-ish config username for the selected panel."""
    try:
        await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payload = await WebAppPurchaseService().generate_username(request.panel_code)
        return WebAppBuyUsernameResponse(**payload)
    except ValueError as e:
        return WebAppBuyUsernameResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppBuyUsernameResponse(ok=False, error=str(e))


@router.post("/webapp/buy/preview", response_model=WebAppBuyPreviewResponse)
async def preview_buy(request: WebAppBuyPreviewRequest) -> WebAppBuyPreviewResponse:
    """Validate a WebApp VPN purchase and return final price before confirmation."""
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payload = await WebAppPurchaseService().preview_purchase(
            user_id=user_id,
            panel_code=request.panel_code,
            plan_id=request.plan_id,
            username=request.username,
            discount_code=request.discount_code,
        )
        return WebAppBuyPreviewResponse(**payload)
    except ValueError as e:
        return WebAppBuyPreviewResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppBuyPreviewResponse(ok=False, error=str(e))


@router.post("/webapp/buy/confirm", response_model=WebAppBuyConfirmResponse)
async def confirm_buy(request: WebAppBuyConfirmRequest) -> WebAppBuyConfirmResponse:
    """Confirm a WebApp VPN purchase and create the config on the selected panel."""
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payload = await WebAppPurchaseService().confirm_purchase(
            user_id=user_id,
            panel_code=request.panel_code,
            plan_id=request.plan_id,
            username=request.username,
            discount_code=request.discount_code,
        )
        return WebAppBuyConfirmResponse(**payload)
    except ValueError as e:
        return WebAppBuyConfirmResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppBuyConfirmResponse(ok=False, error=str(e))
