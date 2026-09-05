import asyncio
import random
import re
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    playlist_file = "playlist.m3u"
    status_file = "status.txt"
    
    status_messages = []

    # ডিভাইস প্রফাইলসমূহ
    device_profiles = [
        {
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
            "viewport": {"width": 393, "height": 852},
            "device_scale_factor": 3
        },
        {
            "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            "viewport": {"width": 412, "height": 915},
            "device_scale_factor": 2.625
        },
        {
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
            "viewport": {"width": 390, "height": 844},
            "device_scale_factor": 3
        }
    ]

    async with async_playwright() as p:
        # আসল Chrome ব্যবহার করে বট ডিটেকশন ও কোডেক ইস্যু বাইপাস করা
        try:
            browser = await p.chromium.launch(
                headless=True,
                channel="chrome",  # সিস্টেমের গুগল ক্রোম ব্যবহার করবে
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )
        except Exception:
            # ক্রোম না থাকলে ডিফল্ট ক্রোমিয়াম
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
        
        # ১. লাইভ পেজ থেকে ম্যাচের লিংক সংগ্রহ
        initial_device = random.choice(device_profiles)
        context = await browser.new_context(
            viewport=initial_device["viewport"],
            device_scale_factor=initial_device["device_scale_factor"],
            is_mobile=True,
            has_touch=True,
            user_agent=initial_device["user_agent"],
            locale="bn-BD",
            timezone_id="Asia/Dhaka",
            geolocation={"latitude": 23.8103, "longitude": 90.4125},
            permissions=["geolocation"]
        )
        
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = await context.new_page()
        
        print("🟢 Loading FanCode Live Sports page...")
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=30000)
        except:
            pass
            
        await asyncio.sleep(5)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
        await asyncio.sleep(2)
        
        page_text = await page.evaluate("document.body.innerText")
        matches_to_process = []
        
        if "LIVE" in page_text:
            matches_to_process = await page.evaluate("""() => {
                let list = [];
                let links = document.querySelectorAll('a[href*="/matches/"], a[href*="/match/"]');
                links.forEach(l => {
                    let href = l.href ? l.href : "";
                    let text = l.innerText ? l.innerText.trim() : "";
                    if(href && text && !text.includes("Live Now") && text.length > 5) {
                        if(!list.some(item => item.href === href)) {
                            let lines = text.split('\\n').map(x => x.trim()).filter(x => x && x !== "LIVE");
                            let title = lines.length >= 2 ? lines[0] + " vs " + lines[1] : (lines.length == 1 ? lines[0] : "FanCode Match");
                            list.push({ title: title, href: href });
                        }
                    }
                });
                return list;
            }""")
        
        await context.close()
        
        m3u_output = ["#EXTM3U"]
        
        if not matches_to_process:
            print("🔴 No active matches found.")
            status_messages.append("🔴 No active matches found.")
        else:
            print(f"🟢 Found {len(matches_to_process)} match(es). Processing...")
            
            # ২. প্রতিটি ম্যাচের প্লেব্যাক ইন্টারসেপশন
            for match in matches_to_process:
                match_title = match['title']
                match_url = match['href']
                
                print(f"🟡 Processing match: {match_title}")
                
                unique_device = random.choice(device_profiles)
                m_context = await browser.new_context(
                    viewport=unique_device["viewport"],
                    device_scale_factor=unique_device["device_scale_factor"],
                    is_mobile=True,
                    has_touch=True,
                    user_agent=unique_device["user_agent"],
                    locale="bn-BD",
                    timezone_id="Asia/Dhaka",
                    geolocation={"latitude": 23.8103, "longitude": 90.4125},
                    permissions=["geolocation"]
                )
                await m_context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
                m_page = await m_context.new_page()
                
                captured_m3u8 = []
                
                # রিকোয়েস্ট URL পর্যবেক্ষণ
                async def on_request(request):
                    if ".m3u8" in request.url:
                        captured_m3u8.append(request.url)

                # ব্যাকএন্ড এপিআই রেসপন্স (JSON Body) পর্যবেক্ষণ
                async def on_response(response):
                    try:
                        url = response.url
                        # প্লেব্যাক এপিআই রিকোয়েস্ট থেকে m3u8 খুঁজে বের করা
                        if "playback" in url or "stream" in url or "graphql" in url or ".m3u8" in url:
                            ct = response.headers.get("content-type", "")
                            if "json" in ct or "text" in ct:
                                text = await response.text()
                                if ".m3u8" in text:
                                    matches = re.findall(r'https?://[^\s<>"]+?\.m3u8[^\s<>"]*', text)
                                    for m in matches:
                                        # এস্কেপ ক্যারেক্টার পরিষ্কার করা
                                        clean_url = m.replace("\\/", "/").replace("\\u0026", "&")
                                        captured_m3u8.append(clean_url)
                    except:
                        pass

                m_page.on("request", on_request)
                m_page.on("response", on_response)
                
                try:
                    await m_page.goto(match_url, wait_until="domcontentloaded", timeout=35000)
                    
                    print("🟡 Waiting 10s for player and stream API response...")
                    await asyncio.sleep(10) # ভিডিও এবং প্লেব্যাক এপিআই ট্রিগার হওয়ার সময়
                    
                except Exception as e:
                    print(f"🟡 Error during page load: {str(e)}")
                
                # ফিল্টারিং
                valid_stream = None
                if captured_m3u8:
                    unique_links = list(set(captured_m3u8))
                    print(f"🔍 Raw captured links count: {len(unique_links)}")
                    # মাস্টার স্ট্রিম ফাইল অগ্রাধিকার পাবে
                    valid_stream = next((u for u in unique_links if "master" in u or "hls" in u or "pdlive" in u), unique_links[0])
                
                if valid_stream:
                    print(f"🟢 SUCCESS - Master Link: {valid_stream}")
                    m3u_output.append(f'#EXTINF:-1 tvg-name="{match_title}" group-title="FanCode Live",{match_title}')
                    m3u_output.append(valid_stream)
                    status_messages.append(f"🟢 Captured: {match_title}")
                else:
                    print(f"🔴 Stream capture failed for: {match_title}")
                    m3u_output.append(f'#EXTINF:-1 tvg-name="{match_title}" group-title="FanCode Live",{match_title}')
                    m3u_output.append(match_url)
                    status_messages.append(f"🟡 Fallback used: {match_title}")
                
                await m_context.close()

        await browser.close()
        
        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_output))
            
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
            
        print("🟢 Completed.")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
