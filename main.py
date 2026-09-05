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
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            msg_err = f"🟡 Network idle timeout, proceeding with DOM load: {str(e)}"
            print(msg_err)
            status_messages.append(msg_err)
        
        # পেজের ডাইনামিক কন্টেন্ট ও লাইভ ব্যাজ পুরোপুরি লোড হওয়ার জন্য অতিরিক্ত সময় ও স্ক্রোলিং
        print("🟡 Waiting for live elements to render...")
        await asyncio.sleep(3)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight/2);")
        await asyncio.sleep(2)
        
        msg2 = "🟡 Checking for live match cards across all categories..."
        print(msg2)
        status_messages.append(msg2)
        
        card_loaded_successfully = False

        try:
            # ফ্যানকোডের লাইভ ব্যাজ (LIVE লেখাটি) অথবা কার্ডের কমন কন্টেইনার দিয়ে চেক করা
            live_badge_selector = "text=LIVE"
            await page.wait_for_selector(live_badge_selector, timeout=15000)
            
            # পেজে থাকা সমস্ত লাইভ ইভেন্ট বা কার্ডের টেক্সটগুলো সংগ্রহ করা
            # যেহেতু একাধিক ক্যাটাগরি থাকতে পারে (যেমন ক্রিকেট ও মোটোরস্পোর্টস)
            all_cards_text = await page.locator("div, span, a").all_inner_texts()
            
            # যেগুলোতে লাইভ বা টুর্নামেন্টের নাম আছে সেগুলো ফিল্টার করা
            found_live_items = [t.strip() for t in all_cards_text if "LIVE" in t or "League" in t or "Race" in t]
            
            if found_live_items:
                card_loaded_successfully = True
                msg3 = "🟢 100% CONFIRMED: Live match cards/events loaded successfully!"
                print(msg3)
                status_messages.append(msg3)
                
                # পাওয়া কিছু লাইভ ইভেন্টের নাম স্ট্যাটাসে যুক্ত করা
                for idx, item in enumerate(found_live_items[:4], 1):
                    clean_item = " | ".join([line.strip() for line in item.split('\n') if line.strip()])
                    if len(clean_item) > 3:
                        detail_msg = f"🟢 Live Event [{idx}]: {clean_item[:60]}"
                        print(detail_msg)
                        status_messages.append(detail_msg)
            else:
                raise Exception("Live badge found but text extraction failed.")

        except Exception:
            # যদি লাইভ ম্যাচ না থাকে তবে নো ম্যাচ চেক করা
            try:
                await page.wait_for_selector("text=No Matches Live At The Moment", timeout=3000)
                msg3 = "🔴 100% CONFIRMED: 'No Matches Live At The Moment' message is present."
                print(msg3)
                status_messages.append(msg3)
            except Exception:
                msg3 = "🔴 WARNING: Live elements could not be verified properly."
                print(msg3)
                status_messages.append(msg3)

        # সম্পূর্ণ HTML সংগ্রহ করা
        html_content = await page.content()
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        msg4 = f"🟢 Successfully saved fully-rendered HTML to {output_file}"
        print(msg4)
        status_messages.append(msg4)
        
        await browser.close()
        
        # স্ট্যাটাস ফাইল সেভ করা
        with open(status_file, "w", encoding="utf-8") as sf:
            sf.write("\n".join(status_messages))
        print(f"🟢 Status successfully saved to {status_file}")

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
