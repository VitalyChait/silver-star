import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
from twitter_utils import TwitterScraper
from selenium.webdriver.common.keys import Keys

class TestTwitterScraper(unittest.TestCase):
    """Unit tests for the TwitterScraper class."""

    def setUp(self):
        """Set up a mock driver and scraper instance before each test."""
        # Mock the entire selenium webdriver
        self.patcher = patch('twitter_utils.webdriver.Chrome')
        self.mock_chrome = self.patcher.start()
        self.mock_driver = self.mock_chrome.return_value
        
        # Create a valid credentials structure for tests
        self.credentials = {"username": "testuser", "password": "testpassword"}
        
        # Patch 'builtins.open' to mock file reading for credentials
        # The mock will apply to the instantiation of TwitterScraper
        self.mock_file = mock_open(read_data=json.dumps(self.credentials))
        with patch('builtins.open', self.mock_file):
            self.scraper = TwitterScraper(credentials_path='credentials.json')

    def tearDown(self):
        """Stop the patcher after each test."""
        self.patcher.stop()

    def test_init_and_load_credentials_success(self):
        """Test successful initialization and credential loading."""
        self.mock_file.assert_called_once_with('credentials.json', 'r')
        self.assertEqual(self.scraper.username, "testuser")
        self.assertEqual(self.scraper.password, "testpassword")
        self.assertIsNotNone(self.scraper.driver)
    
    def test_load_credentials_file_not_found(self):
        """Test that FileNotFoundError is raised if credentials file is missing."""
        mock_file = mock_open()
        mock_file.side_effect = FileNotFoundError
        with patch('builtins.open', mock_file):
            with self.assertRaises(FileNotFoundError):
                TwitterScraper(credentials_path='nonexistent.json')

    def test_load_credentials_json_error(self):
        """Test that JSONDecodeError is raised for invalid JSON."""
        # Re-patch open with invalid JSON data for this specific test
        m = mock_open(read_data="invalid json")
        with patch('builtins.open', m):
            with self.assertRaises(json.JSONDecodeError):
                TwitterScraper(credentials_path='credentials.json')

    def test_login_success(self):
        """Test the sequence of actions for a successful login."""
        # Mocks for each element that will be found
        mock_username_input = MagicMock()
        mock_next_button = MagicMock()
        mock_password_input = MagicMock()
        mock_login_button = MagicMock()

        # Configure find_element to return the correct mock element based on the selector
        def find_element_side_effect(by, value):
            if value == 'input[name="text"]':
                return mock_username_input
            elif "//span[contains(text(), 'Next')]" in value:
                return mock_next_button
            elif value == 'input[name="password"]':
                return mock_password_input
            elif "//span[contains(text(), 'Log in')]" in value:
                return mock_login_button
            return MagicMock()

        self.scraper.driver.find_element.side_effect = find_element_side_effect

        # --- Call the method to be tested ---
        self.scraper.login()

        # --- Assertions ---
        # 1. Check navigation
        self.scraper.driver.get.assert_called_with("https://x.com/login")
        
        # 2. Check username input
        mock_username_input.send_keys.assert_called_with("testuser")
        
        # 3. Check that the "Next" button was clicked
        mock_next_button.click.assert_called_once()
        
        # 4. Check password input
        mock_password_input.send_keys.assert_called_with("testpassword")
        
        # 5. Check that the "Log in" button was clicked
        mock_login_button.click.assert_called_once()

    @patch('twitter_utils.time.sleep', return_value=None)
    def test_query_grok_success(self, mock_sleep):
        """Test a successful Grok query and response retrieval."""
        mock_grok_input = MagicMock()
        mock_grok_response = MagicMock()
        mock_grok_response.text = "Grok's final answer."

        def find_element_side_effect(by, value):
            if by == "css selector" and "br > span" in value:
                return mock_grok_input
            elif by == "xpath" and "GPT-3" in value: # Using a known part of the response selector
                return mock_grok_response
            return MagicMock()

        self.scraper.driver.find_element.side_effect = find_element_side_effect

        query = "Test query"
        result = self.scraper.query_grok(query)

        self.scraper.driver.get.assert_called_with("https://x.com/i/grok")
        mock_grok_input.send_keys.assert_any_call(query)
        mock_grok_input.send_keys.assert_any_call(Keys.RETURN)
        self.assertEqual(result, "Grok's final answer.")

    @patch('twitter_utils.time.sleep', return_value=None)
    def test_scrape_home_feed_success(self, mock_sleep):
        """Test successful scraping of home feed with keyword matching."""
        mock_tweet1 = MagicMock()
        mock_tweet1.text = "This is a tweet about Python and AI."
        mock_tweet2 = MagicMock()
        mock_tweet2.text = "Another tweet without keywords."
        mock_tweet3 = MagicMock()
        mock_tweet3.text = "Let's talk about data science."
        
        self.scraper.driver.find_elements.return_value = [mock_tweet1, mock_tweet2, mock_tweet3]
        
        keywords = ["python", "data science"]
        results = self.scraper.scrape_home_feed(keywords, scrolls=1)

        self.scraper.driver.get.assert_called_with("https://x.com/home")
        self.scraper.driver.execute_script.assert_called_with("window.scrollTo(0, document.body.scrollHeight);")
        self.assertEqual(len(results), 2)
        self.assertIn(mock_tweet1.text, results)
        self.assertIn(mock_tweet3.text, results)
        
    def test_close(self):
        """Test that the driver's quit method is called."""
        self.scraper.close()
        self.scraper.driver.quit.assert_called_once()

if __name__ == '__main__':
    unittest.main()

