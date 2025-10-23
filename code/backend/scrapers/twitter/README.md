Silver Star - X.com Automation Utilities

This project provides a collection of Python utilities for automating interactions with X.com (formerly Twitter). It uses Selenium to control a web browser, allowing it to perform tasks such as logging in, querying the Grok AI, and scraping the home feed for specific keywords.

The primary goal is to create a reusable and testable module that can be integrated into larger automated workflows or AI agent systems.

Files

1. twitter_utils.py

This is the main, reusable module. It contains the TwitterScraper class, which encapsulates all the logic for interacting with X.com.

Core Features:

Login: Automates the multi-step login process.

Query Grok: Navigates to the Grok interface, submits a query, and waits for and collects the full response.

Scrape Home Feed: Navigates to the home feed, scrolls a specified number of times, and collects tweets that contain user-defined keywords.

It is designed to be imported into other scripts. An example usage block is included under the if __name__ == '__main__': section to demonstrate its functionality.

2. test_twitter_utils.py

This file contains unit tests for the TwitterScraper class. It uses Python's unittest framework and the unittest.mock library to test the class's methods in isolation.

Testing Strategy:

Isolation: The tests mock external dependencies like the Selenium WebDriver and filesystem access. This means the tests can run without opening a browser, connecting to the internet, or requiring a real credentials.json file.

Speed & Reliability: Mocking ensures the tests are fast and produce consistent results, making them suitable for automated testing pipelines.

Coverage: The tests cover successful operations, file I/O errors (like a missing credentials file), and core logic for each public method.

Setup and Installation

Prerequisites

Python 3.7+

Google Chrome browser installed on your system.

1. Install Required Packages

The project relies on selenium for browser automation and webdriver-manager to automatically handle the Chrome driver. Install these packages using pip:

pip install selenium webdriver-manager


2. Create Credentials File

For the script to log into X.com, you must create a credentials.json file in the same directory as twitter_utils.py. The file must contain your username and password in the following format:

{
    "username": "your_x_username_or_email",
    "password": "your_x_password"
}


Note: This file is included in the .gitignore of most projects to prevent accidentally committing sensitive credentials to version control.

How to Run

Running the Main Script (Demonstration)

To run the example demonstration in twitter_utils.py, which logs in, queries Grok, and scrapes the feed, execute the following command from your terminal:

python twitter_utils.py


Running the Unit Tests

To verify that the TwitterScraper class is functioning correctly according to its tests, run the test_twitter_utils.py file:

python test_twitter_utils.py


You should see an output indicating that all tests passed successfully.

Troubleshooting

Error: cannot find Chrome binary

This is the most common error and means that Selenium was unable to find the Google Chrome browser application on your system.

Solution:

Install Google Chrome: Make sure you have the official Google Chrome browser installed, not just Chromium. You can download it from the official Google Chrome website.

For Linux Users: If you are on a Debian-based Linux distribution (like Ubuntu), you can install it via the terminal:

wget [https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb](https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb)
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f 
