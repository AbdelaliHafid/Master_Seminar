# pip3 install requests beautifulsoup4
import os
import glob
#import shutil
import requests
import hashlib
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


target_url = "https://www.scrapingcourse.com/ecommerce/"

#target_url = "https://planningtank.com/computer-applications/data-processing"

#target_url = "https://quotes.toscrape.com"

#image directory
#os.makedirs("images", exist_ok=True)

#screenshots directory
#os.makedirs("screenshots", exist_ok=True)

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
urls_to_visit = [target_url]
visited_urls = set()

# set a maximum crawl limit
max_crawl = 5

# set content storage
pages = []



def crawler():
    # set a crawl counter to track the crawl depth
    crawl_count = 0

    while urls_to_visit and crawl_count < max_crawl:
        

        # get the page to visit from the list
        current_url = urls_to_visit.pop()

        # skip if already visited
        if current_url in visited_urls:
            continue

        # mark as visited
        visited_urls.add(current_url)

        # set image storage
        image_urls = []



        # request the target URL
        response = requests.get(current_url)
        response.raise_for_status()

        # parse the HTML
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

        # storing Images's Links
        for img in images:
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if not src:
                continue

        

        # images absolute Urls 
        
        
            if not src.startswith("http"):
                absolute_img_url = requests.compat.urljoin(current_url, src)
            else:
                absolute_img_url = src
        

            image_urls.append(absolute_img_url)
        
            if absolute_img_url in downloaded_images:
                continue
            downloaded_images.add(absolute_img_url)








        #Downloading Image from Url
        # and checking if the image link is a duplicate with md5 and encode
            try:
                image_response = requests.get(absolute_img_url, timeout=10)

                if image_response.status_code == 200:
                    #filename = absolute_img_url.split("/")[-1]
                    filename = (hashlib.md5(absolute_img_url.encode()).hexdigest()+ ".jpg")
                 
                    filepath = os.path.join("images",filename)

                    if os.path.exists(filepath):
                        print(f"Image already exists:{filename}")
                    else:
                        with open(filepath,"wb") as f:
                            f.write(image_response.content)
                    
                        print(f"Downloaded: {filename}")

             

            except Exception as e:
                print("Image download failed:", e)




        #taking screenshots with playwright old version


        #with sync_playwright() as p:
            #browser = p.chromium.launch()
            #page = browser.new_page()
            #page.goto(current_url)

            #filename = hashlib.md5(current_url.encode()).hexdigest() + ".png"
            #path = os.path.join("screenshots", filename)
        
            #page.screenshot(path=path,full_page=True)
            #browser.close()

        







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
                absolute_url.startswith(target_url)
                and absolute_url not in urls_to_visit
                and absolute_url not in visited_urls
            ):
                if len(urls_to_visit) < max_crawl:
                    urls_to_visit.append(absolute_url)

        # update crawl count (ONE PER PAGE, NOT PER LINK)
        crawl_count += 1

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