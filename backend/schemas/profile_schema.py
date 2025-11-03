from __future__ import annotations
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any

class RiskTolerance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class LoyaltyProgram:
    program: str                  # e.g., "Delta SkyMiles", "Marriott Bonvoy"
    id_or_number: Optional[str] = None
    status: Optional[str] = None  # e.g., "Gold", "Platinum"


@dataclass
class AccessibilityPrefs:
    mobility_assistance: bool = False
    step_free_access: bool = False
    elevator_required: bool = False
    quiet_room_preferred: bool = False
    notes: Optional[str] = None


@dataclass
class PetPolicy:
    traveling_with_pet: bool = False
    pet_type: Optional[str] = None      # e.g., "dog", "cat"
    in_cabin_only: bool = True
    max_pet_weight_kg: Optional[float] = None
    crate_dimensions_cm: Optional[str] = None  # "LxWxH"


@dataclass
class PreferenceProfile:
    user_id: str
    home_airport: Optional[str] = None           # IATA code (e.g., "MEX", "SFO")
    preferred_airlines: List[str] = field(default_factory=list)
    preferred_hotel_brands: List[str] = field(default_factory=list)
    dietary: List[str] = field(default_factory=list)  # e.g., ["vegetarian","halal","gluten-free"]
    budget_band_usd: Optional[Decimal] = None
    cabin_preference: Optional[str] = None       # "ECONOMY" | "PREMIUM" | "BUSINESS"
    seat_preference: Optional[str] = None        # "AISLE" | "WINDOW" | "MIDDLE"
    room_config: Optional[str] = None            # "1Q", "2D", "1K", etc.
    languages: List[str] = field(default_factory=list)
    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM
    loyalty: List[LoyaltyProgram] = field(default_factory=list)
    accessibility: AccessibilityPrefs = field(default_factory=AccessibilityPrefs)
    pet: PetPolicy = field(default_factory=PetPolicy)
    notes: Optional[str] = None
    consent_scopes: Dict[str, bool] = field(default_factory=dict)  # e.g., {"calendar_write": True}

    def __post_init__(self):
        if not self.user_id:
            raise ValueError("PreferenceProfile.user_id is required")
        if self.home_airport and len(self.home_airport) != 3:
            raise ValueError("home_airport must be a 3-letter IATA code")
        if self.cabin_preference and self.cabin_preference not in {"ECONOMY", "PREMIUM", "BUSINESS"}:
            raise ValueError("cabin_preference must be ECONOMY|PREMIUM|BUSINESS")
        if self.seat_preference and self.seat_preference not in {"AISLE", "WINDOW", "MIDDLE"}:
            raise ValueError("seat_preference must be AISLE|WINDOW|MIDDLE")
        if self.budget_band_usd is not None and self.budget_band_usd <= 0:
            raise ValueError("budget_band_usd must be positive when provided")

    def to_dict(self) -> Dict[str, Any]:
        def _convert(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            if hasattr(obj, "__dict__") or isinstance(obj, (list, dict)):
                # dataclasses.asdict handles nested dataclasses
                return obj
            return obj
        d = asdict(self)
        return d







# def create_sample_profile() -> PreferenceProfile:
#     """Sample PreferenceProfile object for testing."""

#     # Step 1. Create nested objects
#     loyalty_air = LoyaltyProgram(
#         program="Delta SkyMiles",
#         id_or_number="DL12345678",
#         status="Gold"
#     )

#     loyalty_hotel = LoyaltyProgram(
#         program="Marriott Bonvoy",
#         id_or_number="MB998877",
#         status="Platinum"
#     )

#     accessibility = AccessibilityPrefs(
#         mobility_assistance=False,
#         step_free_access=True,
#         elevator_required=True,
#         quiet_room_preferred=True,
#         notes="Prefers quiet rooms near elevators but not facing the street."
#     )

#     pet_policy = PetPolicy(
#         traveling_with_pet=True,
#         pet_type="dog",
#         in_cabin_only=True,
#         max_pet_weight_kg=7.5,
#         crate_dimensions_cm="45x30x25"
#     )

#     # Step 2. Create the preference profile
#     profile = PreferenceProfile(
#         user_id="user-123",
#         home_airport="SFO",
#         preferred_airlines=["Delta", "Lufthansa"],
#         preferred_hotel_brands=["Marriott", "Hilton"],
#         dietary=["vegetarian", "no seafood"],
#         budget_band_usd=Decimal("3000.00"),
#         cabin_preference="PREMIUM",
#         seat_preference="AISLE",
#         room_config="1K",
#         languages=["English", "Spanish", "Italian"],
#         risk_tolerance=RiskTolerance.LOW,
#         loyalty=[loyalty_air, loyalty_hotel],
#         accessibility=accessibility,
#         pet=pet_policy,
#         notes="Enjoys art museums and hiking trips. Prefers moderate travel pace.",
#         consent_scopes={"calendar_write": True, "email_notifications": True},
#     )

#     return profile


# # Create and print the test object
# profile = create_sample_profile()

# print("Created PreferenceProfile object:")
# print(profile)

# # Serialize to dict and JSON for inspection
# profile_dict = profile.to_dict()
# print("\nSerialized Dict:")
# print(profile_dict)

# profile_json = json.dumps(profile_dict, indent=4, default=str)
# print("\nSerialized JSON:")
# print(profile_json)