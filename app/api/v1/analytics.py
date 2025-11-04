"""
Analytics endpoints
"""

from typing import Annotated
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_analytics_service
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/user/{user_address}")
async def get_user_analytics(
    user_address: str,
    days: int = 7,
    analytics: Annotated[AnalyticsService, Depends(get_analytics_service)] = None,
):
    """Get user analytics"""
    try:
        stats = await analytics.get_user_stats(
            user_address, start_date=datetime.now() - timedelta(days=days)
        )
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_id}")
async def get_agent_analytics(
    agent_id: str,
    days: int = 7,
    analytics: Annotated[AnalyticsService, Depends(get_analytics_service)] = None,
):
    """Get agent analytics"""
    try:
        stats = await analytics.get_agent_stats(
            agent_id, start_date=datetime.now() - timedelta(days=days)
        )
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/global")
async def get_global_analytics(
    days: int = 7, analytics: Annotated[AnalyticsService, Depends(get_analytics_service)] = None
):
    """Get global analytics""" """Get global platform analytics"""
    try:
        stats = await analytics.get_global_stats(start_date=datetime.now() - timedelta(days=days))
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
