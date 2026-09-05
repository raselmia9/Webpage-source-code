import asyncio
import os
import random
import re
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
    
    # প্রতিবার রান করার সময় Row_Link ফোল্ডারটি সম্পূর্ণ পরিষ্কার করে নতুন করে তৈরি করা
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
                
                safe_title_slug = re.sub(r'[^a-zA-Z0-9]', '_', m_title)
                safe_title_slug = re.sub(r'_+', '_', safe_title_slug).strip('_')
                match_file_name = f"match_{index + 1}_{safe_title_slug}.m3u8"
                match_file_path = os.path.join(row_link_folder, match_file_name)
                
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
                
                captured_links = []
                # নেটওয়ার্ক রিকোয়েস্ট থেকে যেকোনো m3u8 বা স্ট্রিম লিংক ক্যাপচার করার লজিক
                match_page.on("request", lambda req: captured_links.append(req.url) if ".m3u8" in req.url else None)
                
                try:
                    await match_page.goto(m_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(9)
                except Exception as e:
                    print(f"🟡 Match page error: {str(e)}")
                
                # যেকোনো একটি রেজোলিউশনের লিংক (যেমন 240p, 360p বা অন্য কিছু) অথবা প্রথম প্রাপ্ত m3u8 লিংকটি বেছে নেওয়া
                valid_stream_link = next((l for l in captured_links if any(res in l for res in ["240p", "360p", "480p", "720p", "1080p"]) and "master" not in l), captured_links[0] if captured_links else None)
                
                sub_file_content = ["#EXTM3U"]
                
                if valid_stream_link:
                    print(f"🟢 Captured Valid Stream Link for: {m_title}")
                    
                    sub_file_content.append(f'#EXTINF:-1 tvg-logo="{m_logo}" group-title="FanCode",{m_title}')
                    sub_file_content.append("#EXT-X-VERSION:3")
                    
                    # প্রাপ্ত লিংকের রেজোলিউশন অংশটি চিহ্নিত করে সেটিকে টেমপ্লেটে রূপান্তর করা
                    base_link_cleaned = valid_stream_link
                    detected_res = "240p" # ডিফল্ট ধরে নেওয়া
                    for r_name in ["1080p", "720p", "540p", "480p", "360p", "240p"]:
                        if f"{r_name}.m3u8" in base_link_cleaned:
                            detected_res = r_name
                            break
                    
                    base_link_cleaned = base_link_cleaned.replace(f"{detected_res}.m3u8", "REPLACE_RES.m3u8")
                    
                    resolutions = [
                        {"res": "240p", "bandwidth": "446936", "size": "426x240", "codecs": "avc1.42e015,mp4a.40.2"},
                        {"res": "360p", "bandwidth": "702376", "size": "640x360", "codecs": "avc1.42e01e,mp4a.40.2"},
                        {"res": "480p", "bandwidth": "1023224", "size": "854x480", "codecs": "avc1.4d401e,mp4a.40.2"},
                        {"res": "540p", "bandwidth": "1278664", "size": "960x540", "codecs": "avc1.4d401f,mp4a.40.2"},
                        {"res": "720p", "bandwidth": "1789512", "size": "1280x720", "codecs": "avc1.64001f,mp4a.40.2"},
                        {"res": "1080p", "bandwidth": "3322120", "size": "1920x1080", "codecs": "avc1.640028,mp4a.40.2"}
                    ]
                    
                    for item in resolutions:
                        r = item["res"]
                        bw = item["bandwidth"]
                        sz = item["size"]
                        cd = item["codecs"]
                        
                        link_with_res = base_link_cleaned.replace("REPLACE_RES", r)
                        sub_file_content.append(f'#EXT-X-STREAM-INF:BANDWIDTH={bw},AVERAGE-BANDWIDTH={bw},CODECS="{cd}",PROGRAM-ID=1,RESOLUTION={sz},FRAME-RATE=25.000')
                        sub_file_content.append(link_with_res)
                    
                    status_messages.append(f"🟢 Success (Multi-Res Generated): {m_title}")
                else:
                    # লিংক না পেলে আর মূল পেজ বসবে না, বরং একটি এর বা খালি স্ট্যাটাস দেখাবে যাতে ভুল লিংক প্লে না হয়
                    print(f"🔴 No stream link found for: {m_title}")
                    sub_file_content.append(f'#EXTINF:-1 tvg-logo="{m_logo}" group-title="FanCode",{m_title} (Stream Unavailable)')
                    sub_file_content.append("http://invalid-link-or-stream-not-started.m3u8")
                    status_messages.append(f"🔴 Stream Not Found: {m_title}")
                
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
            
        print("🟢 Process completed successfully!")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
