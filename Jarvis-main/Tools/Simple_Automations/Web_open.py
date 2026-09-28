import sys
import os

# Add parent directory to path so we can import DATA module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import webbrowser
from DATA.web_data import websites


def open_web(web_name):
    """
    Opens websites based on user input.
    Can open multiple websites if multiple keywords are found.
    
    Args:
        web_name: Text input containing website names
    """
    # Convert input to lowercase and split into individual words
    website_name = web_name.lower().split()
    
    # Dictionary to count occurrences of each website keyword
    count = {}
    
    # Count how many times each word appears in the input
    for name in website_name:
        count[name] = count.get(name, 0) + 1
    
    # List to store URLs to open
    urls = []
    
    # Check if any word matches a website in our dictionary
    for name, cnt in count.items():
        if name in websites:
            # Add the URL to our list, multiplied by count
            urls.extend([websites[name]] * cnt)
    
    # Open all the URLs
    for url in urls:
        webbrowser.open(url)

    if urls:
        print("Opening websites...")
    else:
        print("No matching websites found.")    


# Main execution loop
if __name__ == "__main__":
    while True:
        web_input = input("Website name: ")
        open_web(web_input)