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
        
        # রিয়্যাক্ট কম্পোনেন্ট রেন্ডার হওয়ার জন্য সময় ও স্ক্রোলিং
        print("🟡 Waiting for SPA components and live cards to render...")
        await asyncio.sleep(5)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
        await asyncio.sleep(2)
        
        # পেজের সম্পূর্ণ টেক্সট সংগ্রহ করে লাইভ যাচাই করা
        page_text = await page.evaluate("document.body.innerText")
        
        m3u_lines = ["#EXTM3U"]
        
        if "LIVE" in page_text:
            success_msg = "🟢 Status: Live Matches Are Active. Extracting card details..."
            print(success_msg)
            status_messages.append(success_msg)
            
            # ফ্যানকোডের কার্ডগুলোর DOM থেকে সরাসরি টাইটেল, লোগো এবং লিংক এক্সট্রাক্ট করা
            extracted_cards = await page.evaluate("""() => {
                let cardsList = [];
                // ফ্যানকোডের লাইভ ইভেন্ট কার্ডগুলো সাধারণত যে কন্টেইনার বা লিঙ্ক ট্যাগে থাকে
                let elements = document.querySelectorAll('a[href*="/match/"], div');
                
                elements.forEach(el => {
                    let text = el.innerText ? el.innerText.trim() : "";
                    // স্ক্রিনশটের মতো কার্ডগুলোতে টুর্নামেন্ট নাম এবং লাইভ ট্যাগ থাকে
                    if (text.includes("LIVE") && text.length > 10 && text.length < 300) {
                        let img = el.querySelector('img');
                        let logo = img ? img.src : "https://images.fancode.com/icons/fancode-logo.png";
                        
                        if (!cardsList.some(c => c.text === text)) {
                            cardsList.push({ text: text, logo: logo });
                        }
                    }
                });
                return cardsList;
            }""")
            
            # যদি সরাসরি DOM থেকে কার্ড পাওয়া যায়, সেগুলোকে প্রসেস করা
            if extracted_cards:
                for card in extracted_cards:
                    # কার্ডের টেক্সট থেকে প্রথম লাইন বা টুর্নামেন্ট নাম আলাদা করা
                    lines_in_card = [l.strip() for l in card['text'].split('\n') if l.strip() and l.strip() != "LIVE"]
                    match_title = " vs ".join(lines_in_card[:3]) if lines_in_card else "FanCode Live Match"
                    
                    # ক্যাটাগরি নির্ধারণ
                    group_title = "Cricket"
                    card_lower = card['text'].lower()
                    if "supercup" in card_lower or "f3" in card_lower or "race" in card_lower or "motorsport" in card_lower:
                        group_title = "Motorsports"
                    elif "t20" in card_lower or "cricket" in card_lower:
                        group_title = "Cricket"
                    
                    # M3U ফরম্যাট যোগ করা
                    m3u_lines.append(f'#EXTINF:-1 tvg-name="{match_title}" tvg-logo="{card["logo"]}" group-title="{group_title}",{match_title}')
                    m3u_lines.append(target_url) # স্ট্রিম বা পেজ লিংক প্লেসহোল্ডার
                    
                    status_messages.append(f"🟢 Added to M3U: {match_title} [{group_title}]")
            else:
                # ফলব্যাক মেথড: টেক্সট লাইন স্ক্যান করে তৈরি করা
                lines = page_text.split('\n')
                for line in lines:
                    line_str = line.strip()
                    line_lower = line_str.lower()
                    if ("league" in line_lower or "supercup" in line_lower or "vs" in line_lower) and len(line_str) > 8:
                        group_title = "Motorsports" if "supercup" in line_lower else "Cricket"
                        m3u_lines.append(f'#EXTINF:-1 tvg-name="{line_str}" tvg-logo="https://images.fancode.com/icons/fancode-logo.png" group-title="{group_title}",{line_str}')
                        m3u_lines.append(target_url)
                        status_messages.append(f"🟢 Added via fallback: {line_str}")
        else:
            no_match_msg = "🔴 Status: No Matches Live At The Moment"
            print(no_match_msg)
            status_messages.append(no_match_msg)

        # M3U ফাইল সেভ করা
        with open(playlist_file, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))
            
        msg4 = f"🟢 Successfully generated and saved {playlist_file}"
        print(msg4)
        status_messages.append(msg4)
        
        await browser.close()
        
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
        print(f"🟢 Status successfully saved to {status_file}")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
