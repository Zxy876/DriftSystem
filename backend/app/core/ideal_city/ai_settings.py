"""Shared Ideal City AI timeout configuration."""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

AI_CONNECT_TIMEOUT = float(os.getenv("IDEAL_CITY_AI_CONNECT_TIMEOUT", "6.0"))
AI_READ_TIMEOUT = float(os.getenv("IDEAL_CITY_AI_READ_TIMEOUT", "6.0"))
