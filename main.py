import asyncio
from playwright.async_api import async_playwright

async def scrape_webpage():
    # যে পেজটি স্ক্র্যাপ করতে চান তার লিংক এখানে দিন
    target_url = "https://www.fancode.com/bd/live-now/all-sports"
    output_file = "index.html"

    async with async_playwright() as p:
        # ব্রাউজার লঞ্চ করার সময় বাংলাদেশ কেন্দ্রিক কনফিগারেশন দেওয়া
        browser = await p.chromium.launch(headless=True)
        
        # নতুন ব্রাউজার কন্টেক্সট তৈরি যেখানে বাংলাদেশ লোকেল, টাইমজোন এবং লোকেশন সেট করা থাকবে
        context = await browser.new_context(
            locale="bn-BD",
            timezone_id="Asia/Dhaka",
            geolocation={"latitude": 23.8103, "longitude": 90.4125}, # ঢাকা, বাংলাদেশের কোঅর্ডিনেট
            permissions=["geolocation"]
        )
        
        page = await context.new_page()
        
        print(f"Opening URL as a user from Bangladesh: {target_url}")
        # পেজে যাওয়া এবং পুরোপুরি লোড হওয়া পর্যন্ত অপেক্ষা করা
        await page.goto(target_url, wait_until="networkidle")
        
        # সম্পূর্ণ এইচটিএমএল সোর্স কোড সংগ্রহ করা
        html_content = await page.content()
        
        # ফাইল সেভ করা
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        print(f"Successfully saved HTML to {output_file}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_webpage())
