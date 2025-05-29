import warnings
warnings.filterwarnings("ignore", category=ResourceWarning)

from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, BrowserSession
from dotenv import load_dotenv
import asyncio
import json
import os
import sys
import re

# Load environment variables from .env
load_dotenv()

# Get Google API key from environment
google_api_key = os.getenv("GOOGLE_API_KEY")
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")

# Define the storage path for interactions
STORAGE_DIR = "interactions"
STORAGE_FILE = os.path.join(STORAGE_DIR, "hmm_tracking_interactions.json")

def extract_tracking_fields(result, booking_id):
    """
    Extract booking_id, vessel_name, voyage_number, and arrival_date from agent result.
    Accepts either a string or dict result.
    Returns a dict with only those fields.
    """
    import re, json
    # If result is a dict with the fields, return them directly
    if isinstance(result, dict):
        # Try to get from top-level or nested 'result' or 'raw_result'
        for key in ['result', 'raw_result']:
            if key in result:
                return extract_tracking_fields(result[key], booking_id)
        # If all fields present, return
        if all(k in result for k in ['booking_id', 'voyage_number', 'vessel_name', 'arrival_date']):
            return {
                'booking_id': result['booking_id'],
                'vessel_name': result['vessel_name'],
                'voyage_number': result['voyage_number'],
                'arrival_date': result['arrival_date']
            }
        # If only some fields, continue to parse as string
        result = str(result)
    # If result is a string, try to extract fields
    text = str(result)
    # 1. Try to extract JSON code block with vessel_voyage
    json_block = re.search(r'```json(.*?)```', text, re.DOTALL)
    if json_block:
        try:
            data = json.loads(json_block.group(1))
            if 'vessel_voyage' in data and isinstance(data['vessel_voyage'], list) and data['vessel_voyage']:
                v = data['vessel_voyage'][0]
                return {
                    'booking_id': booking_id,
                    'vessel_name': v.get('vessel_name', 'Not available'),
                    'voyage_number': v.get('voyage_number', 'Not available'),
                    'arrival_date': v.get('arrival_date_time', 'Not available')
                }
        except Exception:
            pass
    # 2. Vessel Movement table row: | YM MANDATE 0096W | PS3 | SINGAPORE | 2025-03-17 11:00 | NHAVA SHEVA, INDIA | 2025-03-28 10:38 |
    vessel_row = re.search(r'\|\s*([A-Z0-9\- ]+)\s+(\d{4,5}[A-Z])\s*\|[^\|]*\|[^\|]*\|[^\|]*\|[^\|]*\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|', text)
    if vessel_row:
        vessel_name = vessel_row.group(1).strip()
        voyage_number = vessel_row.group(2).strip()
        arrival_date = vessel_row.group(3).strip()
        return {
            'booking_id': booking_id,
            'vessel_name': vessel_name,
            'voyage_number': voyage_number,
            'arrival_date': arrival_date
        }
    # 3. Fallback: try to extract from summary line
    summary = re.search(r"Voyage number: ([A-Z0-9]+). Arrival date: (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", text)
    if summary:
        voyage_number = summary.group(1)
        arrival_date = summary.group(2)
        # Try to extract vessel name from previous lines
        vessel_name = None
        vessel_match = re.search(r'Vessel / Voyage \|.*\n\| ([A-Z0-9\- ]+) '+voyage_number, text)
        if vessel_match:
            vessel_name = vessel_match.group(1).strip()
        else:
            vessel_name = 'Not available'
        return {
            'booking_id': booking_id,
            'vessel_name': vessel_name,
            'voyage_number': voyage_number,
            'arrival_date': arrival_date
        }
    # If not found, return Not available
    return {
        'booking_id': booking_id,
        'vessel_name': 'Not available',
        'voyage_number': 'Not available',
        'arrival_date': 'Not available'
    }

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
    
    # Configure and create browser session for Windows Chrome
    browser_session = BrowserSession(
        executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        headless=headless,
        viewport_size={"width": 1920, "height": 1080},
    )
    await browser_session.start()

    # Create the agent with optimized settings
    agent = Agent(
        task=task,
        llm=llm,
        browser_session=browser_session  # Pass BrowserSession
    )

    # Run the agent
    try:
        result = await agent.run()
        # Extract and store only the required fields in the JSON file
        minimal = extract_tracking_fields(result, booking_id)
        with open(STORAGE_FILE, 'w') as f:
            json.dump(minimal, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Saved minimal tracking result to {STORAGE_FILE}:")
        print(json.dumps(minimal, indent=2, ensure_ascii=False))
        return minimal
    except Exception as e:
        print(f"\n❌ Error during adaptive tracking: {e}")
        if 'ResourceExhausted' in str(e) or '429' in str(e):
            print('You have exhausted your Gemini API quota. Please wait for quota reset or use a new API key.')
        elif 'Failed to connect to LLM' in str(e):
            print('Failed to connect to LLM. Please check your API key and network connection.')
        raise
    finally:
        # Ensure the browser is properly closed
        await browser_session.close()

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


