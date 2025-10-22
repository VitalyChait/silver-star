import unittest
import json
from unittest.mock import patch, MagicMock, mock_open
from twitter_utils import TwitterScraper

class TestTwitterScraper(unittest.TestCase):
    """
    Unit tests for the TwitterScraper class.

    These tests use mocking to isolate the class from external dependencies
    like the filesystem and the Selenium WebDriver.
    """

    # 1. Test Initialization and Credential Loading
    @patch("builtins.open", new_callable=mock_open, read_data='{"username": "testuser", "password": "testpassword"}')
    @patch("twitter_utils.webdriver.Chrome")
    def test_init_and_load_credentials_success(self, mock_chrome, mock_file):
        """Test successful initialization and credential loading."""
        scraper = TwitterScraper("dummy/path.json")
        self.assertEqual(scraper.credentials['username'], 'testuser')
        self.assertEqual(scraper.credentials['password'], 'testpassword')
        mock_file.assert_called_with("dummy/path.json", 'r')
        mock_chrome.assert_called_once()

    @patch("builtins.open", side_effect=FileNotFoundError)
    @patch("twitter_utils.webdriver.Chrome")
    def test_load_credentials_file_not_found(self, mock_chrome, mock_file):
        """Test that FileNotFoundError is raised if credentials file is missing."""
        with self.assertRaises(FileNotFoundError):
            TwitterScraper("nonexistent/path.json")

    @patch("builtins.open", new_callable=mock_open, read_data='{"username": "testuser",}')
    @patch("twitter_utils.webdriver.Chrome")
    def test_load_credentials_json_error(self, mock_chrome, mock_file):
        """Test that JSONDecodeError is raised for invalid JSON."""
        with self.assertRaises(json.JSONDecodeError):
            TwitterScraper("invalid/json.json")

    # 2. Test Core Functionality
    def setUp(self):
        """Set up a scraper instance with a mocked driver for each test."""
        # Mock the entire webdriver module used by the class
        self.patcher = patch('twitter_utils.webdriver.Chrome')
        self.mock_chrome = self.patcher.start()
        self.mock_driver = MagicMock()
        self.mock_chrome.return_value = self.mock_driver

        # Mock credential loading to avoid filesystem dependency in these tests
        with patch("builtins.open", mock_open(read_data='{"username": "testuser", "password": "testpassword"}')):
            self.scraper = TwitterScraper("dummy/path.json")
            # The wait object should also use the mock driver
            self.scraper.wait = MagicMock()

    def tearDown(self):
        """Stop the patcher after each test."""
        self.patcher.stop()

    def test_login_success(self):
        """Test the sequence of actions for a successful login."""
        # Setup mock elements
        mock_username_input = MagicMock()
        mock_password_input = MagicMock()
        mock_home_link = MagicMock()

        # Configure the wait object to return the mock elements in sequence
        self.scraper.wait.until.side_effect = [
            mock_username_input,
            mock_password_input,
            mock_home_link
        ]
        
        self.scraper.login()

        # Assertions
        self.mock_driver.get.assert_called_with("https://x.com/login")
        
        # Check username interaction
        mock_username_input.send_keys.assert_any_call("testuser")
        mock_username_input.send_keys.assert_any_call(self.scraper.driver.common.keys.Keys.RETURN)
        
        # Check password interaction
        mock_password_input.send_keys.assert_any_call("testpassword")
        mock_password_input.send_keys.assert_any_call(self.scraper.driver.common.keys.Keys.RETURN)

        # Check that we waited for the home link to appear, confirming login
        self.assertEqual(self.scraper.wait.until.call_count, 3)

    def test_query_grok_success(self):
        """Test a successful Grok query and response retrieval."""
        # Setup mock elements
        mock_textarea = MagicMock()
        mock_send_button = MagicMock()
        mock_regenerate_button = MagicMock()
        
        mock_response_bubble = MagicMock()
        mock_response_bubble.text = "  This is the Grok response.  "
        
        self.scraper.wait.until.side_effect = [
            mock_textarea,
            mock_send_button,
            mock_regenerate_button
        ]
        self.mock_driver.find_elements.return_value = [MagicMock(), mock_response_bubble]

        result = self.scraper.query_grok("Test query")
        
        # Assertions
        self.mock_driver.get.assert_called_with("https://x.com/i/grok")
        mock_textarea.send_keys.assert_called_with("Test query")
        mock_send_button.click.assert_called_once()
        self.assertEqual(self.scraper.wait.until.call_count, 3)
        self.mock_driver.find_elements.assert_called_once()
        self.assertEqual(result, "This is the Grok response.")

    def test_scrape_home_feed_success(self):
        """Test successful scraping of home feed with keyword matching."""
        # Setup mock tweet elements
        mock_tweet1 = MagicMock()
        mock_tweet1.text = "This is a tweet about Python and AI."
        mock_tweet2 = MagicMock()
        mock_tweet2.text = "Another post about something unrelated."
        mock_tweet3 = MagicMock()
        mock_tweet3.text = "Let's talk about data science."

        # Configure driver to return these mock tweets
        self.mock_driver.find_elements.return_value = [mock_tweet1, mock_tweet2, mock_tweet3]

        keywords = ["python", "data science"]
        results = self.scraper.scrape_home_feed(keywords=keywords, scroll_limit=1)

        # Assertions
        self.mock_driver.get.assert_called_with("https://x.com/home")
        self.mock_driver.execute_script.assert_called_with("window.scrollTo(0, document.body.scrollHeight);")
        self.assertEqual(len(results), 2)
        self.assertIn("This is a tweet about Python and AI.", results)
        self.assertIn("Let's talk about data science.", results)
        self.assertNotIn("Another post about something unrelated.", results)

    def test_close(self):
        """Test that the driver's quit method is called."""
        self.scraper.close()
        self.mock_driver.quit.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
