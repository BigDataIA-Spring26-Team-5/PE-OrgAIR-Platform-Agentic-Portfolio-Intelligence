"""Re-export canonical dimension types from app.models.enumerations."""

# CS3/RAG code uses short aliases ('talent', 'leadership', 'culture') — see DIMENSION_ALIAS_MAP.
# The canonical enum values TALENT_SKILLS, LEADERSHIP_VISION, CULTURE_CHANGE match the
# Snowflake schema and are used throughout the codebase. The plan's shorter names
# (TALENT, LEADERSHIP, CULTURE) were simplifications — no rename needed.
from app.models.enumerations import Dimension, DIMENSION_ALIAS_MAP, VALID_DIMENSIONS

__all__ = ["Dimension", "DIMENSION_ALIAS_MAP", "VALID_DIMENSIONS"]
