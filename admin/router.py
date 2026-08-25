from aiogram import Router

# Підключаємо всі адмін-модулі
from .base import router as base_router
from .winrate import router as winrate_router
from .users import router as users_router
from .broadcast import router as broadcast_router
from .menu_update import router as menu_update_router
from .promocodes import router as promocodes_router
from .casino_codes import router as casino_codes_router
from .bans import router as bans_router
from .cards import router as cards_router
from .weekly_tasks import router as weekly_tasks_router
from .notifications import router as notifications_router
from .safe import router as safe_router
from .checks import router as admin_checks_router
from .payment_history import router as payment_history_router
from .losses import router as losses_router
from .piggy_bank import router as piggy_bank_router
from .top_players import router as top_players_router

router = Router(name="admin")

# Підключаємо всі підроутери
router.include_router(admin_checks_router) 
router.include_router(payment_history_router)
router.include_router(losses_router)
router.include_router(piggy_bank_router)
router.include_router(top_players_router)
router.include_router(base_router)
router.include_router(winrate_router)
router.include_router(users_router)
router.include_router(broadcast_router)
router.include_router(menu_update_router)
router.include_router(promocodes_router)
router.include_router(casino_codes_router)
router.include_router(bans_router)
router.include_router(cards_router)
router.include_router(weekly_tasks_router)
router.include_router(notifications_router)
router.include_router(safe_router)
 # Підключаємо роутер для чеків
__all__ = ["router"]
