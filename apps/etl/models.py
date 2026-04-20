"""Re-export the legacy-id-map model so Django discovers it under this app."""
from common.etl.legacy_id_map import (  # noqa: F401
    LegacyIdMap,
    lookup,
    remember,
    require,
)
