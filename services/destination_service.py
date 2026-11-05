"""
RouteWise AI – Indian Destination Knowledge Base
Structured static data for featured destinations.
"""

from __future__ import annotations

from typing import Dict, List, Optional

DESTINATIONS: List[Dict] = [
    {
        "name": "Rajasthan",
        "city": "Jaipur",
        "region": "North India",
        "type": "heritage",
        "description": "The Pink City – majestic forts, vibrant bazaars, royal palaces and the iconic Amber Fort.",
        "best_months": ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"],
        "tags": ["history", "culture", "architecture", "photography"],
        "avg_budget_per_day_inr": 2500,
        "highlights": ["Amber Fort", "Hawa Mahal", "City Palace", "Jantar Mantar", "Nahargarh Fort"],
        "latitude": 26.9124,
        "longitude": 75.7873,
        "destination_type": "tier2",
    },
    {
        "name": "Goa",
        "city": "Panaji",
        "region": "West India",
        "type": "beach",
        "description": "Golden beaches, Portuguese heritage, world-class seafood and legendary nightlife.",
        "best_months": ["Nov", "Dec", "Jan", "Feb", "Mar"],
        "tags": ["beach", "food", "nightlife", "history", "watersports"],
        "avg_budget_per_day_inr": 3000,
        "highlights": ["Baga Beach", "Old Goa Churches", "Dudhsagar Falls", "Anjuna Market", "Fort Aguada"],
        "latitude": 15.4909,
        "longitude": 73.8278,
        "destination_type": "beach",
    },
    {
        "name": "Kerala",
        "city": "Kochi",
        "region": "South India",
        "type": "nature",
        "description": "God's Own Country – backwaters, hill stations, Ayurveda and rich coastal heritage.",
        "best_months": ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb"],
        "tags": ["nature", "backwaters", "wellness", "culture", "food"],
        "avg_budget_per_day_inr": 2800,
        "highlights": ["Alleppey Backwaters", "Munnar Tea Gardens", "Periyar Wildlife", "Fort Kochi", "Wayanad"],
        "latitude": 9.9312,
        "longitude": 76.2673,
        "destination_type": "tier2",
    },
    {
        "name": "Himachal Pradesh",
        "city": "Shimla",
        "region": "North India",
        "type": "hill",
        "description": "Snow-capped peaks, cedar forests, adventure sports and colonial-era charm.",
        "best_months": ["Mar", "Apr", "May", "Jun", "Sep", "Oct"],
        "tags": ["adventure", "nature", "trekking", "snow", "photography"],
        "avg_budget_per_day_inr": 2200,
        "highlights": ["The Ridge", "Kufri", "Manali", "Rohtang Pass", "Solang Valley"],
        "latitude": 31.1048,
        "longitude": 77.1734,
        "destination_type": "hill",
    },
    {
        "name": "Uttarakhand",
        "city": "Dehradun",
        "region": "North India",
        "type": "hill",
        "description": "Gateway to the Himalayas – pilgrimage trails, wildlife reserves and river rafting.",
        "best_months": ["Mar", "Apr", "May", "Jun", "Sep", "Oct", "Nov"],
        "tags": ["adventure", "pilgrimage", "nature", "trekking", "wildlife"],
        "avg_budget_per_day_inr": 2000,
        "highlights": ["Rishikesh", "Haridwar", "Mussoorie", "Jim Corbett", "Valley of Flowers"],
        "latitude": 30.3165,
        "longitude": 78.0322,
        "destination_type": "hill",
    },
    {
        "name": "Tamil Nadu",
        "city": "Chennai",
        "region": "South India",
        "type": "heritage",
        "description": "Ancient Dravidian temples, classical dance, rich cuisine and UNESCO heritage sites.",
        "best_months": ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"],
        "tags": ["history", "culture", "temples", "food", "art"],
        "avg_budget_per_day_inr": 2000,
        "highlights": ["Madurai Meenakshi Temple", "Mahabalipuram", "Thanjavur", "Ooty", "Marina Beach"],
        "latitude": 13.0827,
        "longitude": 80.2707,
        "destination_type": "metro",
    },
    {
        "name": "Ladakh",
        "city": "Leh",
        "region": "North India",
        "type": "adventure",
        "description": "High-altitude desert landscape, ancient monasteries and bucket-list bike expeditions.",
        "best_months": ["Jun", "Jul", "Aug", "Sep"],
        "tags": ["adventure", "photography", "spirituality", "trekking", "biking"],
        "avg_budget_per_day_inr": 3500,
        "highlights": ["Pangong Tso", "Nubra Valley", "Hemis Monastery", "Magnetic Hill", "Zanskar"],
        "latitude": 34.1526,
        "longitude": 77.5771,
        "destination_type": "hill",
    },
    {
        "name": "Varanasi",
        "city": "Varanasi",
        "region": "North India",
        "type": "spiritual",
        "description": "One of the world's oldest living cities – ghats, Ganga Aarti and profound spirituality.",
        "best_months": ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"],
        "tags": ["spirituality", "culture", "photography", "history", "food"],
        "avg_budget_per_day_inr": 1800,
        "highlights": ["Dashashwamedh Ghat", "Kashi Vishwanath Temple", "Sarnath", "Assi Ghat", "Boat Ride"],
        "latitude": 25.3176,
        "longitude": 82.9739,
        "destination_type": "tier2",
    },
]

DESTINATION_INDEX: Dict[str, Dict] = {d["name"].lower(): d for d in DESTINATIONS}
DESTINATION_INDEX.update({d["city"].lower(): d for d in DESTINATIONS})


def get_destination(name: str) -> Optional[Dict]:
    return DESTINATION_INDEX.get(name.strip().lower())


def get_featured_destinations(limit: int = 6) -> List[Dict]:
    return DESTINATIONS[:limit]


def get_destinations_by_type(dest_type: str) -> List[Dict]:
    return [d for d in DESTINATIONS if d["type"] == dest_type]


def get_destinations_by_tag(tag: str) -> List[Dict]:
    return [d for d in DESTINATIONS if tag.lower() in [t.lower() for t in d["tags"]]]


def get_best_season_destinations(month: str) -> List[Dict]:
    return [d for d in DESTINATIONS if month in d.get("best_months", [])]
