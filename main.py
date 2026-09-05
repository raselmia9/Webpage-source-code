import asyncio
import random
import re
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    playlist_file = "playlist.m3u"
    status_file = "status.txt"
    
    status_messages = []

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
        browser = await p.chromium.launch(headless=True)
        
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
        else:
            print(f"🟢 Found {len(matches_to_process)} match(es). Capturing master stream links...")
            
            for match in matches_to_process:
                match_title = match['title']
                match_url = match['href']
                
                print(f"🟡 Processing match: {match_title}")
                
                # প্রতিটি ম্যাচের জন্য একদম ফ্রেশ ডিভাইস ও কুকি সেশন
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
                
                master_links = []
                
                # নেটওয়ার্ক রিকোয়েস্ট এবং এক্সএইচআর/ফেচ রেসপন্স নিখুঁতভাবে ট্র্যাক করা
                async def track_requests(request):
                    url = request.url
                    if ".m3u8" in url:
                        master_links.append(url)

                m_page.on("request", track_requests)
                
                try:
                    await m_page.goto(match_url, wait_until="domcontentloaded", timeout=35000)
                    
                    # ভিডিও প্লেয়ার লোড হওয়ার জন্য পর্যাপ্ত সময় দেওয়া এবং প্লে বাটনে ক্লিক বা স্ক্রোল সিমুলেট করা
                    await asyncio.sleep(4)
                    
                    # পেজে ক্লিক করে ভিডিও প্লেয়ার ট্রিগার করা
                    try:
                        await m_page.click("video, .plyr__video-wrapper, [class*='player']", timeout=5000)
                    except:
                        pass
                        
                    await asyncio.sleep(6)
                    await m_page.evaluate("window.scrollTo(0, 300);")
                    await asyncio.sleep(4)
                    
                except Exception as e:
                    print(f"🟡 Error during navigation: {str(e)}")
                
                # মাস্টার লিংক ফিল্টার করা (যেটাতে রেজুলেশন বা মাস্টার কিউয়ার্ড আছে)
                valid_master = None
                if master_links:
                    # ডুপ্লিকেট রিমুভ করা
                    unique_links = list(set(master_links))
                    # মাস্টার বা hls সমৃদ্ধ লিংকটি আগে খোঁজা
                    valid_master = next((l for l in unique_links if "master" in l or "hls" in l or "pdlive" in l), unique_links[0])
                
                if valid_master:
                    print(f"🟢 SUCCESS - Master Link Captured: {valid_master}")
                    m3u_output.append(f'#EXTINF:-1 tvg-name="{match_title}" group-title="FanCode Live",{match_title}')
                    m3u_output.append(valid_master)
                    status_messages.append(f"🟢 Captured Master Link: {match_title}")
                else:
                    print(f"🟡 Master link not found for {match_title}")
                    status_messages.append(f"🟡 Failed to capture master link: {match_title}")
                
                await m_context.close()

        await browser.close()
        
        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_output))
            
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
            
        print("🟢 Process completed.")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
