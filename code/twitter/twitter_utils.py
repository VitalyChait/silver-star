import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class TwitterScraper:
    """
    A class to automate interactions with X.com (formerly Twitter),
    including logging in, querying Grok, and scraping the home feed.

    This class requires Selenium and a compatible WebDriver.
    """

    def __init__(self, credentials_path):
        """
        Initializes the TwitterScraper.

        Args:
            credentials_path (str): The file path to a JSON file containing
                                    'username' and 'password'.
        """
        self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
        self.wait = WebDriverWait(self.driver, 20)
        self.credentials = self._load_credentials(credentials_path)
        self.base_url = "https://x.com"

    def _load_credentials(self, path):
        """Loads credentials from a JSON file."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Credentials file not found at {path}")
            raise
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {path}. Ensure it's a valid JSON file.")
            raise

    def login(self):
        """
        Logs into X.com using the provided credentials.
        Handles the multi-step login process.
        """
        print("Navigating to login page...")
        self.driver.get(f"{self.base_url}/login")

        try:
            # 1. Enter username
            username_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="text"]'))
            )
            username_input.send_keys(self.credentials['username'])
            username_input.send_keys(Keys.RETURN)
            print("Username entered.")
            
            # X.com sometimes has an extra verification step. This is a basic handler.
            # A more robust solution might be needed if it's a common occurrence.
            time.sleep(1.5) # Wait briefly to see if a verification step appears
            
            # 2. Enter password
            password_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
            )
            password_input.send_keys(self.credentials['password'])
            password_input.send_keys(Keys.RETURN)
            print("Password entered.")

            # 3. Wait for home feed to confirm login
            self.wait.until(EC.presence_of_element_located((By.XPATH, "//a[@aria-label='Home']")))
            print("Login successful.")

        except Exception as e:
            print(f"An error occurred during login: {e}")
            self.close()
            raise

    def query_grok(self, query_text):
        """
        Navigates to Grok, runs a query, and returns the result.

        Args:
            query_text (str): The query to send to the Grok LLM.

        Returns:
            str: The text content of Grok's response.
        """
        print(f"Navigating to Grok to query: '{query_text}'")
        self.driver.get(f"{self.base_url}/i/grok")

        try:
            # 1. Find the text area and enter the query
            prompt_textarea = self.wait.until(
                EC.presence_of_element_located((By.XPATH, '//div[@data-testid="dmComposerTextInput"]'))
            )
            prompt_textarea.send_keys(query_text)

            # 2. Find and click the send button
            send_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, '//div[@data-testid="dmComposerSendButton"]'))
            )
            send_button.click()
            print("Query sent to Grok. Awaiting response...")

            # 3. Wait for the response to be generated.
            # We wait for the "regenerate" button to appear, which signals the end of the stream.
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, '//div[@role="button" and contains(.,"Regenerate")]'))
            )
            print("Grok response received.")
            
            # 4. Find all message bubbles and extract the text from the last one
            message_bubbles = self.driver.find_elements(By.XPATH, '//div[@data-testid="conversation-turn-text"]')
            if not message_bubbles:
                return "Could not find a response message from Grok."
            
            grok_response = message_bubbles[-1].text
            return grok_response.strip()

        except Exception as e:
            print(f"An error occurred while querying Grok: {e}")
            return None

    def scrape_home_feed(self, keywords, scroll_limit=3):
        """
        Scrapes the home feed for tweets containing specific keywords.

        Args:
            keywords (list): A list of strings to search for in tweets.
            scroll_limit (int): The number of times to scroll down the page.

        Returns:
            list: A list of tweet texts that contain any of the keywords.
        """
        print(f"Navigating to home feed to search for keywords: {keywords}")
        self.driver.get(f"{self.base_url}/home")
        self.wait.until(EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']")))

        matching_tweets = []
        tweet_texts = set() # Use a set to avoid duplicate tweets

        try:
            for i in range(scroll_limit):
                print(f"Scrolling page... ({i+1}/{scroll_limit})")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3) # Wait for new content to load

                # Find all tweet articles on the page
                tweets = self.driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
                for tweet in tweets:
                    tweet_text = tweet.text
                    # Check if we've already processed this tweet
                    if tweet_text and tweet_text not in tweet_texts:
                        tweet_texts.add(tweet_text)
                        # Check for any of the keywords (case-insensitive)
                        if any(keyword.lower() in tweet_text.lower() for keyword in keywords):
                            matching_tweets.append(tweet_text)
                            print(f"Found matching tweet: {tweet_text[:80]}...")
            
            return matching_tweets

        except Exception as e:
            print(f"An error occurred while scraping the home feed: {e}")
            return matching_tweets # Return what was found so far

    def close(self):
        """Closes the browser."""
        print("Closing the browser.")
        self.driver.quit()


if __name__ == '__main__':
    # --- EXAMPLE USAGE ---
    # 1. Make sure you have a 'credentials.json' file in the same directory.
    #    It should look like this:
    #    {
    #        "username": "your_x_username",
    #        "password": "your_x_password"
    #    }
    # 2. Make sure you have installed the required libraries:
    #    pip install selenium webdriver-manager

    CREDENTIALS_FILE_PATH = 'credentials.json'

    try:
        scraper = TwitterScraper(CREDENTIALS_FILE_PATH)
        scraper.login()

        # --- Task 1: Query Grok ---
        grok_query = "What are the latest trends in renewable energy?"
        grok_result = scraper.query_grok(grok_query)
        print("\n--- Grok Query Result ---")
        if grok_result:
            print(grok_result)
        else:
            print("Failed to get a result from Grok.")

        # --- Task 2: Scrape Home Feed ---
        # Give some time before the next task
        time.sleep(5)
        search_keywords = ["python", "AI", "data science", "FastAPI"]
        feed_results = scraper.scrape_home_feed(keywords=search_keywords, scroll_limit=2)
        print("\n--- Home Feed Scraping Results ---")
        if feed_results:
            for i, tweet in enumerate(feed_results):
                print(f"{i+1}. {tweet}\n")
        else:
            print(f"No tweets found containing the keywords: {search_keywords}")

    except FileNotFoundError:
        print("Stopping script. Please create the credentials.json file.")
    except Exception as e:
        print(f"An unexpected error occurred in the main script: {e}")
    finally:
        if 'scraper' in locals():
            scraper.close()
