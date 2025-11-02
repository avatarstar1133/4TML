"""
Configuration file for Requirements Engineering Agent
"""

import os

# ============================================
# GOOGLE API KEY CONFIGURATION
# ============================================

# Option 1: Set your API key directly here (NOT recommended for production)
GOOGLE_API_KEY = "AIzaSyCQqaMRaRAz9Ewmflh66LZUovZ7v87Q9mY"

# Option 2: Read from environment variable (Recommended)
# GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

# ============================================
# DO NOT EDIT BELOW THIS LINE
# ============================================

def setup_api_key():
    """Setup the API key in environment"""
    if GOOGLE_API_KEY and GOOGLE_API_KEY != "AIzaSyCQqaMRaRAz9Ewmflh66LZUovZ7v87Q9mY":
        os.environ['GOOGLE_API_KEY'] = GOOGLE_API_KEY
        return True
    return False