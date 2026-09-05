import asyncio
import random
os_import = __import__('os')
import re
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    playlist_file = "playlist.m3u"
    status_file = "status.txt"
    index_file = "Index.html"
    row_link_dir = "Row_Link"
    
    os_import.makedirs(row_link_dir, exist_ok=True)
    
    status_messages = []
    m3u_output = ["#EXTM3U"]
    html_match_list = []

    # বিভিন্ন মোবাইল ও ট্যাবলেটের ভিন্ন এবং শক্তিশালী ডিভাইস প্রফাইলসমূহ
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
            "viewport": {"width": 412, "height": 915},
            "device_scale_factor": 2.625
        }
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # ১. প্রথমে মূল পেজ থেকে ম্যাচগুলোর লিস্ট সংগ্রহ করার জন্য একটি প্রাথমিক কন্টেক্সট
        init_device = random.choice(device_profiles)
        init_context = await browser.new_context(
            viewport=init_device["viewport"],
            device_scale_factor=init_device["device_scale_factor"],
            is_mobile=True,
            has_touch=True,
            user_agent=init_device["user_agent"],
            locale="bn-BD",
            timezone_id="Asia/Dhaka"
        )
        init_page = await init_context.new_page()
        
        print("🟢 Opening FanCode Live page...")
        try:
            await init_page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(6)
            await init_page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2);")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"🔴 Error loading main page: {str(e)}")
            
        matches = await init_page.evaluate("""() => {
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
            return items.slice(0, 10);
        }""")
        
        await init_context.close()
        print(f"🟢 Found matches count: {len(matches)}")
        
        if not matches:
            print("🟡 No matches found.")
            status_messages.append("🔴 No matches found on main page.")
        else:
            # ২. প্রতিটি ম্যাচের জন্য সম্পূর্ণ আলাদা এবং নতুন পরিচয় (Fresh Context) তৈরি করে লুপ চালানো
            for match in matches:
                m_title = match['title']
                m_url = match['href']
                print(f"🟡 Processing with NEW identity: {m_title}")
                
                safe_title = re.sub(r'[\\/*?:"<>|]', "", m_title).strip()
                if not safe_title:
                    safe_title = "fancode_match"
                
                # প্রতিবার র‍্যান্ডম নতুন ডিভাইস ও জিরো কুকি কনটেক্সট
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
                
                captured_links = []
                m_page.on("request", lambda req: captured_links.append(req.url) if ".m3u8" in req.url else None)
                
                try:
                    await m_page.goto(m_url, wait_until="domcontentloaded", timeout=30000)
                    print("🟡 Waiting for stream API & trial trigger...")
                    await asyncio.sleep(8)
                except Exception as e:
                    print(f"🟡 Match page error: {str(e)}")
                
                m3u8_link = next((l for l in captured_links if "master" in l or "hls" in l), captured_links[0] if captured_links else None)
                final_stream_url = m3u8_link if m3u8_link else m_url
                
                # আলাদা ফাইলে সংরক্ষণ (Row_Link)
                match_file_path = os_import.path.join(row_link_dir, f"{safe_title}.m3u")
                match_m3u_content = f"""#EXTM3U
#EXTINF:-1,{m_title}
{final_stream_url}"""
                with open(match_file_path, "w", encoding="utf-8") as mf:
                    mf.write(match_m3u_content)

                # মূল playlist.m3u এর ডেটা
                m3u_output.append(f'#EXTINF:-1,{m_title}')
                m3u_output.append(final_stream_url)
                
                # Index.html এর লিস্ট
                html_match_list.append(f"<li><b>{m_title}</b>: <a href='{final_stream_url}' target='_blank'>Stream Link</a> | <a href='Row_Link/{safe_title}.m3u' target='_blank'>Download .m3u</a></li>")
                
                if m3u8_link:
                    status_messages.append(f"🟢 Success: {m_title}")
                else:
                    status_messages.append(f"🟡 Fallback (Trial/Link missing): {m_title}")
                
                # কাজ শেষ হওয়ার সাথে সাথে এই কন্টেক্সট পুরোপুরি ধ্বংস বা বন্ধ করা যাতে ক্যাশ বা কুকি ডিলিট হয়ে যায়
                await m_context.close()

        await browser.close()
        
        # ৩. ৪টি প্রধান ফাইল আপডেট করা
        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_output))
            
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages) if status_messages else "🔴 No status recorded.")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>FanCode Live Playlists</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #121212; color: #fff; }}
        h1 {{ color: #ff6600; }}
        ul {{ line-height: 1.8; }}
        a {{ color: #00bcd4; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>FanCode Live Matches</h1>
    <p>Auto-generated live stream playlists with fresh device identities.</p>
    <ul>
        {"".join(html_match_list) if html_match_list else "<li>No active matches found right now.</li>"}
    </ul>
</body>
</html>"""
        with open(index_file, "w", encoding="utf-8") as hf:
            hf.write(html_content)
            
        print("🟢 All 4 targets successfully generated with independent identities!")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
