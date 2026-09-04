import asyncio
from playwright.async_api import async_playwright

async def scrape_webpage():
    # নতুন কাঙ্ক্ষিত লিংক এখানে সেট করা হলো
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    output_file = "index.html"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # মোবাইল ডিভাইসের রিয়েল ফিল এবং বাংলাদেশ সিগন্যাল সহ কনফিগারেশন
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},  # আইফোন সাইজ ভিউপোর্ট
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            
            # রিয়েল মোবাইল ইউজার-এজেন্ট
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            
            # বাংলাদেশ কান্ট্রি সিগন্যাল (লোকাল, টাইমজোন ও জিপিএস লোকেশন)
            locale="bn-BD",
            timezone_id="Asia/Dhaka",
            geolocation={"latitude": 23.8103, "longitude": 90.4125}, # ঢাকা, বাংলাদেশ
            permissions=["geolocation"],
            
            # অতিরিক্ত রিয়েল ইউজার হেডার্স
            extra_http_headers={
                "Accept-Language": "bn-BD,bn;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            }
        )
        
        # বট ডিটেকশন এড়াতে navigator.webdriver প্রপার্টি হাইড করা
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()
        
        print(f"Opening URL as a mobile user from Bangladesh: {target_url}")
        
        # পেজে যাওয়া এবং পুরোপুরি লোড হওয়া পর্যন্ত অপেক্ষা করা
        await page.goto(target_url, wait_until="networkidle")
        
        # পেজ লোড হওয়ার জন্য অতিরিক্ত একটু সময় দেওয়া
        await asyncio.sleep(3)
        
        # সম্পূর্ণ এইচটিএমএল সোর্স কোড সংগ্রহ করা
        html_content = await page.content()
        
        # ফাইল সেভ করা
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        print(f"Successfully saved mobile HTML to {output_file}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
