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
    print(f"\nDEBUG: Result type: {type(result)}")
    print(f"DEBUG: Result content: {result[:500]}..." if isinstance(result, str) else f"DEBUG: Result content: {result}")
    
    def split_vessel_and_voyage(text):
        """Split combined vessel name and voyage number"""
        if not text:
            return None, None
        # Pattern: name followed by space and number+letter at the end (e.g. "YM MANDATE 0096W")
        parts = text.strip().rsplit(' ', 1)
        if len(parts) == 2 and any(c.isdigit() for c in parts[1]) and parts[1][-1].upper() in 'WENS':
            return parts[0], parts[1]
        return text, None

    # Initialize return structure
    extracted = {
        'booking_id': booking_id,
        'vessel_name': 'Not available',
        'voyage_number': 'Not available',
        'arrival_date': 'Not available'
    }
    print(f"\nDEBUG: Result type: {type(result)}")
    print(f"DEBUG: Result content: {result[:500]}..." if isinstance(result, str) else f"DEBUG: Result content: {result}")
    
    # Initialize return structure
    extracted = {
        'booking_id': booking_id,
        'vessel_name': 'Not available',
        'voyage_number': 'Not available',
        'arrival_date': 'Not available'
    }
    
    # First try to handle dict input
    if isinstance(result, dict):
        # Try to parse nested results
        for key in ['result', 'raw_result', 'data']:
            if key in result:
                nested_result = extract_tracking_fields(result[key], booking_id)
                if nested_result['vessel_name'] != 'Not available':
                    return nested_result

        # Look for vessel_voyage structure
        if 'vessel_voyage' in result and isinstance(result['vessel_voyage'], list):
            v = result['vessel_voyage'][0]
            if 'vessel_name' in v or 'voyage_number' in v:
                # Extract combined vessel and voyage if present
                if 'voyage_number' in v and ' ' in v['voyage_number']:
                    vessel_name, voyage_number = split_vessel_and_voyage(v['voyage_number'])
                    if vessel_name:
                        extracted['vessel_name'] = vessel_name
                    if voyage_number:
                        extracted['voyage_number'] = voyage_number
                else:
                    # Take values as-is
                    extracted['vessel_name'] = v.get('vessel_name', extracted['vessel_name'])
                    extracted['voyage_number'] = v.get('voyage_number', extracted['voyage_number'])

                # Try different date field names
                for date_key in ['arrival_date_time', 'arrival_date', 'etb']:
                    if date_key in v and v[date_key]:
                        extracted['arrival_date'] = v[date_key]
                        break

                if any(val != 'Not available' for val in extracted.values()):
                    return extracted

    # Convert to string for pattern matching
    text = str(result)
    
    # Look for direct JSON data first
    json_match = re.search(r'\{[^{}]*"voyage_number":\s*"([^"]+)"[^{}]*\}', text)
    if json_match:
        voyage_str = json_match.group(1)
        vessel_name, voyage_number = split_vessel_and_voyage(voyage_str)
        if vessel_name:
            extracted['vessel_name'] = vessel_name
        if voyage_number:
            extracted['voyage_number'] = voyage_number
            # Look for corresponding arrival date
            date_match = re.search(r'"arrival_date(?:_time)?":\s*"([^"]+)"', text)
            if date_match:
                extracted['arrival_date'] = date_match.group(1)
                return extracted

    # Search for json code blocks
    json_blocks = re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    for match in json_blocks:
        try:
            data = json.loads(match.group())
            if 'voyage_number' in data:
                # Handle combined vessel name and voyage
                vessel_name, voyage_number = split_vessel_and_voyage(data['voyage_number'])
                if vessel_name:
                    extracted['vessel_name'] = vessel_name
                if voyage_number:
                    extracted['voyage_number'] = voyage_number
                    
                if 'arrival_date' in data:
                    extracted['arrival_date'] = data['arrival_date']
                    if any(val != 'Not available' for val in extracted.values()):
                        return extracted
        except json.JSONDecodeError:
            continue

    # Look for specific patterns in text
    vessel_num = re.search(r'(?:vessel|ship)\s+name\s+(?:and\s+voyage\s+number\s+)?(?:is|:)\s*([A-Z0-9\- ]+\s+\d{4,5}[WENS])', text, re.IGNORECASE)
    if vessel_num:
        vessel_name, voyage_number = split_vessel_and_voyage(vessel_num.group(1))
        if vessel_name:
            extracted['vessel_name'] = vessel_name
        if voyage_number:
            extracted['voyage_number'] = voyage_number
            # Look for arrival date nearby
            date_match = re.search(r'arrival\s+date\s*(?:\(ETB\))?\s*(?:is|:)\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', text, re.IGNORECASE)
            if date_match:
                extracted['arrival_date'] = date_match.group(1)
                return extracted

    # Look for plaintext patterns as last resort
    name_match = re.search(r'(?:vessel|ship)\s+name\s*(?:is|:)\s*([A-Z0-9\- ]+)(?!\d{4,5}[WENS])', text, re.IGNORECASE)
    if name_match:
        extracted['vessel_name'] = name_match.group(1).strip()

    voyage_match = re.search(r'voyage\s+(?:number\s+)?(?:is|:)\s*(\d{4,5}[WENS])', text, re.IGNORECASE)
    if voyage_match:
        extracted['voyage_number'] = voyage_match.group(1).strip()

    date_match = re.search(r'(?:arrival|eta|etb)\s+(?:date|time)\s*(?:\(ETB\))?\s*(?:is|:)\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', text, re.IGNORECASE)
    if date_match:
        extracted['arrival_date'] = date_match.group(1).strip()

    if any(val != 'Not available' for val in extracted.values()):
        print("DEBUG: Found some values in plain text")
        return extracted
    
    print("DEBUG: No reliable data found, returning defaults")
    return extracted

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


