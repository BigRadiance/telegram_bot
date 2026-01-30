from aiogram import Router
from .start import router as start_router
from .mini_tour import router as mini_tour_router

routers = Router()
routers.include_router(start_router)
routers.include_router(mini_tour_router)
