# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# ===========================================================================
"""business_value — ROI and financial impact quantification for NAWEX consulting.

Provides tools to translate AI risk scores into dollar-denominated business
impact estimates suitable for C-suite and board-level consulting conversations.
"""

from .roi_calculator import ROICalculator
from .impact_estimator import ImpactEstimator

__all__ = ["ROICalculator", "ImpactEstimator"]
