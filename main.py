import asyncio
import random
import re
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    playlist_file = "playlist.m3u"
    status_file = "status.txt"
    
    status_messages = []

    # প্রতিবার একদম নতুন ডিভাইসের পরিচয় দেওয়ার জন্য বিভিন্ন রেন্ডম মোবাইল ও ট্যাবলেটের প্রফাইল
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
        
        # ১. প্রথমে লাইভ পেজ থেকে ম্যাচের তালিকা সংগ্রহের জন্য একটি ডিভাইস কনটেক্সট
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
            print(f"🟢 Found {len(matches_to_process)} match(es). Processing with unique device identities...")
            
            # ২. প্রতিটি ম্যাচের জন্য আলাদা ও নতুন ডিভাইস প্রোফাইল ব্যবহার করে লিংক ক্যাপচার
            for match in matches_to_process:
                match_title = match['title']
                match_url = match['href']
                
                print(f"🟡 Processing match: {match_title}")
                
                # সম্পূর্ণ নতুন ডিভাইস সিলেক্ট করা হচ্ছে
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
                
                captured_requests = []
                
                # নেটওয়ার্কের সমস্ত রিকোয়েস্ট বা ইউআরএল ধরে লিস্টে জমা করা
                async def intercept_requests(request):
                    captured_requests.append(request.url)

                m_page.on("request", intercept_requests)
                
                try:
                    # ম্যাচের ওয়াচ পেজে প্রবেশ করা
                    await m_page.goto(match_url, wait_until="domcontentloaded", timeout=35000)
                    
                    # কোনো ক্লিক ছাড়াই ভিডিও অটোমেটিক লোড ও স্ট্রিম ট্রিগার হওয়ার জন্য ৫ থেকে ৭ সেকেন্ড অপেক্ষা করা
                    print("🟡 Waiting for video player to auto-load and trigger stream...")
                    await asyncio.sleep(7)
                    
                    # পেজটি একটু স্ক্রোল করে প্লেয়ার রেন্ডার নিশ্চিত করা
                    await m_page.evaluate("window.scrollTo(0, 300);")
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    print(f"🟡 Error during navigation: {str(e)}")
                
                # ৩. ক্যাচ করা সমস্ত রিকোয়েস্ট থেকে ফিল্টার করে m3u8 লিংক বের করা
                valid_m3u8 = None
                if captured_requests:
                    # ডুপ্লিকেট রিমুভ করা
                    unique_urls = list(set(captured_requests))
                    
                    # ফিল্টারিং: যে লিংকগুলোতে .m3u8 রয়েছে
                    m3u8_candidates = [url for url in unique_urls if ".m3u8" in url]
                    
                    if m3u8_candidates:
                        # অগ্রাধিকার দেওয়া হবে যেখানে মাস্টার বা hls কিউয়ার্ড আছে
                        valid_m3u8 = next((u for u in m3u8_candidates if "master" in u or "hls" in u or "pdlive" in u), m3u8_candidates[0])
                
                # ৪. ফলাফল আউটপুট বা প্লেলিস্টে যোগ করা
                if valid_m3u8:
                    print(f"🟢 SUCCESS - M3U8 Master Link Found: {valid_m3u8}")
                    m3u_output.append(f'#EXTINF:-1 tvg-name="{match_title}" group-title="FanCode Live",{match_title}')
                    m3u_output.append(valid_m3u8)
                    status_messages.append(f"🟢 Captured: {match_title}")
                else:
                    print(f"🟡 M3U8 link not found, falling back to watch URL for: {match_title}")
                    m3u_output.append(f'#EXTINF:-1 tvg-name="{match_title}" group-title="FanCode Live",{match_title}')
                    m3u_output.append(match_url)
                    status_messages.append(f"🟡 Fallback used: {match_title}")
                
                await m_context.close()

        await browser.close()
        
        # ফাইল সেভ করা
        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_output))
            
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
            
        print("🟢 Process finished successfully.")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
