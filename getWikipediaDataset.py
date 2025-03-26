import os
import requests
import concurrent.futures
from tqdm import tqdm

# Set the folder to store images
my_folder = 'wikipedia_dataset'
os.makedirs(my_folder, exist_ok=True)

# Wikipedia API query string
base_url = 'https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&format=json&piprop=original&titles='

# User-Agent header to comply with Wikipedia policy
headers = {
    'User-Agent': 'YourBot/0.0 (https://yourwebsite.com/yourbot; your@email.com)'
}

# Create a session object for better performance
session = requests.Session()
session.headers.update(headers)

# Function to get the image URL from a Wikipedia page
def get_image_url(partial_url):
    try:
        api_res = session.get(base_url + partial_url).json()
        first_part = api_res['query']['pages']
        for value in first_part.values():
            if 'original' in value:
                return value['original']['source']
    except Exception as exc:
        print(f"Error fetching image for {partial_url}: {exc}")
    return None

# Function to download an image
def download_image(params):
    the_url, filename = params
    try:
        res = session.get(the_url, stream=True)
        res.raise_for_status()
        file_ext = '.' + the_url.split('.')[-1].lower()
        if file_ext not in ['.svg']:
            with open(os.path.join(my_folder, filename + file_ext), 'wb') as image_file:
                for chunk in res.iter_content(1024):
                    image_file.write(chunk)
        return True  # Indicate success
    except Exception as exc:
        print(f"Error downloading {filename}: {exc}")
        return False  # Indicate failure

# Function to get page titles from a category
def get_page_titles(category):
    titles = []
    api_url = f'https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmlimit=max&format=json&cmtitle=Category:{category}'
    while True:
        response = session.get(api_url).json()
        titles.extend(page['title'] for page in response['query']['categorymembers'])
        if 'continue' not in response:
            break
        api_url = f'https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmlimit=max&format=json&cmtitle=Category:{category}&cmcontinue=' + response['continue']['cmcontinue']
    return titles

# Fetch page titles for multiple categories with progress
categories = ['Nature', 'Human_evolution', 'Art']
all_pages = []
with concurrent.futures.ThreadPoolExecutor() as executor:
    results = list(tqdm(executor.map(get_page_titles, categories), total=len(categories), desc="Fetching page titles"))
    for result in results:
        all_pages.extend(result)

# Get image URLs in parallel with progress bar
image_urls = []
with concurrent.futures.ThreadPoolExecutor() as executor:
    for url in tqdm(executor.map(get_image_url, all_pages), total=len(all_pages), desc="Fetching image URLs"):
        if url:
            image_urls.append(url)

# Prepare download tasks
tasks = [(url, str(i)) for i, url in enumerate(image_urls[:5000])]

# Download images in parallel with progress bar
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    list(tqdm(executor.map(download_image, tasks), total=len(tasks), desc="Downloading images"))

print("All done!")

