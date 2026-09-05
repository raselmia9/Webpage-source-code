import asyncio
import random
import os
import re
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    status_file = "status.txt"
    row_link_dir = "Row_Link"
    
    # Row_Link ফোল্ডার তৈরি করা না থাকলে তৈরি করে নেওয়া
    os.makedirs(row_link_dir, exist_ok=True)
    
    status_messages = []

    mobile_devices = [
        {
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "viewport": {"width": 390, "height": 844},
            "device_scale_factor": 3
        },
        {
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
            "viewport": {"width": 393, "height": 852},
            "device_scale_factor": 3
        },
        {
            "user_agent": "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "viewport": {"width": 412, "height": 915},
            "device_scale_factor": 2.625
        }
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # ১. প্রথমে লাইভ পেজ থেকে সমস্ত ম্যাচের তালিকা ও ওয়াচ লিংক সংগ্রহ করা
        selected_device = random.choice(mobile_devices)
        context = await browser.new_context(
            viewport=selected_device["viewport"],
            device_scale_factor=selected_device["device_scale_factor"],
            is_mobile=True,
            has_touch=True,
            user_agent=selected_device["user_agent"],
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
        except Exception as e:
            print(f"🟡 Network idle timeout, proceeding: {str(e)}")
            
        await asyncio.sleep(5)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
        await asyncio.sleep(2)
        
        page_text = await page.evaluate("document.body.innerText")
        
        matches_to_process = []
        
        if "LIVE" in page_text:
            print("🟢 Live matches found. Extracting match watch links...")
            extracted_cards = await page.evaluate("""() => {
                let cardsList = [];
                let matchLinks = document.querySelectorAll('a[href*="/matches/"], a[href*="/match/"]');
                
                matchLinks.forEach(link => {
                    let href = link.href ? link.href : "";
                    let text = link.innerText ? link.innerText.trim() : "";
                    
                    if (href && text && !text.includes("Live Now") && text.length > 5) {
                        if (!cardsList.some(c => c.href === href)) {
                            let lines = text.split('\\n').map(l => l.trim()).filter(l => l && l !== "LIVE");
                            let mainTitle = lines.length >= 2 ? lines[0] + " vs " + lines[1] : (lines.length == 1 ? lines[0] : "FanCode Match");
                            cardsList.push({ title: mainTitle, href: href });
                        }
                    }
                });
                return cardsList;
            }""")
            matches_to_process = extracted_cards
        
        await context.close()
        
        if not matches_to_process:
            msg = "🔴 No active match links found to capture m3u8."
            print(msg)
            status_messages.append(msg)
        else:
            print(f"🟢 Found {len(matches_to_process)} match(es). Capturing m3u8 streams...")
            
            # ২. প্রতিটি ম্যাচের ওয়াচ পেজে আলাদা ফ্রেশ ব্রাউজার কনটেক্সট দিয়ে প্রবেশ করে m3u8 ক্যাপচার করা
            for match in matches_to_process:
                match_title = match['title']
                match_url = match['href']
                
                safe_title = re.sub(r'[\\/*?:"<>|]', "", match_title).strip()
                if not safe_title:
                    safe_title = "fancode_match"
                
                print(f"🟡 Processing match: {match_title}")
                
                # প্রতিটি ম্যাচের জন্য একদম নতুন ফ্রেশ ডিভাইস প্রোফাইল
                match_device = random.choice(mobile_devices)
                m_context = await browser.new_context(
                    viewport=match_device["viewport"],
                    device_scale_factor=match_device["device_scale_factor"],
                    is_mobile=True,
                    has_touch=True,
                    user_agent=match_device["user_agent"],
                    locale="bn-BD",
                    timezone_id="Asia/Dhaka",
                    geolocation={"latitude": 23.8103, "longitude": 90.4125},
                    permissions=["geolocation"]
                )
                await m_context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
                m_page = await m_context.new_page()
                
                master_m3u8_url = []
                
                # নেটওয়ার্ক রিকোয়েস্ট ইন্টারসেপ্ট করে .m3u8 বা মাস্টার প্লেলিস্ট ধরা
                m_page.on("request", lambda req: master_m3u8_url.append(req.url) if ".m3u8" in req.url and ("hls" in req.url or "pdlive" in req.url) else None)
                
                try:
                    await m_page.goto(match_url, wait_until="networkidle", timeout=35000)
                    # প্লেয়ার লোড হয়ে স্ট্রিম রিকোয়েস্ট পাঠানোর জন্য সময় দেওয়া
                    await asyncio.sleep(8)
                    
                    # যদি সরাসরি রিকোয়েস্টে m3u8 না পাওয়া যায়, পেজের ভেতরে প্লে বাটন ক্লিক সিমুলেট করা যেতে পারে
                    await m_page.evaluate("window.scrollTo(0, 300);")
                    await asyncio.sleep(3)
                except Exception as e:
                    print(f"🟡 Error loading match page {match_title}: {str(e)}")
                
                playlist_content = None
                # ক্যাপচার করা m3u8 লিংক থেকে ব্রাউজারের সেশন ব্যবহার করে মূল ডাটা ফেচ করা
                target_m3u8 = next((url for url in master_m3u8_url if "master" in url or "index" in url or "hls" in url), None)
                if not target_m3u8 and master_m3u8_url:
                    target_m3u8 = master_m3u8_url[0] # যেকোনো একটি কার্যকরী m3u8 লিংক
                
                if target_m3u8:
                    try:
                        # ব্রাউজারের ভেতর থেকেই ফেচ করলে কুকি ও অথেন্টিকেশন বজায় থাকে
                        playlist_content = await m_page.evaluate(f"""async () => {{
                            try {{
                                let res = await fetch('{target_m3u8}');
                                return await res.text();
                            }} catch(err) {{
                                return null;
                            }}
                        }}""")
                    except:
                        pass
                
                match_file_path = os.path.join(row_link_dir, f"{safe_title}.m3u")
                
                if playlist_content and "#EXTM3U" in playlist_content:
                    with open(match_file_path, "w", encoding="utf-8") as f:
                        f.write(playlist_content)
                    msg_success = f"🟢 Captured and saved multi-resolution M3U for: {match_title}"
                    print(msg_success)
                    status_messages.append(msg_success)
                else:
                    # যদি মাস্টার প্লেলিস্ট সরাসরি ফেচ না হয়, আপনার দেওয়া ফরম্যাটের ফলব্যাক বা স্ট্যাটাস লেখা
                    fallback_m3u = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=1789512,AVERAGE-BANDWIDTH=1789512,CODECS="avc1.64001f,mp4a.40.2",PROGRAM-ID=1,RESOLUTION=1280x720,FRAME-RATE=25.000
{match_url}"""
                    with open(match_file_path, "w", encoding="utf-8") as f:
                        f.write(fallback_m3u)
                    msg_fallback = f"🟡 Saved fallback match info for: {match_title}"
                    print(msg_fallback)
                    status_messages.append(msg_fallback)
                
                await m_context.close()

        await browser.close()
        
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
        print("🟢 All tasks completed successfully.")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
