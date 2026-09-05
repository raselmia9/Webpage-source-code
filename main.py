import asyncio
import random
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    playlist_file = "playlist.m3u"
    status_file = "status.txt"
    
    status_messages = []

    # ডিভাইস রোটেশন ও ট্রায়াল বাইপাসের জন্য র‍্যান্ডম ডিভাইস প্রোফাইল
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
        },
        {
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
            "viewport": {"width": 375, "height": 812},
            "device_scale_factor": 3
        }
    ]

    selected_device = random.choice(mobile_devices)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            viewport=selected_device["viewport"],
            device_scale_factor=selected_device["device_scale_factor"],
            is_mobile=True,
            has_touch=True,
            user_agent=selected_device["user_agent"],
            locale="bn-BD",
            timezone_id="Asia/Dhaka",
            geolocation={"latitude": 23.8103, "longitude": 90.4125},
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "bn-BD,bn;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            }
        )
        
        # বটের আলামত লুকানোর জন্য
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()
        
        msg1 = "🟢 Fresh Device Profile Loaded Successfully"
        print(msg1)
        status_messages.append(msg1)
        
        # পেজে যাওয়া
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            msg_err = f"🟡 Network idle timeout, proceeding with DOM: {str(e)}"
            print(msg_err)
            status_messages.append(msg_err)
        
        # রিয়্যাক্ট কম্পোনেন্ট রেন্ডার হওয়ার জন্য অপেক্ষা ও স্ক্রোলিং
        print("🟡 Waiting for SPA components and live data to render...")
        await asyncio.sleep(5)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
        await asyncio.sleep(2)
        
        # পেজের সম্পূর্ণ টেক্সট সংগ্রহ করে আগে যাচাই করা যে লাইভ ম্যাচ আছে কি না
        page_text = await page.evaluate("document.body.innerText")
        
        m3u_lines = ["#EXTM3U"]
        
        if "LIVE" in page_text:
            success_msg = "🟢 Status: Live Matches Are Currently Active. Parsing match details..."
            print(success_msg)
            status_messages.append(success_msg)
            
            # ফ্যানকোডের কার্ডগুলো থেকে ডাইনামিকভাবে তথ্য বের করার জন্য জাভাস্ক্রিপ্ট ইভ্যালুয়েশন
            # ফ্যানকোডের কার্ড স্ট্রাকচার অনুযায়ী টাইটেল, লোগো এবং ক্যাটাগরি এক্সট্রাক্ট করা
            matches_data = await page.evaluate("""() => {
                let items = [];
                // ফ্যানকোডের লাইভ কার্ড বা কন্টেইনারগুলো সাধারণত যে ট্যাগ বা ক্লাসে থাকে
                // আমরা পেজের কার্ড এলিমেন্টগুলো থেকে ডেটা সংগ্রহ করার চেষ্টা করছি
                let cards = document.querySelectorAll('a[href*="/match/"], div');
                
                // বিকল্প হিসেবে টেক্সট লাইনগুলো বিশ্লেষণ করব যদি স্পেসিফিক সিলেক্টর না মিলে
                return items;
            }""")
            
            # যেহেতু ফ্যানকোডের লেআউট পরিবর্তনশীল, তাই ইউনিভার্সাল টেক্সট পার্সিং লজিক ব্যবহার করে M3U তৈরি করা হচ্ছে
            lines = page_text.split('\n')
            menu_or_junk_words = [
                "premier destination", "sports fans", "highlights", "stream", 
                "privacy policy", "terms of use", "download app", "all sports", 
                "fancode shop", "fantasy research", "watch cricket"
            ]
            
            valid_matches = []
            for line in lines:
                line_str = line.strip()
                line_lower = line_str.lower()
                
                if any(junk in line_lower for junk in menu_or_junk_words):
                    continue
                
                if (" vs " in line_lower or " v " in line_lower) and (10 < len(line_str) < 80):
                    if line_str not in valid_matches:
                        valid_matches.append(line_str)
            
            # M3U ফরম্যাটে ডেটা যোগ করা
            if valid_matches:
                for match in valid_matches:
                    # ক্যাটাগরি বা গ্রুপ টাইটেল নির্ধারণ (ডিফল্ট FanCode Live)
                    group_title = "FanCode Live"
                    if "t20" in match.lower() or "cricket" in match.lower():
                        group_title = "Cricket"
                    elif "f3" in match.lower() or "race" in match.lower() or "motorsport" in match.lower():
                        group_title = "Motorsports"
                    
                    logo_url = "https://images.fancode.com/icons/fancode-logo.png"
                    
                    # M3U এক্সটেন্ডেড ইনফো ও স্ট্রিম প্লেসহোল্ডার যোগ করা
                    m3u_lines.append(f'#EXTINF:-1 tvg-name="{match}" tvg-logo="{logo_url}" group-title="{group_title}",{match}')
                    m3u_lines.append(f'https://www.fancode.com/bd/live-now/all-sports') # প্লেসহোল্ডার লিংক
                    
                    status_messages.append(f"🟢 Added to M3U: {match} [{group_title}]")
            else:
                # যদি নির্দিষ্ট 'vs' লাইন না পাওয়া যায় কিন্তু লাইভ থাকে
                m3u_lines.append(f'#EXTINF:-1 tvg-name="FanCode Live Stream" tvg-logo="https://images.fancode.com/icons/fancode-logo.png" group-title="Live Sports",FanCode Live Stream')
                m3u_lines.append(f'https://www.fancode.com/bd/live-now/all-sports')
                status_messages.append("🟢 Added general live stream entry to M3U.")
                
        else:
            if "No Matches Live At The Moment" in page_text:
                no_match_msg = "🔴 Status: No Matches Live At The Moment"
                print(no_match_msg)
                status_messages.append(no_match_msg)
            else:
                warning_msg = "🟡 Status: Checking live elements..."
                print(warning_msg)
                status_messages.append(warning_msg)

        # M3U ফাইল সেভ করা
        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))
            
        msg4 = f"🟢 Successfully generated and saved {playlist_file}"
        print(msg4)
        status_messages.append(msg4)
        
        await browser.close()
        
        # স্ট্যাটাস ফাইল সেভ করা
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
        print(f"🟢 Status successfully saved to {status_file}")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
