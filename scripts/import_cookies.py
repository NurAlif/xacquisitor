import json
import os
import sys
from pathlib import Path

def convert_netscape_to_playwright(cookies_txt_path, output_json_path):
    """
    Converts a Netscape format cookies.txt file to Playwright JSON format.
    """
    cookies = []
    if not os.path.exists(cookies_txt_path):
        print(f"Error: {cookies_txt_path} not found.")
        return False

    with open(cookies_txt_path, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            
            parts = line.strip().split('\t')
            if len(parts) < 7:
                continue
            
            # Netscape format: 
            # domain, is_domain_cookie, path, is_secure, expires, name, value
            domain = parts[0]
            path = parts[2]
            secure = parts[3].upper() == 'TRUE'
            expires = int(parts[4])
            name = parts[5]
            value = parts[6]
            
            cookie = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
                "expires": expires,
                "httpOnly": False, # Netscape doesn't explicitly store this, usually False
                "secure": secure,
                "sameSite": "Lax" # Default
            }
            cookies.append(cookie)
    
    with open(output_json_path, 'w') as f:
        json.dump(cookies, f, indent=2)
    
    print(f"✅ Successfully converted {len(cookies)} cookies to {output_json_path}")
    return True

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "cookies.txt"
    dst = sys.argv[2] if len(sys.argv) > 2 else "x_cookies.json"
    convert_netscape_to_playwright(src, dst)
