import asyncio
import random
import os
import re
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    status_file = "status.txt"
    row_link_dir = "Row_Link"
    
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
        
        # ১. লাইভ পেজ থেকে ম্যাচের তালিকা ও ওয়াচ লিংক সংগ্রহ
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
            msg = "🔴 No active match links found."
            print(msg)
            status_messages.append(msg)
        else:
            print(f"🟢 Found {len(matches_to_process)} match(es). Capturing stream APIs...")
            
            # ২. প্রতিটি ম্যাচের ওয়াচ পেজে প্রবেশ করে API রেসপন্স থেকে m3u8 লিংক ধরা
            for match in matches_to_process:
                match_title = match['title']
                match_url = match['href']
                
                safe_title = re.sub(r'[\\/*?:"<>|]', "", match_title).strip()
                if not safe_title:
                    safe_title = "fancode_match"
                
                print(f"🟡 Processing match: {match_title}")
                
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
                
                captured_master_url = []
                
                # নেটওয়ার্ক রেসপন্স ইন্টারসেপ্ট করে .m3u8 লিংক বা স্ট্রিম এপিআই খুঁজে বের করা
                async def handle_response(response):
                    try:
                        url = response.url
                        if ".m3u8" in url or "playback" in url or "stream" in url:
                            if "master" in url or "hls" in url or "pdlive" in url:
                                captured_master_url.append(url)
                            # যদি এপিআই রেসপন্স JSON হয়, তার ভেতর থেকেও m3u8 খুঁজে নেওয়া
                            if "application/json" in response.headers.get("content-type", ""):
                                text = await response.text()
                                if ".m3u8" in text:
                                    found_urls = re.findall(r'https?://[^\s<>"]+?\.m3u8[^\s<>"]*', text)
                                    for fu in found_urls:
                                        captured_master_url.append(fu)
                    except:
                        pass

                m_page.on("response", handle_response)
                
                try:
                    await m_page.goto(match_url, wait_until="networkidle", timeout=35000)
                    # প্লেয়ার ও ভিডিও স্ট্রিম রিকোয়েস্ট ট্রিগার হওয়ার জন্য পর্যাপ্ত সময় ও স্ক্রোলিং
                    await asyncio.sleep(6)
                    await m_page.evaluate("window.scrollTo(0, 400);")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"🟡 Error loading match page: {str(e)}")
                
                match_file_path = os.path.join(row_link_dir, f"{safe_title}.m3u")
                master_playlist_content = None
                
                # যে মাস্টার .m3u8 লিংকটি পাওয়া গেছে, সেটির ডেটা ফেচ করা
                valid_m3u8_url = captured_master_url[0] if captured_master_url else None
                
                if valid_m3u8_url:
                    print(f"🟢 Found stream URL: {valid_m3u8_url}")
                    try:
                        master_playlist_content = await m_page.evaluate(f"""async () => {{
                            try {{
                                let res = await fetch('{valid_m3u8_url}');
                                return await res.text();
                            }} catch(err) {{
                                return null;
                            }}
                        }}""")
                    except:
                        pass
                
                # যদি মাস্টার প্লেলিস্ট সরাসরি ফেচ করা যায় এবং তা রেজুলেশনভিত্তিক হয়
                if master_playlist_content and "#EXT-X-STREAM-INF" in master_playlist_content:
                    with open(match_file_path, "w", encoding="utf-8") as f:
                        f.write(master_playlist_content)
                    msg_success = f"🟢 Successfully captured multi-res M3U for: {match_title}"
                    print(msg_success)
                    status_messages.append(msg_success)
                else:
                    # যদি মাস্টার প্লেলিস্ট সরাসরি না পাওয়া যায়, তবে পেজের সোর্স থেকে স্ট্রিম খোঁজার চেষ্টা
                    page_content = await m_page.content()
                    extracted_from_page = re.findall(r'https?://[^\s<>"]+?\.m3u8[^\s<>"]*', page_content)
                    
                    if extracted_from_page:
                        # যদি পেজের ভেতরে রিয়েল m3u8 লিংক থাকে, তা দিয়ে একটি ফরম্যাট তৈরি করা
                        stream_url = extracted_from_page[0]
                        custom_m3u = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=1789512,AVERAGE-BANDWIDTH=1789512,CODECS="avc1.64001f,mp4a.40.2",PROGRAM-ID=1,RESOLUTION=1280x720,FRAME-RATE=25.000
{stream_url}"""
                        with open(match_file_path, "w", encoding="utf-8") as f:
                            f.write(custom_m3u)
                        msg_p = f"🟢 Captured stream link from page content for: {match_title}"
                        print(msg_p)
                        status_messages.append(msg_p)
                    else:
                        # একদম না পেলে ফলব্যাক
                        fallback_m3u = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=1789512,AVERAGE-BANDWIDTH=1789512,CODECS="avc1.64001f,mp4a.40.2",PROGRAM-ID=1,RESOLUTION=1280x720,FRAME-RATE=25.000
{match_url}"""
                        with open(match_file_path, "w", encoding="utf-8") as f:
                            f.write(fallback_m3u)
                        msg_fallback = f"🟡 Saved fallback for: {match_title}"
                        print(msg_fallback)
                        status_messages.append(msg_fallback)
                
                await m_context.close()

        await browser.close()
        
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
        print("🟢 All extraction tasks finished.")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
