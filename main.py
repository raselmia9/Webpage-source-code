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
        
        # পেজে যাওয়া এবং নেটওয়ার্ক আইডিলে রাখা
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            msg_err = f"🟡 Network idle timeout, proceeding with DOM load: {str(e)}"
            print(msg_err)
            status_messages.append(msg_err)
        
        msg2 = "🟡 Waiting for 100% confirmation of Live Match cards or No Matches message..."
        print(msg2)
        status_messages.append(msg2)
        
        card_loaded_successfully = False

        # ১00% নিশ্চিত হওয়ার জন্য লজিক
        try:
            # প্রথমে দেখবো লাইভ ম্যাচের কোনো কার্ড বা এলিমেন্ট এসেছে কি না (১০ সেকেন্ড ম্যাক্সিমাম ওয়েট)
            match_selector = ".match-card, [class*='match'], [class*='card']"
            await page.wait_for_selector(match_selector, timeout=12000)
            
            # অতিরিক্ত সুনিশ্চিত হওয়ার জন্য চেক করা যে কার্ডের ভেতর রিয়্যাল টেক্সট আছে কি না
            cards_text = await page.locator(match_selector).all_inner_texts()
            
            valid_cards = [c.strip() for c in cards_text if c.strip()]
            
            if valid_cards:
                card_loaded_successfully = True
                msg3 = "🟢 100% CONFIRMED: Live Match card loaded successfully!"
                print(msg3)
                status_messages.append(msg3)
                
                # কার্ডের ভেতরের তথ্যগুলো স্ট্যাটাসে যুক্ত করা যাতে গিটহবে আপডেট টের পাওয়া যায়
                for idx, text in enumerate(valid_cards[:3], 1):
                    clean_text = " | ".join(text.split('\n'))
                    detail_msg = f"🟢 Card Details [{idx}]: {clean_text}"
                    print(detail_msg)
                    status_messages.append(detail_msg)
            else:
                raise Exception("Match elements found but text content is empty.")

        except Exception:
            # যদি লাইভ ম্যাচ কার্ড না পাওয়া যায়, তবে চেক করব "No Matches" লেখাটি আছে কি না
            try:
                await page.wait_for_selector("text=No Matches Live At The Moment", timeout=5000)
                msg3 = "🔴 100% CONFIRMED: 'No Matches Live At The Moment' message is present."
                print(msg3)
                status_messages.append(msg3)
            except Exception:
                msg3 = "🟡 WARNING: Could not 100% verify match cards or no-match text. Page might still be loading."
                print(msg3)
                status_messages.append(msg3)

        # পেজ সম্পূর্ণ স্টেবল হওয়ার জন্য অতিরিক্ত ২ সেকেন্ড অপেক্ষা
        await asyncio.sleep(2)
        
        # রেন্ডার হওয়া সম্পূর্ণ এইচটিএমএল সোর্স কোড সংগ্রহ করা
        html_content = await page.content()
        
        # ফাইল সেভ করা
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        msg4 = f"🟢 Successfully saved fully-rendered HTML to {output_file}"
        print(msg4)
        status_messages.append(msg4)
        
        await browser.close()
        
        # স্ট্যাটাস ফাইল সেভ করা (প্রতিবার যাতে ফাইল আপডেট হয়ে গিটহব পরিবর্তন ট্র্যাক করে)
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
        print(f"🟢 Status successfully saved and forced update to {status_file}")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
