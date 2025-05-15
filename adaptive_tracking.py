from langchain_google_genai import ChatGoogleGenerativeAI  
from browser_use import Agent, Browser, BrowserConfig
from dotenv import load_dotenv
import asyncio
import json
import os
import sys

# Load environment variables from .env
load_dotenv()

# Get OpenAI API key from environment
google_api_key = os.getenv("GOOGLE_API_KEY") 
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")

# Define the storage path for interactions
STORAGE_DIR = "interactions"
STORAGE_FILE = os.path.join(STORAGE_DIR, "hmm_tracking_interactions.json")

async def adaptive_tracking(booking_id, headless=False):
    """
    Use stored interactions to track a shipping container with minimal AI intervention
    
    Args:
        booking_id: The booking ID to track
        headless: Whether to run browser in headless mode
    
    Returns:
        Dictionary containing tracking information
    """
    # Initialize LLM with recommended settings
    llm = ChatGoogleGenerativeAI(  
        model='gemini-2.0-flash-exp',
        temperature=0.0,
        google_api_key=google_api_key
    )
    
    # Check if stored interactions exist
    if not os.path.exists(STORAGE_FILE):
        print("No stored interactions found. Running full tracking.")
        from main import track_shipping
        return await track_shipping(booking_id, headless=headless)
    
    # Load stored interactions
    try:
        with open(STORAGE_FILE, 'r') as f:
            stored = json.load(f)
        print(f"Using stored interactions from {STORAGE_FILE}")
    except Exception as e:
        print(f"Error loading stored interactions: {e}")
        print("Falling back to full tracking.")
        from main import track_shipping
        return await track_shipping(booking_id, headless=headless)
    
    # Define task that uses the stored interactions as guidance
    task = f"""
    Using the previous successful interactions with seacargotracking.net, retrieve the voyage number and arrival date for HMM booking ID '{booking_id}':
    
    1. Go to http://www.seacargotracking.net/ 
    2. Look for HMM (Hyundai Merchant Marine) or similar options
    3. Search for Track & Trace and click on it:
        - Input booking ID in search or B/L No. field 
        - Click on Search button 
    4. Scrape the full page content and extract:
        - Voyage number from vessel name format (XXXXX XXXW)
        - Arrival date with time from ETB (Estimated Time of Berthing)
    
    Return ONLY a JSON object with fields 'booking_id', 'voyage_number', and 'arrival_date'.
    If any information cannot be found, set the value to "Not available".
    
    Note: If the website structure has changed, adapt your approach accordingly.
    """
    
    # Configure browser with optimal settings
    browser_config = BrowserConfig(
        browser_binary_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' 
    )
    
    browser = Browser(config=browser_config)
    
    # Create the agent with optimization enabled
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )
    
    # Run the agent
    try:
        result = await agent.run()
        return result
    finally:
        # Ensure browser is properly closed
        await browser.close()

async def main():
    # Get booking ID from command line
    if len(sys.argv) > 1:
        booking_id = sys.argv[1]
    else:
        booking_id = "SINI25432400"  # Default example
    
    # Check if headless mode is specified
    headless = "--headless" in sys.argv
    
    print(f"Adaptively tracking booking ID: {booking_id}")
    print(f"Headless mode: {'enabled' if headless else 'disabled'}")
    
    result = await adaptive_tracking(booking_id, headless=headless)
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    asyncio.run(main()) 


