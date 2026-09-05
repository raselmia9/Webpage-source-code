import asyncio
import os
import random
import re
import urllib.parse
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    main_playlist_file = "playlist.m3u"
    row_link_folder = "Row_Link"
    status_file = "status.txt"
    index_file = "Index.html"
    
    github_username = "raselmia9"
    repo_name = "Webpage-source-code"
    branch_name = "main"
    base_raw_url = f"https://raw.githubusercontent.com/{github_username}/{repo_name}/refs/heads/{branch_name}/{row_link_folder}"
    
    # Row_Link ফোল্ডার পরিষ্কার করা
    if os.path.exists(row_link_folder):
        for old_file in os.listdir(row_link_folder):
            old_file_path = os.path.join(row_link_folder, old_file)
            if os.path.isfile(old_file_path):
                os.remove(old_file_path)
    else:
        os.makedirs(row_link_folder)
        
    status_messages = []
    main_m3u_output = ["#EXTM3U"]
    html_match_list = []

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
        temp_browser = await p.chromium.launch(headless=True)
        temp_context = await temp_browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        temp_page = await temp_context.new_page()
        
        print("🟢 Opening FanCode Live page...")
        matches = []
        try:
            await temp_page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(6)
            await temp_page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2);")
            await asyncio.sleep(3)
            
            matches = await temp_page.evaluate("""() => {
                let items = [];
                let matchCards = document.querySelectorAll('a[href*="/matches/"]');
                matchCards.forEach(a => {
                    let href = a.href;
                    let text = a.innerText.replace(/\\n/g, ' - ').trim();
                    let cleanText = text.replace(/LIVE/g, '').replace(/\\s+/g, ' ').trim();
                    
                    let imgTag = a.querySelector('img');
                    let logoUrl = imgTag ? (imgTag.src || imgTag.getAttribute('data-src') || '') : '';

                    if (href && cleanText.length > 5 && !items.some(i => i.href === href)) {
                        items.push({ title: cleanText, href: href, logo: logoUrl });
                    }
                });
                return items.slice(0, 10);
            }""")
        except Exception as e:
            print(f"🔴 Error loading main page: {str(e)}")
            
        await temp_browser.close()
        print(f"🟢 Found matches count: {len(matches)}")
        
        if not matches:
            print("🟡 No matches found.")
            status_messages.append("🔴 No matches found on main page.")
        else:
            for index, match in enumerate(matches):
                m_title = match['title']
                m_url = match['href']
                m_logo = match['logo']
                print(f"🟡 Processing: {m_title}")
                
                match_browser = await p.chromium.launch(headless=True)
                unique_device = random.choice(device_profiles)
                
                match_context = await match_browser.new_context(
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
                
                await match_context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
                match_page = await match_context.new_page()
                
                captured_playlists = []
                
                # নেটওয়ার্ক রেসপন্স থেকে সরাসরি .m3u8 ফাইলের টেক্সট ডেটা ক্যাচ করার ফাংশন
                async def handle_response(response):
                    if "m3u8" in response.url:
                        try:
                            body = await response.text()
                            if "#EXTM3U" in body or "#EXT-X-STREAM-INF" in body:
                                captured_playlists.append({
                                    "url": response.url,
                                    "content": body
                                })
                        except Exception:
                            pass

                match_page.on("response", lambda resp: asyncio.create_task(handle_response(resp)))
                
                try:
                    await match_page.goto(m_url, wait_until="domcontentloaded", timeout=30000)
                    # প্লেয়ার লোড হওয়ার জন্য পর্যাপ্ত সময় অপেক্ষা করা
                    await asyncio.sleep(12)
                except Exception as e:
                    print(f"🟡 Match page error: {str(e)}")
                
                # মাস্টার প্লেলিস্ট বা যেকোনো ভ্যালিড প্লেলিস্ট খুঁজে বের করা
                valid_playlist = next((p for p in captured_playlists if "#EXT-X-STREAM-INF" in p['content']), captured_playlists[0] if captured_playlists else None)
                
                if not valid_playlist:
                    print(f"🔴 Stream not available for: {m_title}. Skipping.")
                    status_messages.append(f"🔴 Skipped (No Stream): {m_title}")
                    await match_browser.close()
                    continue
                
                print(f"🟢 Captured Playlist from Response: {valid_playlist['url']}")
                
                safe_title_slug = re.sub(r'[^a-zA-Z0-9]', '_', m_title)
                safe_title_slug = re.sub(r'_+', '_', safe_title_slug).strip('_')
                match_file_name = f"match_{index + 1}_{safe_title_slug}.m3u8"
                match_file_path = os.path.join(row_link_folder, match_file_name)
                
                # ভেতরের ইউআরএলগুলোকে Absolute URL এ রূপান্তর করা (যাতে относительный বা রিলেটিভ পাথ ভেঙে না যায়)
                playlist_url = valid_playlist['url']
                raw_content = valid_playlist['content']
                
                processed_lines = []
                for line in raw_content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        absolute_url = urllib.parse.urljoin(playlist_url, line)
                        processed_lines.append(absolute_url)
                    else:
                        processed_lines.append(line)
                
                final_playlist_body = "\n".join(processed_lines)
                
                sub_file_content = [
                    "#EXTM3U",
                    f'#EXTINF:-1 tvg-logo="{m_logo}" group-title="FanCode",{m_title}',
                    final_playlist_body
                ]
                
                status_messages.append(f"🟢 Success: {m_title}")
                
                with open(match_file_path, "w", encoding="utf-8") as sf:
                    sf.write("\n".join(sub_file_content))
                
                full_raw_file_url = f"{base_raw_url}/{match_file_name}"
                main_m3u_output.append(f'#EXTINF:-1 tvg-logo="{m_logo}" group-title="FanCode",{m_title}')
                main_m3u_output.append(full_raw_file_url)
                
                html_match_list.append(f"<li><img src='{m_logo}' width='30' style='vertical-align:middle;margin-right:8px;'><b>{m_title}</b> -> <a href='{row_link_folder}/{match_file_name}' target='_blank'>Row File (.m3u8)</a></li>")
                
                await match_browser.close()

        with open(main_playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(main_m3u_output))
            
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
        ul {{ line-height: 2; }}
        a {{ color: #00bcd4; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>FanCode Live Matches (Row Links Structure)</h1>
    <p>Individual match playlist files are stored in the <code>{row_link_folder}/</code> folder with <code>.m3u8</code> extension.</p>
    <ul>
        {"".join(html_match_list) if html_match_list else "<li>No active streams found right now.</li>"}
    </ul>
</body>
</html>"""
        with open(index_file, "w", encoding="utf-8") as hf:
            hf.write(html_content)
            
        print("🟢 Process completed successfully with exact tokenized response content!")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
