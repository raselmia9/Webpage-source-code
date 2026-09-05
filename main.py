import asyncio
import random
import re
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    playlist_file = "playlist.m3u"
    status_file = "status.txt"
    
    status_messages = []
    m3u_output = ["#EXTM3U"]

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
        }
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # ইউনিক ডিভাইস দিয়ে পেজ ওপেন করা
        device = random.choice(device_profiles)
        context = await browser.new_context(
            viewport=device["viewport"],
            device_scale_factor=device["device_scale_factor"],
            is_mobile=True,
            has_touch=True,
            user_agent=device["user_agent"],
            locale="bn-BD",
            timezone_id="Asia/Dhaka",
            geolocation={"latitude": 23.8103, "longitude": 90.4125},
            permissions=["geolocation"]
        )
        
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = await context.new_page()
        
        print("🟢 Opening FanCode Live page...")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(6)
            
            # পেজ একটু স্ক্রোল করা যাতে কন্টেন্ট লোড হয়
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2);")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"🔴 Error loading main page: {str(e)}")
            
        # ম্যাচ লিংকগুলো খুঁজে বের করার শক্তিশালী সিলেক্টর
        matches = await page.evaluate("""() => {
            let items = [];
            let links = document.querySelectorAll('a[href*="/matches/"]');
            links.forEach(a => {
                let href = a.href;
                let text = a.innerText.trim();
                if (href && text && !items.some(i => i.href === href)) {
                    let cleanText = text.replace(/\\n/g, ' - ').replace(/LIVE/g, '').trim();
                    if(cleanText.length > 3) {
                        items.push({ title: cleanText, href: href });
                    }
                }
            });
            return items;
        .slice(0, 5); // পরীক্ষামূলকভাবে প্রথম ৫টি ম্যাচ নেব
        }""")
        
        print(f"🟢 Found matches count: {len(matches)}")
        
        if not matches:
            print("🟡 No matches found via selector, checking fallback...")
            status_messages.append("🔴 No matches found on main page.")
        else:
            for match in matches:
                m_title = match['title']
                m_url = match['href']
                print(f"🟡 Processing: {m_title}")
                
                # প্রতিটি ম্যাচের জন্য একদম নতুন ট্যাব/কন্টেক্সট (যাতে ট্রায়াল লিমিট রিসেট থাকে)
                m_device = random.choice(device_profiles)
                m_context = await browser.new_context(
                    viewport=m_device["viewport"],
                    device_scale_factor=m_device["device_scale_factor"],
                    is_mobile=True,
                    has_touch=True,
                    user_agent=m_device["user_agent"]
                )
                m_page = await m_context.new_page()
                
                captured_links = []
                
                # নেটওয়ার্ক রিকোয়েস্ট থেকে m3u8 ধরা
                m_page.on("request", lambda req: captured_links.append(req.url) if ".m3u8" in req.url else None)
                
                try:
                    await m_page.goto(m_url, wait_until="domcontentloaded", timeout=30000)
                    print("🟡 Waiting for stream to trigger...")
                    await asyncio.sleep(8) # ভিডিও লোড হওয়ার সময়
                except Exception as e:
                    print(f"🟡 Match page error: {str(e)}")
                
                # লিংক ফিল্টার করা
                m3u8_link = next((l for l in captured_links if "master" in l or "hls" in l), captured_links[0] if captured_links else None)
                
                if m3u8_link:
                    print(f"🟢 Captured M3U8: {m3u8_link}")
                    m3u_output.append(f'#EXTINF:-1,{m_title}')
                    m3u_output.append(m3u8_link)
                    status_messages.append(f"🟢 Success: {m_title}")
                else:
                    print(f"🟡 M3U8 not found, using watch url.")
                    m3u_output.append(f'#EXTINF:-1,{m_title}')
                    m3u_output.append(m_url)
                    status_messages.append(f"🟡 Fallback: {m_title}")
                
                await m_context.close()

        await browser.close()
        
        # ফাইল নিশ্চিতভাবে সেভ করা
        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_output))
            
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages) if status_messages else "🔴 No status recorded.")
            
        print("🟢 Files successfully updated and saved.")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
