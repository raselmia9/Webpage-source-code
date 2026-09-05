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
            msg_err = f"🟡 Network idle timeout, proceeding: {str(e)}"
            print(msg_err)
            status_messages.append(msg_err)
        
        # জাভাস্ক্রিপ্ট ও রিয়্যাক্ট কম্পোনেন্ট পুরোপুরি লোড হওয়ার জন্য সময় ও স্ক্রোলিং
        print("🟡 Waiting for SPA components and live data to render...")
        await asyncio.sleep(4)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
        await asyncio.sleep(2)
        
        msg2 = "🟡 Scanning page text for active live matches..."
        print(msg2)
        status_messages.append(msg2)
        
        # পেজের সম্পূর্ণ দৃশ্যমান টেক্সট সংগ্রহ করা
        page_text = await page.evaluate("document.body.innerText")
        
        # কাঙ্ক্ষিত লাইভ ম্যাচ বা কীওয়ার্ড চেক করা (যেমন Dehradun, Monza, League, Race বা LIVE)
        keywords_to_check = ["Dehradun", "Monza", "League", "Sprint Race", "LIVE"]
        found_keywords = [kw for kw in keywords_to_check if kw.lower() in page_text.lower()]
        
        if "LIVE" in page_text and (len(found_keywords) > 1):
            success_msg = "🟢 100% CONFIRMED: Live match cards loaded successfully!"
            print(success_msg)
            status_messages.append(success_msg)
            
            # পেজ থেকে নির্দিষ্ট ম্যাচ বা টুর্নামেন্টের লাইনগুলো ফিল্টার করে বের করা
            lines = page_text.split('\n')
            for line in lines:
                line_str = line.strip()
                # যে লাইনগুলোতে ম্যাচের নাম বা টুর্নামেন্টের ক্লু আছে সেগুলো স্ট্যাটাসে তুলব
                if any(k.lower() in line_str.lower() for k in ["Dehradun", "Monza", "League", "Sprint", "Knight", "Thunder"]):
                    if len(line_str) > 3:
                        detail_msg = f"🟢 Live Match Found: {line_str}"
                        print(detail_msg)
                        status_messages.append(detail_msg)
        else:
            # যদি লাইভ ম্যাচ না থাকে তবে নো ম্যাচ চেক করা
            if "No Matches Live At The Moment" in page_text:
                no_match_msg = "🔴 100% CONFIRMED: 'No Matches Live At The Moment' message is present."
                print(no_match_msg)
                status_messages.append(no_match_msg)
            else:
                warning_msg = "🟡 WARNING: Live elements could not be verified completely."
                print(warning_msg)
                status_messages.append(warning_msg)

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
