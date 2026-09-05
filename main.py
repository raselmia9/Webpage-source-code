import asyncio
import random
import re
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    playlist_file = "playlist.m3u"
    status_file = "status.txt"
    
    status_messages = []

    # বিভিন্ন রেন্ডম মোবাইল ও ট্যাবলেট ডিভাইসের বড় লিস্ট, যাতে প্রতিবার একদম নতুন পরিচয় যায়
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
        },
        {
            "user_agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "viewport": {"width": 412, "height": 892},
            "device_scale_factor": 2.625
        }
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # প্রথমে লাইভ পেজ থেকে ম্যাচের লিংক সংগ্রহ করার জন্য রেন্ডম ডিভাইস কনটেক্সট
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
        
        print("🟢 Loading FanCode Live Sports page to fetch match URLs...")
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"🟡 Network timeout, moving forward: {str(e)}")
            
        await asyncio.sleep(5)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
        await asyncio.sleep(2)
        
        page_text = await page.evaluate("document.body.innerText")
        matches_to_process = []
        
        if "LIVE" in page_text:
            print("🟢 Live matches found. Extracting watch links...")
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
            msg = "🔴 No active matches found right now."
            print(msg)
            status_messages.append(msg)
        else:
            print(f"🟢 Found {len(matches_to_process)} match(es). Starting stream interception with unique device profiles...")
            
            # প্রতিটি ম্যাচের জন্য সম্পূর্ণ আলাদা এবং ফ্রেশ ডিভাইস প্রোফাইল নিয়ে ব্রাউজার সেশন শুরু করা
            for match in matches_to_process:
                match_title = match['title']
                match_url = match['href']
                
                print(f"🟡 Processing match: {match_title}")
                
                # প্রতিটি ম্যাচের জন্য একদম নতুন ডিভাইস সিলেক্ট করা হচ্ছে (যাতে ২ মিনিটের ট্রায়াল বাইপাস হয়)
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
                
                captured_streams = []
                
                # নেটওয়ার্ক রিকোয়েস্ট ও এপিআই রেসপন্স থেকে m3u8 লিংক হাতা
                async def intercept_response(response):
                    try:
                        url = response.url
                        if ".m3u8" in url or "playback" in url or "stream" in url:
                            if "master" in url or "hls" in url or "pdlive" in url or "index" in url:
                                captured_streams.append(url)
                            if "application/json" in response.headers.get("content-type", ""):
                                body_text = await response.text()
                                if ".m3u8" in body_text:
                                    found = re.findall(r'https?://[^\s<>"]+?\.m3u8[^\s<>"]*', body_text)
                                    for f_url in found:
                                        captured_streams.append(f_url)
                    except:
                        pass

                m_page.on("response", intercept_response)
                
                try:
                    # ওয়াচ পেজে প্রবেশ করা
                    await m_page.goto(match_url, wait_until="networkidle", timeout=35000)
                    # প্লেয়ার লোড হওয়ার জন্য এবং ট্রায়াল শুরু হওয়ার ঠিক আগের মুহূর্তের স্ট্রিম ট্রিগার ধরার জন্য সময়
                    await asyncio.sleep(6)
                    # পেজে হালকা স্ক্রোল করা যাতে প্লেয়ার রেন্ডার হয়
                    await m_page.evaluate("window.scrollTo(0, 350);")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"🟡 Error navigating match page: {str(e)}")
                
                # কার্যকরী স্ট্রিম লিংক নির্বাচন করা
                valid_stream = None
                if captured_streams:
                    # অগ্রাধিকার দেওয়া হবে যেখানে 'master' বা 'hls' বা নির্দিষ্ট পডলাইভ আছে
                    valid_stream = next((s for s in captured_streams if "master" in s or "hls" in s), captured_streams[0])
                
                if valid_stream:
                    print(f"🟢 Captured Master Stream URL for {match_title}: {valid_stream}")
                    m3u_output.append(f'#EXTINF:-1 tvg-name="{match_title}" group-title="FanCode Live",{match_title}')
                    m3u_output.append(valid_stream)
                    status_messages.append(f"🟢 Captured stream: {match_title}")
                else:
                    print(f"🟡 Could not capture direct stream for {match_title}, using fallback watch URL.")
                    m3u_output.append(f'#EXTINF:-1 tvg-name="{match_title}" group-title="FanCode Live",{match_title}')
                    m3u_output.append(match_url)
                    status_messages.append(f"🟡 Fallback to watch URL: {match_title}")
                
                await m_context.close()

        await browser.close()
        
        # মূল playlist.m3u ফাইলে ফলাফল সেভ করা
        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_output))
            
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
            
        print("🟢 Stream capture process finished successfully.")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
