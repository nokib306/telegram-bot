"""
Webshare API Integration Module
Copy this ENTIRE file as webshare_api.py
"""

import requests
import random
import logging

logger = logging.getLogger(__name__)

# API Configuration - Already Set!
WEBSHARE_API_KEY = "w8lbp6n0edqpmvlaru697hsdittgb0zq673cbik9"
WEBSHARE_BASE_URL = "https://proxy.webshare.io/api/v2"

def get_headers():
    """Get authorization headers"""
    return {
        "Authorization": f"Token {WEBSHARE_API_KEY}"
    }

def fetch_all_proxies():
    """Fetch all proxies from Webshare"""
    try:
        response = requests.get(
            f"{WEBSHARE_BASE_URL}/proxy/list/",
            headers=get_headers(),
            params={'mode': 'direct', 'page_size': 100}
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            logger.info(f"✅ Webshare: Fetched {len(results)} proxies")
            return results
        else:
            logger.error(f"❌ Webshare API Error: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Webshare Exception: {e}")
        return []

def get_random_proxy(proxy_type=None):
    """Get a random proxy from pool"""
    proxies = fetch_all_proxies()
    
    if not proxies:
        logger.warning("⚠️ No proxies available")
        return None
    
    proxy = random.choice(proxies)
    logger.info(f"✅ Selected: {proxy.get('proxy_address')}")
    return proxy

def rotate_ip(current_proxy_id):
    """Get different IP (rotation)"""
    proxies = fetch_all_proxies()
    
    if not proxies:
        return None
    
    available = [p for p in proxies if p.get('id') != current_proxy_id]
    
    if not available:
        logger.warning("⚠️ Only one proxy, returning random")
        return random.choice(proxies)
    
    new_proxy = random.choice(available)
    logger.info(f"🔄 Rotated to: {new_proxy.get('proxy_address')}")
    return new_proxy

def extract_proxy_details(webshare_proxy, proxy_type='HTTP'):
    """Extract proxy details"""
    if not webshare_proxy:
        return None
    
    return {
        'ip': webshare_proxy.get('proxy_address'),
        'port': str(webshare_proxy.get('port')),
        'username': webshare_proxy.get('username'),
        'password': webshare_proxy.get('password'),
        'webshare_id': webshare_proxy.get('id'),
        'type': proxy_type
    }

def test_connection():
    """Test API connection"""
    try:
        response = requests.get(
            f"{WEBSHARE_BASE_URL}/profile/",
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Connected! Account: {data.get('email')}")
            return True
        else:
            logger.error(f"❌ Failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def get_proxy_count():
    """Get total proxies available"""
    proxies = fetch_all_proxies()
    return len(proxies)

if __name__ == "__main__":
    print("Testing Webshare connection...")
    if test_connection():
        count = get_proxy_count()
        print(f"✅ Working! Available proxies: {count}")
        if count > 0:
            proxy = get_random_proxy()
            if proxy:
                details = extract_proxy_details(proxy)
                print(f"\nSample Proxy:")
                print(f"IP: {details['ip']}")
                print(f"Port: {details['port']}")
    else:
        print("❌ Connection failed!")
