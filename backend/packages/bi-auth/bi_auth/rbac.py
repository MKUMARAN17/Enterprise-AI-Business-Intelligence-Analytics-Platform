"""Role-Based Access Control: which UPPERCASE tables each role may read.

This is the second half of the platform's data-access security (the first being
the SQL guard's DDL/DML block). The policy is intentionally *table-level* and
*allow-list* based: a role can only touch tables explicitly granted to it, so a
prompt-injected or hallucinated query that references FINANCE tables under a
SALES token is rejected before execution — the guard is handed
``policy.allowed_tables(role)`` and enforces membership.

Platform-owned tables (USERS/ROLES/AUDIT_LOG) are never queryable through the
NL→SQL path by anyone except ADMIN; business users analyse business data only.
"""
from __future__ import annotations

from bi_auth.models import Role

# Every business (queryable) table in the ENTERPRISE_BI schema, UPPERCASE.
_ALL_BUSINESS_TABLES: frozenset[str] = frozenset(
    {
        "REGIONS",
        "BRANCHES",
        "PRODUCTS",
        "CUSTOMERS",
        "CUSTOMER_ACCOUNTS",
        "EMPLOYEES",
        "EMPLOYEE_PERFORMANCE",
        "COLLECTIONS",
        "REVENUE",
        "SALES",
        "CLAIMS",
        "PAYMENTS",
        "INVENTORY",
        "PROCUREMENT",
    }
)

_PLATFORM_TABLES: frozenset[str] = frozenset({"USERS", "ROLES", "AUDIT_LOG"})

# Role → grants. ADMIN gets everything (incl. platform tables). Others get a
# curated business subset that matches the role's job.
_GRANTS: dict[Role, frozenset[str]] = {
    Role.ADMIN: _ALL_BUSINESS_TABLES | _PLATFORM_TABLES,
    Role.BUSINESS_ANALYST: _ALL_BUSINESS_TABLES,
    Role.MANAGER: _ALL_BUSINESS_TABLES,
    Role.FINANCE: frozenset(
        {
            "REGIONS",
            "BRANCHES",
            "CUSTOMERS",
            "CUSTOMER_ACCOUNTS",
            "COLLECTIONS",
            "REVENUE",
            "CLAIMS",
            "PAYMENTS",
        }
    ),
    Role.SALES: frozenset(
        {
            "REGIONS",
            "BRANCHES",
            "PRODUCTS",
            "CUSTOMERS",
            "EMPLOYEES",
            "EMPLOYEE_PERFORMANCE",
            "COLLECTIONS",
            "SALES",
            "INVENTORY",
        }
    ),
}


class RbacPolicy:
    """Resolves a role to its allow-list of UPPERCASE table names."""

    def allowed_tables(self, role: Role) -> set[str]:
        return set(_GRANTS.get(role, frozenset()))

    def can_read(self, role: Role, table: str) -> bool:
        return table.upper() in _GRANTS.get(role, frozenset())

    @property
    def all_business_tables(self) -> set[str]:
        return set(_ALL_BUSINESS_TABLES)
