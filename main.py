import asyncio
import random
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    playlist_file = "playlist.m3u"
    status_file = "status.txt"
    
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
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()
        
        msg1 = "🟢 Fresh Device Profile Loaded Successfully"
        print(msg1)
        status_messages.append(msg1)
        
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            msg_err = f"🟡 Network idle timeout, proceeding with DOM: {str(e)}"
            print(msg_err)
            status_messages.append(msg_err)
        
        print("🟡 Waiting for SPA components and live cards to render...")
        await asyncio.sleep(5)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
        await asyncio.sleep(2)
        
        page_text = await page.evaluate("document.body.innerText")
        
        m3u_lines = ["#EXTM3U"]
        
        if "LIVE" in page_text:
            success_msg = "🟢 Status: Live Matches Are Active. Extracting precise match links and team titles..."
            print(success_msg)
            status_messages.append(success_msg)
            
            # ফ্যানকোডের নির্দিষ্ট ওয়াচ পেজ লিংক এবং টিম টাইটেল এক্সট্রাক্ট করার লজিক
            extracted_cards = await page.evaluate("""() => {
                let cardsList = [];
                // ফ্যানকোডের কার্ডগুলোতে থাকা আসল ম্যাচ বা ওয়াচ লিংকগুলো টার্গেট করা
                let matchLinks = document.querySelectorAll('a[href*="/matches/"], a[href*="/match/"]');
                
                matchLinks.forEach(link => {
                    let href = link.href ? link.href : "";
                    let text = link.innerText ? link.innerText.trim() : "";
                    
                    if (href && text && !text.includes("Live Now") && text.length > 5) {
                        let img = link.querySelector('img');
                        let logo = img ? img.src : "https://images.fancode.com/icons/fancode-logo.png";
                        
                        if (!cardsList.some(c => c.href === href)) {
                            let lines = text.split('\\n').map(l => l.trim()).filter(l => l && l !== "LIVE");
                            
                            // টিম টাইটেল বা টুর্নামেন্ট নাম সুন্দরভাবে সাজানো
                            let mainTitle = "FanCode Live Match";
                            if (lines.length >= 2) {
                                // যেমন: প্রথম লাইন টুর্নামেন্ট এবং পরের লাইন টিম বনাম টিম হলে
                                mainTitle = lines[0] + " - " + lines[1];
                            } else if (lines.length == 1) {
                                mainTitle = lines[0];
                            }
                            
                            cardsList.push({ title: mainTitle, href: href, logo: logo, fullText: text });
                        }
                    }
                });
                return cardsList;
            }""")
            
            if extracted_cards:
                for card in extracted_cards:
                    match_title = card['title']
                    match_url = card['href'] # একদম সঠিক ওয়াচ পেজের লিংক
                    
                    group_title = "Cricket"
                    card_lower = card['fullText'].lower()
                    if "supercup" in card_lower or "f3" in card_lower or "race" in card_lower or "motorsport" in card_lower:
                        group_title = "Motorsports"
                    elif "t20" in card_lower or "cricket" in card_lower:
                        group_title = "Cricket"
                    
                    m3u_lines.append(f'#EXTINF:-1 tvg-name="{match_title}" tvg-logo="{card["logo"]}" group-title="{group_title}",{match_title}')
                    m3u_lines.append(match_url)
                    
                    status_messages.append(f"🟢 Added valid watch link: {match_title} [{group_title}]")
            else:
                status_messages.append("🟡 No valid match cards found with /matches/ pattern.")
        else:
            no_match_msg = "🔴 Status: No Matches Live At The Moment"
            print(no_match_msg)
            status_messages.append(no_match_msg)

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
