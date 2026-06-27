# db/__init__.py
# ФІНАЛЬНА ВЕРСІЯ — включає add_or_update_user для handlers/profile.py

from .core import (
    init_db,
    DB_PATH,
    ensure_users_table_and_columns,
    create_pending_payments_table,
    create_used_monobank_txs_table,
)

# ==================== WALLET ====================
from .wallet import (
    add_to_balance,
    get_balance,
    add_pending_payment,
    get_pending_payments,
    remove_pending_payment,
    mark_tx_used,
    is_tx_used,
    add_payment_log,
    get_payment_logs,
    cleanup_old_payment_logs,
    get_payment_logs_by_date,
    log_check_issued,
    get_issued_checks_for_user,
    get_all_balances,
    mark_tx_used, 
    get_active_champion_checks,
    delete_issued_check,
    # get_project_net,
    # get_personal_net,
    get_daily_net,
    get_yesterday_net,
    update_daily_net,
    get_all_daily_game_wins,
    get_daily_game_win, 
    add_daily_game_win, 
    can_receive_prize,
    get_yesterday_game_win,
    get_cashback_claimed_base,
    get_cashback_status, 
    claim_cashback,
    claim_promo,
    get_promo_status,
    get_promo_claimed_base,
    _generate_promo_code,
)

# ==================== USERS ====================
from .users import (
    save_user,
    has_claimed_gift,
    set_gift_claimed,
    reset_all_gifts,
    get_total_money_won,
    add_game_win,
    add_money_win,
    increment_games_played,
    get_user_data,
    add_last_action,
    get_user_access,
    set_user_access,
    get_all_users,
    get_all_users_info,
    add_or_update_user, 
    search_users,          
)

# ==================== PROMO ====================
from .promo import (
    add_promocode,
    list_promocodes,
    check_promocode,
    clear_promocodes,
)

# ==================== SAFE ====================
from .safe import get_safe_state, save_safe_state

# ==================== GAMES ====================
from .games import (
    get_all_stats,
    add_game_result,
    reset_all_game_stats,
    add_slot_session,
    get_slot_session_stats,
    add_blackjack_session,
    get_blackjack_session_stats,
    clear_game_stats,
    add_casino_code,
    get_free_code,
    mark_code_used_by_id,
    mark_code_unused,
    create_pending_reward,
    set_pending_status,
    get_pending_by_id,
    get_winrate,
    set_winrate,
    spend_promo_for_fortune,
    add_promo,
    get_promo,
)

# ==================== ADMIN ====================
from .admin import (
    ban_user,
    unban_user,
    get_all_banned,
    get_cards,
    update_card,
    save_notification,
    get_notifications,
    add_weekly_task,
    get_active_tasks,
    get_user_task_progress,
    ensure_ban_table,
)



# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


from .check import (
    add_check_code,
    delete_check_code,
    get_checks_stats,
    clear_all_checks,
    get_checks_count,
    get_free_check,
    remove_check,
)

from .referral import (
    create_referral_tables,
    add_referral,
    get_referrals,
    is_referred,
    mark_referral_paid,
    user_exists, 
    get_all_referrals,
)

__all__ = [name for name in globals() if not name.startswith("_")]