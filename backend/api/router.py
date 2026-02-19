from fastapi import APIRouter

from backend.api.v1 import auth, dashboard, overview, history, analysis, cases, report, notification, admin

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(overview.router)
api_router.include_router(history.router)
api_router.include_router(analysis.router)
api_router.include_router(cases.router)
api_router.include_router(report.router)
api_router.include_router(notification.router)
api_router.include_router(admin.router)
