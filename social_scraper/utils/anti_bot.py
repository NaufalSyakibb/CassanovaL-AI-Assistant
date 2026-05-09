"""
anti_bot.py — Proxy rotation, User-Agent rotation, random delays,
               Selenium stealth, and optional 2Captcha integration.
"""
import random
import time
import requests
from typing import Optional

from utils.config_loader import get_proxies, get_user_agents, get_api_key, get_scraping_config

_cfg = get_scraping_config()

# ── Proxy rotation ─────────────────────────────────────────────────────────────

def get_proxy() -> dict:
    """Return a random proxy dict for requests, or {} if none configured."""
    proxies = get_proxies()
    if not proxies:
        return {}
    p = random.choice(proxies)
    return {"http": p, "https": p}


def get_working_proxy(test_url: str = "https://httpbin.org/ip", timeout: int = 5) -> dict:
    """Cycle through proxies and return the first one that responds."""
    for proxy_url in random.sample(get_proxies(), len(get_proxies())):
        proxy = {"http": proxy_url, "https": proxy_url}
        try:
            r = requests.get(test_url, proxies=proxy, timeout=timeout)
            if r.status_code == 200:
                return proxy
        except Exception:
            continue
    return {}


# ── User-Agent rotation ────────────────────────────────────────────────────────

def get_user_agent() -> str:
    """Return a random User-Agent string."""
    agents = get_user_agents()
    return random.choice(agents) if agents else (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )


def get_headers(extra: dict | None = None) -> dict:
    """Return realistic browser headers with a random User-Agent."""
    headers = {
        "User-Agent": get_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
        "DNT": "1",
    }
    if extra:
        headers.update(extra)
    return headers


def get_json_headers(extra: dict | None = None) -> dict:
    """Headers for JSON/API endpoints."""
    headers = {
        "User-Agent": get_user_agent(),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
    }
    if extra:
        headers.update(extra)
    return headers


# ── Delay ─────────────────────────────────────────────────────────────────────

def random_delay(min_s: float | None = None, max_s: float | None = None) -> None:
    """Sleep for a random duration to mimic human browsing."""
    lo = min_s if min_s is not None else _cfg.get("delay_min", 2)
    hi = max_s if max_s is not None else _cfg.get("delay_max", 10)
    delay = random.uniform(lo, hi)
    time.sleep(delay)


def micro_delay() -> None:
    """Very short delay (0.5–2s) between page elements."""
    time.sleep(random.uniform(0.5, 2.0))


# ── Retry wrapper ─────────────────────────────────────────────────────────────

def safe_get(
    url: str,
    session: Optional[requests.Session] = None,
    headers: dict | None = None,
    proxy: dict | None = None,
    retries: int | None = None,
    timeout: int | None = None,
) -> Optional[requests.Response]:
    """requests.get with retry, rotating proxy, and random delay on error."""
    max_retries = retries if retries is not None else _cfg.get("max_retries", 3)
    req_timeout = timeout if timeout is not None else _cfg.get("timeout", 30)
    used_headers = headers or get_headers()
    used_proxy = proxy if proxy is not None else get_proxy()
    get_fn = (session.get if session else requests.get)

    for attempt in range(1, max_retries + 1):
        try:
            resp = get_fn(
                url,
                headers=used_headers,
                proxies=used_proxy or None,
                timeout=req_timeout,
            )
            if resp.status_code == 429:
                wait = _cfg.get("retry_delay", 5) * attempt
                time.sleep(wait)
                used_proxy = get_proxy()  # rotate on 429
                continue
            return resp
        except requests.exceptions.RequestException:
            if attempt < max_retries:
                time.sleep(_cfg.get("retry_delay", 5) * attempt)
                used_proxy = get_proxy()
    return None


# ── Selenium stealth helpers ───────────────────────────────────────────────────

def make_driver(headless: bool = True):
    """Build a Selenium Chrome driver with stealth options."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(f"--user-agent={get_user_agent()}")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=en-US")

        proxy_list = get_proxies()
        if proxy_list:
            proxy = random.choice(proxy_list).replace("http://", "")
            options.add_argument(f"--proxy-server={proxy}")

        driver = webdriver.Chrome(options=options)
        # Remove navigator.webdriver flag
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        driver.execute_cdp_cmd(
            "Network.setUserAgentOverride",
            {"userAgent": get_user_agent()},
        )
        return driver
    except ImportError:
        raise ImportError("selenium not installed. Run: pip install selenium")


# ── 2Captcha integration ───────────────────────────────────────────────────────

def solve_recaptcha(site_key: str, page_url: str) -> Optional[str]:
    """Solve reCAPTCHA v2 using 2Captcha API. Returns token or None."""
    api_key = get_api_key("twocaptcha")
    if not api_key:
        return None
    try:
        # Submit task
        r = requests.post(
            "https://2captcha.com/in.php",
            data={
                "key": api_key,
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": page_url,
                "json": 1,
            },
            timeout=15,
        )
        result = r.json()
        if result.get("status") != 1:
            return None
        captcha_id = result["request"]

        # Poll for solution (max 2 min)
        for _ in range(24):
            time.sleep(5)
            poll = requests.get(
                f"https://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1",
                timeout=10,
            ).json()
            if poll.get("status") == 1:
                return poll["request"]
        return None
    except Exception:
        return None
