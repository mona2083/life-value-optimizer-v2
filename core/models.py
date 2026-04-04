"""
Domain models for life planning optimization application.
These are the core data structures that flow through the entire app.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class UserProfile:
    """User demographic and household information"""
    age: int
    family_status: str  # e.g., "single", "couple", "family_with_kids"
    household_adults: int = 1
    household_children: int = 0
    household_infants: int = 0
    debt_repayment: float = 0.0
    passion_text: str = ""  # User's freeform passion/interests


@dataclass
class FoodData:
    """Food preferences and consumption patterns"""
    home_meal_style: str = "standard"  # minimalist, standard, health_conscious, time_saving
    dining_out_frequency: str = "0_1"  # 0_1, 2_3, 4_plus
    dining_out_tone: str = "utility"  # utility, casual, experience
    optional_alcohol: bool = False
    optional_supplements: bool = False
    optional_special_diet: bool = False


@dataclass
class LifestyleData:
    """User's lifestyle information"""
    # From surveys
    health_level: int = 5
    connections_level: int = 5
    freedom_level: int = 5
    growth_level: int = 5
    
    # Food data embedded
    food: FoodData = field(default_factory=FoodData)


@dataclass
class FoodEstimate:
    """Food cost estimation - THE SINGLE SOURCE OF TRUTH for food data"""
    monthly_food_cost: float  # Survey-level cost
    minimalist_floor_cost: float  # Absolute minimum
    max_possible_food_cost: float  # Theoretical maximum
    food_stage1_band_max: float  # Flexible spending range 1
    food_stage2_band_max: float  # Flexible spending range 2
    
    # Metadata
    location_adjustment: float = 1.0
    scale_adjustment: float = 1.0
    style_name: str = "Standard"
    style_coeff: float = 1.0
    qol_add: float = 0.0
    adult_equivalent: float = 1.0
    headcount_total: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for Streamlit session state"""
        return {
            "monthly_food_cost": self.monthly_food_cost,
            "minimalist_floor_cost": self.minimalist_floor_cost,
            "max_possible_food_cost": self.max_possible_food_cost,
            "food_stage1_band_max": self.food_stage1_band_max,
            "food_stage2_band_max": self.food_stage2_band_max,
            "location_adjustment": self.location_adjustment,
            "scale_adjustment": self.scale_adjustment,
            "style_name": self.style_name,
            "style_coeff": self.style_coeff,
            "qol_add": self.qol_add,
            "adult_equivalent": self.adult_equivalent,
            "headcount_total": self.headcount_total,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FoodEstimate":
        """Create from dict"""
        return cls(
            monthly_food_cost=data.get("monthly_food_cost", 0),
            minimalist_floor_cost=data.get("minimalist_floor_cost", 0),
            max_possible_food_cost=data.get("max_possible_food_cost", 0),
            food_stage1_band_max=data.get("food_stage1_band_max", 0),
            food_stage2_band_max=data.get("food_stage2_band_max", 0),
            location_adjustment=data.get("location_adjustment", 1.0),
            scale_adjustment=data.get("scale_adjustment", 1.0),
            style_name=data.get("style_name", "Standard"),
            style_coeff=data.get("style_coeff", 1.0),
            qol_add=data.get("qol_add", 0),
            adult_equivalent=data.get("adult_equivalent", 1.0),
            headcount_total=data.get("headcount_total", 1),
        )


@dataclass
class FinancialData:
    """Complete financial situation"""
    initial_budget: int  # Upfront money available
    monthly_budget: int  # Monthly cash flow available
    target_monthly_savings: int  # Monthly savings goal
    savings_period_years: int = 1
    risk_monthly_total: float = 0.0
    
    # Derived/nested
    food_estimate: Optional[FoodEstimate] = None
    user_profile: Optional[UserProfile] = None


@dataclass
class OptimizationResult:
    """Result from running the optimizer"""
    status: str  # "ok", "no_solution", "best_effort"
    selected: List[Dict[str, Any]] = field(default_factory=list)  # Selected items
    total_initial_cost: float = 0.0
    total_monthly_cost: float = 0.0
    food_stage1_monthly_cost: float = 0.0
    food_stage2_monthly_cost: float = 0.0
    actual_monthly_savings: float = 0.0
    target_monthly_savings: float = 0.0
    savings_rate: float = 0.0
    total_value: float = 0.0
    
    # Best effort flags
    best_effort_mandatory_relaxed: bool = False
    best_effort_zero_food_stages: bool = False
    best_effort_transport_optional: bool = False
