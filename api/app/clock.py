from datetime import date, datetime
from zoneinfo import ZoneInfo

# The agency is in Arizona (no daylight saving). "Today" means the agency's today, not the server's:
# a deployed server runs on UTC, which is already tomorrow by 5 pm in Phoenix.
AGENCY_TZ = ZoneInfo("America/Phoenix")


def agency_today() -> date:
    return datetime.now(AGENCY_TZ).date()
