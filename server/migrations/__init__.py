"""Central PostgreSQL schema migrations for LUMS."""

from .core_schema import CORE_SCHEMA_MIGRATION
from .security_schema import SECURITY_SCHEMA_MIGRATION
from .rbac_schema import RBAC_SCHEMA_MIGRATION
from .rbac_seed import RBAC_SEED_MIGRATION
from .infrastructure_topology import INFRASTRUCTURE_TOPOLOGY_MIGRATION
from .telemetry import TELEMETRY_MIGRATION
from .package_search import PACKAGE_SEARCH_MIGRATION
from .alerts import ALERTS_MIGRATION


MIGRATIONS = (
    CORE_SCHEMA_MIGRATION,
    SECURITY_SCHEMA_MIGRATION,
    RBAC_SCHEMA_MIGRATION,
    RBAC_SEED_MIGRATION,
    INFRASTRUCTURE_TOPOLOGY_MIGRATION,
    TELEMETRY_MIGRATION,
    PACKAGE_SEARCH_MIGRATION,
    ALERTS_MIGRATION,
)

__all__ = ["MIGRATIONS"]
