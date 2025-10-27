from scrapingbee import ScrapingBeeClient
import json
from bs4 import BeautifulSoup
import os

client = ScrapingBeeClient(api_key=os.environ["SCRAPING_BEE_API_KEY"])

url = 'https://boston.craigslist.org/search/jjj?query=remote#search=2~gallery~0'

# Make the request
response = client.get(url)

# Check if the request was successful
if response.status_code == 200:
    print('Request successful!')
    html_content = response.content
else:
    print(f'Request failed with status code: {response.status_code}')


soup = BeautifulSoup(html_content, 'html.parser')


listings = soup.select('.cl-static-search-result')
# Extract data from each listing
extracted_data = []
for listing in listings:
    # Find the <a> tag first
    a_tag = listing.find('a')

    # Extract link
    link = a_tag['href'] if a_tag and 'href' in a_tag.attrs else ''

    # Extract title
    title_element = a_tag.select_one('.title') if a_tag else None
    title = title_element.text.strip() if title_element else 'No title'

    # Store the extracted data
    extracted_data.append({
        'title': title,
        'link': link
    })
# Print the first few results
for i, data in enumerate(extracted_data[:3]):
    print(f"Listing {i+1}:")
    print(f"Title: {data['title']}")
    print(f"Link: {data['link']}")
    print("---")
