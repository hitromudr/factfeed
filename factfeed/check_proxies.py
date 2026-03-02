import asyncio
import sys

from curl_cffi.requests import AsyncSession


async def check_proxy(name, url):
    print(f"Checking {name} ({url})...")
    try:
        async with AsyncSession(proxy=url) as s:
            # impersonate="chrome120" to match production code
            resp = await s.get(
                "https://ifconfig.me", timeout=10, impersonate="chrome120"
            )
            print(f"✅ {name}: {resp.text.strip()}")
            return True
    except Exception as e:
        print(f"❌ {name}: Failed - {e}")
        return False


async def main():
    # Since we are using network_mode: "host", we can access localhost directly
    proxies = [
        ("Direct", None),
        ("Riga", "http://127.0.0.1:3129"),
        ("Polka", "http://127.0.0.1:4129"),
        ("Turka", "http://127.0.0.1:5129"),
        ("Nitro", "http://127.0.0.1:6129"),
    ]

    print("=== Checking Connectivity via Proxies (Host Mode) ===\n")
    results = await asyncio.gather(*[check_proxy(name, url) for name, url in proxies])

    if not any(results):
        print("\nCRITICAL: No connection working!")
        sys.exit(1)
    else:
        print("\nAt least one connection is working.")


if __name__ == "__main__":
    asyncio.run(main())
