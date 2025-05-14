from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig
from dotenv import load_dotenv
import asyncio
import json
import os
from datetime import datetime

# Load environment variables from .env
load_dotenv()

# Get OpenAI API key from environment
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Define the storage path for interactions
STORAGE_DIR = "interactions"
STORAGE_FILE = os.path.join(STORAGE_DIR, "hmm_tracking_interactions.json")

# Ensure storage directory exists
os.makedirs(STORAGE_DIR, exist_ok=True)

async def track_shipping(booking_id, use_stored=True, headless=False):
    """
    Track a shipping container from HMM through seacargotracking.net
    
    Args:
        booking_id: The booking ID to track
        use_stored: Whether to use stored interactions if available
        headless: Whether to run browser in headless mode
    
    Returns:
        Dictionary containing tracking information
    """
    # Initialize LLM with recommended settings
    llm = ChatOpenAI(
        model="gpt-4o-mini",  # Best performance according to docs
        temperature=0.0,  # Lower temperature for consistent results
        api_key=openai_api_key,  # Explicitly set API key
    )
    
    # Define the task with clear instructions
    task = f"""
        Track HMM shipping container with booking ID '{booking_id}':
    
        1. Go to http://www.seacargotracking.net/ 
        2. Look for HMM (Hyundai Merchant Marine) or similar options
        3. Try different tracking methods if available:
        - Input booking ID in search or B/L No. field 
        - Click on Search button 
        - Try alternate tracking sites like www.hmm21.com if available
        - If any site blocks automation, try to bypass restrictions by:
         - Waiting for a few seconds between actions
         - Using different input methods or form fields
         - Checking for CAPTCHA and describing what you see
        5. Extract voyage number and arrival date from results
    
    Return JSON with:
    {{
        "booking_id": "{booking_id}",
        "voyage_number": "extracted voyage number or 'Not available'",
        "arrival_date": "extracted arrival date or 'Not available'",
        "notes": "Include any issues encountered with website restrictions"
    }}
    """
    
    # Check if we have stored interactions and should use them
    stored_interactions = None
    if use_stored and os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r') as f:
                stored_interactions = json.load(f)
            print(f"Using stored interactions from {STORAGE_FILE}")
        except Exception as e:
            print(f"Error loading stored interactions: {e}")
            stored_interactions = None
    
    # Configure browser options
    browser_config = BrowserConfig(
        # viewport_size={"width": 1280, "height": 720},  # Set larger viewport for better visibility
        # headless=headless,  # Control headless mode through parameter
          browser_binary_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' 
    )
    
    browser = Browser(config=browser_config)
    
    # Create the agent with optimized settings
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )
    
    # Run the agent
    try:
        result = await agent.run()
        
        # Store the interactions for future use if we don't already have them
        if not stored_interactions and agent.browser_steps:
            try:
                interactions = {
                    "created_at": datetime.now().isoformat(),
                    "booking_id": booking_id,
                    "steps": agent.browser_steps
                }
                with open(STORAGE_FILE, 'w') as f:
                    json.dump(interactions, f, indent=2)
                print(f"Stored interactions to {STORAGE_FILE}")
            except Exception as e:
                print(f"Error storing interactions: {e}")
        
        return result
    finally:
        # Ensure the browser is closed properly
        await browser.close()

async def main():
    # Example booking ID from the assignment
    booking_id = "SINI25432400"
    
    # Get command line arguments if provided
    import sys
    if len(sys.argv) > 1:
        booking_id = sys.argv[1]
    
    # Check if headless mode is specified
    headless = "--headless" in sys.argv
    
    print(f"Tracking booking ID: {booking_id}")
    print(f"Headless mode: {'enabled' if headless else 'disabled'}")
    
    result = await track_shipping(booking_id, headless=headless)
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())




