import json
from pathlib import Path
from typing import List, Dict, Union

def validate_cookies(cookies: Union[str, List[Dict]]) -> List[Dict]:
    """Validate and format cookie data."""
    if isinstance(cookies, str):
        try:
            cookies = json.loads(cookies)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format for cookies.")
    
    if not isinstance(cookies, list):
        # Handle single cookie object
        if isinstance(cookies, dict):
            cookies = [cookies]
        else:
            raise ValueError("Cookies must be a list of cookie objects.")
            
    # Basic validation of required playwright cookie fields
    for cookie in cookies:
        if not isinstance(cookie, dict):
             raise ValueError("Each cookie must be an object.")
        if "name" not in cookie or "value" not in cookie:
            raise ValueError("Each cookie must have 'name' and 'value'.")
        if "domain" not in cookie:
             # Default to .x.com if missing, though usually it should be there
             cookie["domain"] = ".x.com"
            
    return cookies

def save_cookies(cookies: List[Dict], target_file: Path):
    """Save cookies to the specified JSON file."""
    target_file.parent.mkdir(exist_ok=True, parents=True)
    with open(target_file, "w") as f:
        json.dump(cookies, f, indent=2)
    return True
