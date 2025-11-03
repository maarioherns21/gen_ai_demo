from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid

# ENUM: Defines possible categories for trip-related line items
class LineItemType(str, Enum):
    """Enumeration of supported travel service types within a trip."""
    FLIGHT = "flight"
    HOTEL = "hotel"
    RAIL = "rail"
    ACTIVITY = "activity"
    TRANSFER = "transfer"

# CLASS: LineItem
@dataclass
class LineItem:
    """
    Represents a single booked or planned travel service (e.g., flight, hotel, tour).
    Each line item belongs to a specific trip.
    """
    id: str
    trip_id: str
    type: LineItemType
    vendor: Optional[str] = None          # Provider name (e.g., Delta, Booking.com)
    ref: Optional[str] = None             # Booking reference or confirmation number
    start_ts: Optional[datetime] = None   # Start datetime (e.g., flight departure)
    end_ts: Optional[datetime] = None     # End datetime (e.g., flight arrival)
    price_usd: Decimal = Decimal("0.00")  # Price in USD
    currency: str = "USD"                 # ISO 4217 currency code
    refundable: bool = False              # Whether the booking can be refunded
    terms: Dict[str, Any] = field(default_factory=dict)  # Cancellation/booking terms
    meta: Dict[str, Any] = field(default_factory=dict)   # Additional metadata (seat, class, etc.)

    def __post_init__(self):
        """Validation and auto-generation of IDs after initialization."""
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.trip_id:
            raise ValueError("LineItem.trip_id is required")
        if self.price_usd < 0:
            raise ValueError("price_usd cannot be negative")
        if self.currency and len(self.currency) not in (3,):
            raise ValueError("currency must be a 3-letter code (e.g., 'USD')")
        if self.start_ts and self.end_ts and self.end_ts < self.start_ts:
            raise ValueError("end_ts cannot be earlier than start_ts")

# CLASS: ItineraryDay
@dataclass
class ItineraryDay:
    """
    Represents a single day of a trip itinerary.
    Used to organize activities, locations, and notes per day.
    """
    id: str
    trip_id: str
    day_index: int                       # Sequential day number (1-based)
    city: Optional[str] = None           # City or main location for the day
    notes: Optional[str] = None          # Optional text notes or highlights

    def __post_init__(self):
        """Validation and ID assignment after object creation."""
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.day_index < 1:
            raise ValueError("day_index must be >= 1")
        if not self.trip_id:
            raise ValueError("ItineraryDay.trip_id is required")

# CLASS: Trip
@dataclass
class Trip:
    """
    Represents a complete trip plan with metadata, itinerary days, and booked line items.
    Core object used by the vacation planner system.
    """
    id: str
    user_id: str
    title: Optional[str]                 # Custom title (e.g., “Summer in Italy”)
    origin: str                          # Starting location (IATA code or city)
    destination: str                     # Main destination (IATA code or city)
    start_date: date                     # Trip start date
    end_date: date                       # Trip end date
    budget_usd: Decimal                  # Budget constraint in USD
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    days: List[ItineraryDay] = field(default_factory=list)  # List of daily itineraries
    line_items: List[LineItem] = field(default_factory=list) # List of services booked

    def __post_init__(self):
        """Validates date consistency and assigns UUID if missing."""
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.user_id:
            raise ValueError("Trip.user_id is required")
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        if self.budget_usd <= 0:
            raise ValueError("budget_usd must be positive")
   
    # Derived properties
    @property
    def duration_days(self) -> int:
        """Calculates total number of days (inclusive)."""
        return (self.end_date - self.start_date).days + 1

    @property
    def total_cost_usd(self) -> Decimal:
        """Aggregates all line item prices for total trip cost."""
        return sum((li.price_usd for li in self.line_items), Decimal("0.00"))
    
    # Mutation helpers
    def add_day(self, city: Optional[str] = None, notes: Optional[str] = None) -> ItineraryDay:
        """Adds a new day to the itinerary with optional city and notes."""
        day = ItineraryDay(
            id=str(uuid.uuid4()),
            trip_id=self.id,
            day_index=len(self.days) + 1,
            city=city,
            notes=notes,
        )
        self.days.append(day)
        self.updated_at = datetime.utcnow()
        return day

    def add_line_item(self, item: LineItem) -> None:
        """Attaches a new line item (e.g., flight, hotel) to this trip."""
        if item.trip_id != self.id:
            raise ValueError("LineItem.trip_id does not match Trip.id")
        self.line_items.append(item)
        self.updated_at = datetime.utcnow()
    # Serialization helper
    def to_dict(self) -> Dict[str, Any]:
        """Converts dataclass to dict, serializing complex types to strings."""
        def _normalize(v):
            if isinstance(v, datetime):
                return v.isoformat()
            if isinstance(v, date):
                return v.isoformat()
            if isinstance(v, Decimal):
                return str(v)
            return v
        d = asdict(self)
        # Normalize nested values for JSON compatibility
        for k, v in list(d.items()):
            if isinstance(v, list):
                d[k] = [{kk: _normalize(vv) for kk, vv in item.items()} for item in v]  # type: ignore
            else:
                d[k] = _normalize(v)
        return d
    






# def create_sample_trip() -> Trip:
#     """sample Trip object with realistic data for testing."""

#     # Step 1. Define the trip
#     trip = Trip(
#         id="trip-001",
#         user_id="user-123",
#         title="Italy Summer Adventure",
#         origin="MEX",
#         destination="ITA",
#         start_date=date(2025, 6, 1),
#         end_date=date(2025, 6, 7),
#         budget_usd=Decimal("2500.00"),
#     )

#     # Step 2. Add daily itinerary entries
#     trip.add_day(city="Rome", notes="Arrive and explore the Colosseum.")
#     trip.add_day(city="Florence", notes="Visit Uffizi Gallery and Ponte Vecchio.")
#     trip.add_day(city="Venice", notes="Take a gondola ride and enjoy seafood dinner.")

#     # Step 3. Add line items (flight, hotel, tour)
#     flight = LineItem(
#         id="li-001",
#         trip_id=trip.id,
#         type=LineItemType.FLIGHT,
#         vendor="ITA Airways",
#         ref="ITA9876",
#         start_ts=datetime(2025, 6, 1, 8, 30),
#         end_ts=datetime(2025, 6, 1, 14, 50),
#         price_usd=Decimal("780.00"),
#         refundable=True,
#         terms={"cancellation": "Full refund before May 15"},
#         meta={"seat_class": "Economy", "baggage": "1 checked bag"},
#     )

#     hotel = LineItem(
#         id="li-002",
#         trip_id=trip.id,
#         type=LineItemType.HOTEL,
#         vendor="Hotel Borghiciana",
#         ref="BOOK12345",
#         start_ts=datetime(2025, 6, 1, 15, 0),
#         end_ts=datetime(2025, 6, 7, 11, 0),
#         price_usd=Decimal("840.00"),
#         refundable=True,
#         terms={"cancellation": "Free until May 28"},
#         meta={"room_type": "Deluxe Double", "breakfast": True},
#     )

#     tour = LineItem(
#         id="li-003",
#         trip_id=trip.id,
#         type=LineItemType.ACTIVITY,
#         vendor="Viator",
#         ref="VTR-RM-T123",
#         start_ts=datetime(2025, 6, 2, 9, 0),
#         end_ts=datetime(2025, 6, 2, 12, 0),
#         price_usd=Decimal("120.00"),
#         refundable=False,
#         meta={"activity": "Colosseum guided tour"},
#     )

#     # Add them to the trip
#     trip.add_line_item(flight)
#     trip.add_line_item(hotel)
#     trip.add_line_item(tour)
    
#     return trip

#     # Create and print trip details
# trip = create_sample_trip()
# print("Trip Duration (days):", trip.duration_days)
# print("Total Cost (USD):", trip.total_cost_usd)

#     # Serialize to dictionary and JSON
# trip_dict = trip.to_dict()
# print("\nSerialized Trip Dict:\n", trip_dict)

# trip_json = json.dumps(trip_dict, indent=4)
# print("\nSerialized Trip JSON:\n", trip_json)