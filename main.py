import asyncio
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    output_file = "index.html"
    status_file = "status.txt"
    
    status_messages = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # মোবাইল ডিভাইসের রিয়েল ফিল এবং বাংলাদেশ সিগন্যাল সহ কনফিগারেশন
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
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
        
        msg1 = f"🟡 Opening URL as a mobile user from Bangladesh: {target_url}"
        print(msg1)
        status_messages.append(msg1)
        
        # পেজে যাওয়া
        await page.goto(target_url, wait_until="networkidle")
        
        msg2 = "🟡 Waiting for content (No Matches message or Match cards) to load completely..."
        print(msg2)
        status_messages.append(msg2)
        
        # স্মার্ট ওয়েটিং লজিক ও দলগুলোর নাম এক্সট্রাক্ট করা
        try:
            # প্রথমে চেক করব নো ম্যাচ লেখাটি আছে কি না (খুব কম টাইমে বা শর্ট টাইমআউটে)
            await page.wait_for_selector("text=No Matches Live At The Moment", timeout=3000)
            msg3 = "🔴 Detected: 'No Matches Live At The Moment' message successfully loaded!"
            print(msg3)
            status_messages.append(msg3)
        except Exception:
            try:
                # লাইভ ম্যাচ কার্ড আসার জন্য অপেক্ষা
                await page.wait_for_selector(".match-card, [class*='match'], [class*='card']", timeout=10000)
                msg3 = "🟢 Detected: Live match cards successfully loaded!"
                print(msg3)
                status_messages.append(msg3)
                
                # পেজ থেকে ম্যাচ কার্ডগুলোর ভেতরের দৃশ্যমান টেক্সটগুলো সংগ্রহ করা
                # ফ্যানকোডের কার্ডে টুর্নামেন্ট ও দলগুলোর নাম থাকে
                cards_text = await page.locator(".match-card, [class*='match']").all_inner_texts()
                
                if cards_text:
                    for idx, card in enumerate(cards_text, 1):
                        clean_card = " | ".join([line.strip() for line in card.split('\n') if line.strip()])
                        if clean_card:
                            team_msg = f"🟢 Match Details Found: {clean_card}"
                            print(team_msg)
                            status_messages.append(team_msg)
                else:
                    # যদি সরাসরি কার্ডের ক্লাস না ধরে পুরো বডি থেকে নির্দিষ্ট লেখা খুঁজতে হয়
                    fallback_text = "🟢 Live match container is active on the page."
                    print(fallback_text)
                    status_messages.append(fallback_text)
                
            except Exception:
                msg3 = "🟡 Timeout reached for specific elements, proceeding with current DOM state."
                print(msg3)
                status_messages.append(msg3)

        # পেজ সম্পূর্ণ স্টেবল হওয়ার জন্য অতিরিক্ত ১ সেকেন্ড অপেক্ষা
        await asyncio.sleep(1)
        
        # রেন্ডার হওয়া সম্পূর্ণ এইচটিএমএল সোর্স কোড সংগ্রহ করা
        html_content = await page.content()
        
        # ফাইল সেভ করা
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        msg4 = f"🟢 Successfully saved fully-rendered HTML to {output_file}"
        print(msg4)
        status_messages.append(msg4)
        
        await browser.close()
        
        # স্ট্যাটাস ফাইল সেভ করা (কোনো তারিখ বা সময় ছাড়াই)
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
        print(f"🟢 Status successfully saved to {status_file}")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
