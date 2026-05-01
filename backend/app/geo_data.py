"""
Weighted attack source countries — mirrors real-world threat intelligence distributions.
Coordinates are geographic centroids.
"""

ATTACK_SOURCES = [
    {"country": "China",          "code": "CN", "lat": 35.86,  "lng": 104.19,  "weight": 0.24},
    {"country": "Russia",         "code": "RU", "lat": 61.52,  "lng": 105.31,  "weight": 0.18},
    {"country": "United States",  "code": "US", "lat": 37.09,  "lng": -95.71,  "weight": 0.12},
    {"country": "Brazil",         "code": "BR", "lat": -14.23, "lng": -51.92,  "weight": 0.07},
    {"country": "India",          "code": "IN", "lat": 20.59,  "lng": 78.96,   "weight": 0.07},
    {"country": "North Korea",    "code": "KP", "lat": 40.33,  "lng": 127.51,  "weight": 0.06},
    {"country": "Iran",           "code": "IR", "lat": 32.42,  "lng": 53.68,   "weight": 0.05},
    {"country": "Netherlands",    "code": "NL", "lat": 52.13,  "lng": 5.29,    "weight": 0.04},
    {"country": "Germany",        "code": "DE", "lat": 51.16,  "lng": 10.45,   "weight": 0.04},
    {"country": "Ukraine",        "code": "UA", "lat": 48.37,  "lng": 31.16,   "weight": 0.04},
    {"country": "Romania",        "code": "RO", "lat": 45.94,  "lng": 24.96,   "weight": 0.03},
    {"country": "Nigeria",        "code": "NG", "lat": 9.08,   "lng": 8.67,    "weight": 0.03},
    {"country": "Pakistan",       "code": "PK", "lat": 30.37,  "lng": 69.34,   "weight": 0.02},
    {"country": "Indonesia",      "code": "ID", "lat": -0.78,  "lng": 113.92,  "weight": 0.01},
]

_weights = [s["weight"] for s in ATTACK_SOURCES]
_total = sum(_weights)
_weights = [w / _total for w in _weights]


def random_source() -> dict:
    import random
    return random.choices(ATTACK_SOURCES, weights=_weights, k=1)[0]
