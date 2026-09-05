import asyncio
import random
from playwright.async_api import async_playwright

async def scrape_webpage():
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    output_file = "index.html"
    status_file = "status.txt"
    
    status_messages = []

    # বিভিন্ন রিয়েল মোবাইল ডিভাইসের ইউজার এজেন্ট এবং স্ক্রিন সাইজের লিস্ট (প্রতিবার নতুন ডিভাইস পরিচয়ের জন্য)
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
        
        # ফ্রেশ র‍্যান্ডম ডিভাইস কনটেক্সট তৈরি
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
        print("🟡 Waiting for SPA components to render...")
        await asyncio.sleep(4)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
        await asyncio.sleep(2)
        
        # পেজের সম্পূর্ণ টেক্সট সংগ্রহ করা
        page_text = await page.evaluate("document.body.innerText")
        
        # সার্বজনীন লাইভ স্ট্যাটাস চেক করা (মেনুর জাংক শব্দ এড়ানোর জন্য ফিল্টার)
        if "LIVE" in page_text:
            # পেজে লাইভ ম্যাচ আছে কি না তার একটি ইউনিভার্সাল পজিটিভ স্ট্যাটাস
            success_msg = "🟢 Status: Live Matches Are Currently Active on FanCode"
            print(success_msg)
            status_messages.append(success_msg)
        else:
            if "No Matches Live At The Moment" in page_text:
                no_match_msg = "🔴 Status: No Matches Live At The Moment"
                print(no_match_msg)
                status_messages.append(no_match_msg)
            else:
                warning_msg = "🟡 Status: Checking live elements..."
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
