# pip3 install requests beautifulsoup4
import os
import glob
#import shutil
import requests
import hashlib
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
#from duckduckgo_search import DDGS
from ddgs import DDGS
from urllib.parse import urlparse

MAX_QUEUE = 5
#target_url = "https://www.scrapingcourse.com/ecommerce/"

#target_url = "https://planningtank.com/computer-applications/data-processing"

#target_url = "https://quotes.toscrape.com"

#image directory
#os.makedirs("images", exist_ok=True)

#screenshots directory
#os.makedirs("screenshots", exist_ok=True)




#Browser User-Agent : Source =>https://github.com/brave/brave-browser/wiki/User-Agents  

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}













# prompt input
prompt = input("Enter search prompt: ")

#search function
def get_seed_urls(prompt, MAX_QUEUE=5):
    urls = []

    try:
        with DDGS() as ddgs:
            results = ddgs.text(prompt, max_results=MAX_QUEUE)

        for r in results:
            url = r.get("href") or r.get("url") or r.get("link")

            if url:
                urls.append(url)

        return urls

    except Exception as e:
        print("Search failed:", repr(e))
        return []

urls_to_visit = get_seed_urls(prompt)

print("Seed URLs:")
for u in urls_to_visit:
    print("-", u)





downloaded_images = set()


#resetting image dir
files = glob.glob('images/*')
for f in files:
    os.remove(f)

#resetting image dir
files = glob.glob('screenshots/*')
for f in files:
    os.remove(f)

# initialize the list of discovered URLs

print("Seed URLs:", urls_to_visit)
#urls_to_visit = [target_url]
visited_urls = set()

# set a maximum crawl limit


# set content storage
pages = []


# URL Filter

def is_valid_page(url):
    bad_ext = (".jpg", ".png", ".pdf", ".zip", ".mp4", ".mp3")

    path = urlparse(url).path.lower()

    if path.endswith(bad_ext):
        return False

    return True








def crawler():
    # set a crawl counter to track the crawl depth
    crawl_count = 0
    image_urls = []
    
    while urls_to_visit and crawl_count < MAX_QUEUE:
        

        # get the page to visit from the list
        current_url = urls_to_visit.pop()

        # skip if already visited
        if current_url in visited_urls:
            continue

        # mark as visited
        visited_urls.add(current_url)

       

        #Checking URL before request
        if not is_valid_page(current_url):
            continue


        # request the target URL
       # response = requests.get(current_url)
       # response.raise_for_status()
    
    try:
        response = requests.get(current_url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

    except:
        print("Requests failed, switching to Playwright:", current_url)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(current_url, wait_until="domcontentloaded", timeout=15000)
            html = page.content()
            browser.close()

    soup = BeautifulSoup(html, "html.parser")    



   


    soup = BeautifulSoup(response.text, "html.parser")

        #collecting image URL
    images = soup.select("img")

        # collecting title
    if soup.title:
        title = soup.title.string
    else:
        title = "No title"

        # collecting text
    text = soup.get_text(separator=" ", strip=True)

        # store page data
    pages.append({
        "url": current_url,
        "title": title,
        "text": text,
        "images": image_urls
        })


    os.makedirs("images", exist_ok=True)

   













        #taking screenshots with playwright old version


        #with sync_playwright() as p:
            #browser = p.chromium.launch()
            #page = browser.new_page()
            #page.goto(current_url)

            #filename = hashlib.md5(current_url.encode()).hexdigest() + ".png"
            #path = os.path.join("screenshots", filename)
        
            #page.screenshot(path=path,full_page=True)
            #browser.close()

        
    

    for img in images:
        src = img.get("src") or img.get("data-src") or img.get("data-original")

        if not src:
            continue

    # skip base64 images
        if src.startswith("data:"):
            continue

        absolute_img_url = requests.compat.urljoin(current_url, src)

        image_urls.append(absolute_img_url)


    for img_url in image_urls:

        if img_url in downloaded_images:
            continue

        downloaded_images.add(img_url)

        filename = hashlib.md5(img_url.encode()).hexdigest() + ".jpg"
        filepath = os.path.join("images", filename)

        if os.path.exists(filepath):
            continue

        try:
            r = requests.get(img_url, headers=headers, timeout=10)

            if r.status_code != 200:
                print("Blocked or failed:", r.status_code, img_url)
                continue

            content_type = r.headers.get("Content-Type", "")
            if "image" not in content_type:
                print("Not image:", img_url)
                continue

            with open(filepath, "wb") as f:
                f.write(r.content)

            print("Downloaded:", img_url)

        except Exception as e:
            print("Image error:", img_url, e)










        # collect all the links
    link_elements = soup.select("a[href]")

    for link_element in link_elements:
            url = link_element["href"]

            # convert links to absolute URLs
            if not url.startswith("http"):
                absolute_url = requests.compat.urljoin(current_url, url)
            else:
                absolute_url = url

            # ensure same domain + not already seen or queued
            if (
                absolute_url not in urls_to_visit
                and absolute_url not in visited_urls
                and len(urls_to_visit) < MAX_QUEUE
                ):
                urls_to_visit.append(absolute_url)

        # update crawl count (ONE PER PAGE, NOT PER LINK)
        #crawl_count += 1

        # debug output per page :
            # print(f"Crawling: {current_url}")
            # print(f"Pages crawled: {crawl_count}")
            # print(f"Queue size: {len(urls_to_visit)}")
            # print("Visited links:", len(visited_urls))
            # works perfectly fine (20 to crawl and more in Queue :D)
            #print("Images found:", len(image_urls))
            #print(f"Images Links: {image_urls}" )



    #taking screenshots with playwright 
    with sync_playwright() as p:
        browser = p.chromium.launch()

        for current_url in visited_urls:
            page = browser.new_page()
            page.goto(current_url)

            filename = hashlib.md5(current_url.encode()).hexdigest() + ".png"
            path = os.path.join("screenshots", filename)

            page.screenshot(path=path, full_page=True)

            page.close()

        browser.close()



# execute the crawl
crawler()