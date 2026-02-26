from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    errors = []
    page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)
    page.on("pageerror", lambda err: errors.append(f"[PAGE_ERROR] {err}"))
    
    page.goto("http://localhost:8080", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(3000)
    
    # Capture all console messages
    all_msgs = []
    page2 = browser.new_page()
    page2.on("console", lambda msg: all_msgs.append(f"[{msg.type}] {msg.text}"))
    page2.on("pageerror", lambda err: all_msgs.append(f"[PAGE_ERROR] {err}"))
    page2.goto("http://localhost:8080", wait_until="networkidle", timeout=15000)
    page2.wait_for_timeout(3000)
    
    page2.screenshot(path="c:/Users/autre/Downloads/Voco V2/services/mcp-gateway/debug_screenshot.png", full_page=True)
    
    print("=== ERRORS FROM PAGE 1 ===")
    for e in errors:
        print(e)
    print(f"\n=== ALL CONSOLE FROM PAGE 2 ({len(all_msgs)} msgs) ===")
    for m in all_msgs:
        print(m)
    
    # Also try demo mode
    page3 = browser.new_page()
    demo_errors = []
    page3.on("console", lambda msg: demo_errors.append(f"[{msg.type}] {msg.text}"))
    page3.on("pageerror", lambda err: demo_errors.append(f"[PAGE_ERROR] {err}"))
    page3.goto("http://localhost:8080?demo=true", wait_until="networkidle", timeout=15000)
    page3.wait_for_timeout(3000)
    page3.screenshot(path="c:/Users/autre/Downloads/Voco V2/services/mcp-gateway/debug_demo_screenshot.png", full_page=True)
    
    print(f"\n=== DEMO MODE CONSOLE ({len(demo_errors)} msgs) ===")
    for m in demo_errors:
        print(m)
    
    browser.close()
