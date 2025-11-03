from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

class ToolName(str, Enum):
    FLIGHT_SEARCH = "flight_search"
    HOTEL_SEARCH = "hotel_search"
    EVENTS_SEARCH = "events_search"
    WEATHER_LOOKUP = "weather_lookup"
    VISA_CHECK = "visa_check"
    FOREX_RATE = "forex_rate"
    SAFETY_ADVISORY = "safety_advisory"
    CALENDAR_WRITE = "calendar_write"
    BOOKING_CART = "booking_cart"


# ---- Generic tool call/result shells ----------------------------------------

@dataclass
class ToolCall:
    name: ToolName
    input: Dict[str, Any]
    correlation_id: Optional[str] = None         # for tracing
    max_latency_ms: Optional[int] = 8000
    retry_count: int = 0

    def __post_init__(self):
        if not isinstance(self.name, ToolName):
            raise ValueError("ToolCall.name must be a ToolName enum")


@dataclass
class ToolError:
    code: str
    message: str
    retriable: bool = False
    raw: Optional[Dict[str, Any]] = None


@dataclass
class ToolResult:
    name: ToolName
    ok: bool
    output: Optional[Dict[str, Any]] = None
    error: Optional[ToolError] = None
    correlation_id: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.name, ToolName):
            raise ValueError("ToolResult.name must be a ToolName enum")
        if self.ok and self.error is not None:
            raise ValueError("ToolResult cannot be ok=True and have an error")
        if (not self.ok) and self.error is None:
            raise ValueError("ToolResult with ok=False must include error")


# ---- Example: Flight Search typed input/output ------------------------------

class CabinClass(str, Enum):
    ECONOMY = "ECONOMY"
    PREMIUM = "PREMIUM"
    BUSINESS = "BUSINESS"


@dataclass
class FlightSegment:
    carrier: str
    flight_number: str
    origin: str  # IATA
    destination: str  # IATA
    depart_iso: str   # ISO8601 datetime
    arrive_iso: str   # ISO8601 datetime
    duration_minutes: int
    cabin: CabinClass
    stops: int = 0
    baggage_note: Optional[str] = None


@dataclass
class FlightItinerary:
    price_total_usd: float
    refundable: bool
    segments: List[FlightSegment]
    fare_basis: Optional[str] = None
    booking_class: Optional[str] = None
    currency: str = "USD"

    def __post_init__(self):
        if self.price_total_usd < 0:
            raise ValueError("price_total_usd cannot be negative")
        if not self.segments:
            raise ValueError("segments cannot be empty")
        if self.currency and len(self.currency) != 3:
            raise ValueError("currency must be a 3-letter code")


@dataclass
class FlightSearchInput:
    origin: str
    destination: str
    depart_date: date
    return_date: Optional[date] = None
    adults: int = 1
    cabin: CabinClass = CabinClass.ECONOMY
    max_stops: Optional[int] = None
    pet_in_cabin: Optional[bool] = None

    def __post_init__(self):
        if len(self.origin) != 3 or len(self.destination) != 3:
            raise ValueError("origin/destination must be 3-letter IATA codes")
        if self.adults < 1:
            raise ValueError("adults must be >= 1")
        if self.return_date and self.return_date < self.depart_date:
            raise ValueError("return_date cannot be earlier than depart_date")


@dataclass
class FlightSearchOutput:
    itineraries: List[FlightItinerary]
    source: Optional[str] = None       # which API (e.g., "Amadeus")
    currency: str = "USD"

    def __post_init__(self):
        if not self.itineraries:
            raise ValueError("itineraries cannot be empty")



# def to_dict_dataclass(instance) -> Dict[str, Any]:
#     """
#     Safe shallow-to-deep conversion for these tool schemas.
#     Enum values are rendered as their .value; other nested dataclasses are handled by asdict.
#     """
#     def _enum_to_val(x):
#         return x.value if hasattr(x, "value") and isinstance(x, Enum) else x

#     raw = asdict(instance)
#     # Walk and convert any Enum leaves (asdict keeps Enums as Enums)
#     def _walk(v):
#         if isinstance(v, dict):
#             return {k: _walk(_enum_to_val(val)) for k, val in v.items()}
#         if isinstance(v, list):
#             return [_walk(_enum_to_val(i)) for i in v]
#         return _enum_to_val(v)
#     return _walk(raw)  # type: ignore




# def create_flight_search_result():
#     """Create a minimal, successful flight search ToolResult for testing."""

#     # 1 Define the initial tool call
#     call = ToolCall(
#         name=ToolName.FLIGHT_SEARCH,
#         input={"origin": "MEX", "destination": "FCO", "adults": 1},
#         correlation_id="corr-001"
#     )

#     # 2️ Define the structured input (typed)
#     finput = FlightSearchInput(
#         origin="MEX",
#         destination="FCO",
#         depart_date=date(2025, 6, 1),
#         return_date=date(2025, 6, 7),
#         adults=1,
#         cabin=CabinClass.ECONOMY,
#         max_stops=1,
#         pet_in_cabin=True,
#     )

#     # 3️ Create a flight segment (e.g., MEX → FCO direct)
#     seg = FlightSegment(
#         carrier="ITA Airways",
#         flight_number="AZ673",
#         origin="MEX",
#         destination="FCO",
#         depart_iso="2025-06-01T08:30:00-06:00",
#         arrive_iso="2025-06-01T23:10:00+02:00",
#         duration_minutes=640,
#         cabin=CabinClass.ECONOMY,
#         stops=0,
#         baggage_note="1 checked bag included"
#     )

#     # 4️ Build the itinerary
#     itinerary = FlightItinerary(
#         price_total_usd=785.50,
#         refundable=True,
#         segments=[seg],
#         fare_basis="Y-REF",
#         booking_class="Y",
#         currency="USD",
#     )

#     # 5️ Wrap it into an output structure
#     foutput = FlightSearchOutput(
#         itineraries=[itinerary],
#         source="MockProvider",
#         currency="USD"
#     )

#     # 6️ Create the ToolResult (successful)
#     result = ToolResult(
#         name=ToolName.FLIGHT_SEARCH,
#         ok=True,
#         output={
#             "input": to_dict_dataclass(finput),
#             "result": to_dict_dataclass(foutput),
#         },
#         correlation_id=call.correlation_id,
#     )

#     return call, result



#  # Run the happy-path test
# call, result = create_flight_search_result()

# print("TOOL CALL OBJECT:")
# print(call)

# print("\nTOOL RESULT JSON:")
# print(json.dumps(result.output, indent=4, default=str))