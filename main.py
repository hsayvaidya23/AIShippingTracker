from langchain_google_genai import ChatGoogleGenerativeAI  
from browser_use import Agent, Browser, BrowserConfig, BrowserSession
from dotenv import load_dotenv
import asyncio
import json
import os
import re
from datetime import datetime
import warnings

# Ignore ResourceWarnings (e.g., unclosed browser sessions)
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message="unclosed.*")
warnings.filterwarnings("ignore", message="I/O operation on closed pipe")

# Load environment variables from .env
load_dotenv()

# Get Google API key from environment
google_api_key = os.getenv("GOOGLE_API_KEY")
print(f"Google API Key: {google_api_key}")  # Debugging line to check if key is loaded
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")

# Define the storage path for interactions
STORAGE_DIR = "interactions"
RESULTS_DIR = "results"
STORAGE_FILE = os.path.join(STORAGE_DIR, "hmm_tracking_interactions.json")

# Ensure storage directory exists
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

def extract_tracking_fields(result, booking_id):
    """
    Extract booking_id, vessel_name, voyage_number, and arrival_date from agent result.
    Accepts either a string or dict result.
    Returns a dict with only those fields.
    """
    print(f"\nDEBUG: Result type: {type(result)}")
    print(f"DEBUG: Result content: {result[:500]}..." if isinstance(result, str) else f"DEBUG: Result content: {result}")
    
    # Initialize return structure
    extracted = {
        'booking_id': booking_id,
        'vessel_name': 'Not available',
        'voyage_number': 'Not available',
        'arrival_date': 'Not available'
    }
    
    # If input is a dict, try to handle nested structures first
    if isinstance(result, dict):
        # Check for result/raw_result nesting
        for key in ['result', 'raw_result', 'data']:
            if key in result:
                nested_result = extract_tracking_fields(result[key], booking_id)
                if nested_result['vessel_name'] != 'Not available':
                    return nested_result
        
        # Try direct vessel_voyage structure
        if 'vessel_voyage' in result and isinstance(result['vessel_voyage'], list) and result['vessel_voyage']:
            v = result['vessel_voyage'][0]
            if 'vessel_name' in v:
                extracted['vessel_name'] = v.get('vessel_name')
                extracted['voyage_number'] = v.get('voyage_number', 'Not available')
                # Handle different date field names
                for date_key in ['arrival_date_time', 'arrival_date', 'etb']:
                    if date_key in v and v[date_key]:
                        extracted['arrival_date'] = v[date_key]
                        break
                if any(val != 'Not available' for val in extracted.values()):
                    return extracted
    
    # Convert to string for pattern matching
    text = str(result)
    
    # Try each pattern in order of reliability
    
    # 1. Look for structured vessel_voyage JSON pattern
    vessel_voyage_match = re.search(r'"vessel_voyage":\s*\[\s*\{[^}]*"vessel_name":\s*"([^"]+)"[^}]*"voyage_number":\s*"([^"]+)"[^}]*"(?:arrival_date_time|arrival_date|etb)":\s*"([^"]+)"', text)
    if vessel_voyage_match:
        print("DEBUG: Found vessel_voyage JSON pattern")
        vessel_name, voyage_num, arr_date = vessel_voyage_match.groups()
        if vessel_name and voyage_num and arr_date:
            return {
                'booking_id': booking_id,
                'vessel_name': vessel_name,
                'voyage_number': voyage_num,
                'arrival_date': arr_date
            }
    
    # 2. Look for JSON code blocks
    json_blocks = re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    for match in json_blocks:
        try:
            data = json.loads(match.group())
            # Check various JSON structures we might encounter
            if 'vessel_voyage' in data and isinstance(data['vessel_voyage'], list) and data['vessel_voyage']:
                v = data['vessel_voyage'][0]
                if 'vessel_name' in v:
                    print("DEBUG: Found vessel_voyage in JSON block")
                    extracted['vessel_name'] = v.get('vessel_name')
                    extracted['voyage_number'] = v.get('voyage_number', 'Not available')
                    # Try different date field names
                    for date_key in ['arrival_date_time', 'arrival_date', 'etb']:
                        if date_key in v and v[date_key]:
                            extracted['arrival_date'] = v[date_key]
                            break
                    if extracted['vessel_name'] != 'Not available':
                        return extracted
            # Alternative structure
            elif all(key in data for key in ['vessel_name', 'voyage_number']):
                print("DEBUG: Found direct fields in JSON block")
                extracted['vessel_name'] = data.get('vessel_name')
                extracted['voyage_number'] = data.get('voyage_number')
                # Try different date field names
                for date_key in ['arrival_date_time', 'arrival_date', 'etb']:
                    if date_key in data and data[date_key]:
                        extracted['arrival_date'] = data[date_key]
                        break
                if extracted['vessel_name'] != 'Not available':
                    return extracted
        except json.JSONDecodeError:
            continue
    
    # 3. Try to extract from table format
    # Matches vessel name and voyage number in various formats
    vessel_row = re.search(
        r'\|\s*([A-Z0-9\- ]+?)(?:\s+(\d{4,5}[A-Z]))?[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})',
        text
    )
    if vessel_row:
        print("DEBUG: Found vessel info in table format")
        vessel_name = vessel_row.group(1).strip()
        # Group 2 might be None if voyage number wasn't in expected format
        voyage_number = vessel_row.group(2) if vessel_row.group(2) else 'Not available'
        arrival_date = vessel_row.group(3).strip()
        if vessel_name and arrival_date:
            return {
                'booking_id': booking_id,
                'vessel_name': vessel_name,
                'voyage_number': voyage_number,
                'arrival_date': arrival_date
            }
    
    # 4. Look for plaintext patterns
    # Vessel name patterns like "vessel name is YM MANDATE" or "Vessel Name: YM MANDATE"
    vessel_name_match = re.search(r'(?:vessel\s+name\s+is|Vessel\s+Name:?)\s+([A-Z0-9\- ]+)', text)
    voyage_num_match = re.search(r'(?:voyage\s+number\s+is|Voyage\s+Number:?)\s+([A-Z0-9\-]+)', text)
    arrival_date_match = re.search(r'(?:arrival\s+date(?:\s+and\s+time)?\s+is|Arrival\s+Date\s+and\s+Time\s*(?:\(ETB\))?:?)\s+(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})', text)
    
    if vessel_name_match:
        extracted['vessel_name'] = vessel_name_match.group(1).strip()
    if voyage_num_match:
        extracted['voyage_number'] = voyage_num_match.group(1).strip()
    if arrival_date_match:
        extracted['arrival_date'] = arrival_date_match.group(1).strip()
    
    # Only return if we found something
    if any(val != 'Not available' for val in extracted.values()):
        print("DEBUG: Found values in plaintext")
        return extracted
    
    # If we got here, we couldn't extract the data reliably
    print("DEBUG: No reliable data found, returning default values")
    return extracted

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
    llm = ChatGoogleGenerativeAI(  
        model='gemini-2.0-flash-exp',
        temperature=0.0,
        google_api_key=google_api_key
    )
    
    # Define the task with clear instructions    
    task = f"""
        Track HMM shipping container with booking ID '{booking_id}':
    
        1. Go to http://www.seacargotracking.net/ 
        2. Look for HMM (Hyundai Merchant Marine) or similar options
        3. Search for Track & Trace and click on it:
            - Input booking ID in search or B/L No. field 
            - Click on Search button 
        4. Scrape the full page content and extract:
            - Vessel name (e.g., YM MANDATE)
            - Voyage number from vessel name format (e.g., 0096W)
            - Arrival date with time from ETB (Estimated Time of Berthing)
    
    Return the data in this exact JSON format:
    {{
        "vessel_voyage": [
            {{
                "vessel_name": "extracted vessel name",
                "voyage_number": "extracted voyage number",
                "arrival_date_time": "YYYY-MM-DD HH:MM"
            }}
        ]
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
      # Configure and create browser session for Windows Chrome
    browser_session = None
    agent = None
    
    try:
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
            browser_session=browser_session
        )
        
        # Run the agent
        result = await agent.run()
        
        # Debug: Print raw result
        print(f"\nDEBUG: Raw agent result type: {type(result)}")
        print(f"DEBUG: Raw agent result: {result}")
        
        return result
    finally:
        # Ensure proper cleanup
        try:
            if browser_session:
                await browser_session.close()
                # Give it a moment to clean up
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Warning: Error closing browser session: {e}")

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

    # Extract and store only the required fields in the JSON file
    minimal = extract_tracking_fields(result, booking_id)    
    
    # Save both the raw result and the extracted data for debugging
    debug_data = {
        "timestamp": datetime.now().isoformat(),
        "booking_id": booking_id,
        "raw_result": str(result),
        "extracted_data": minimal
    }
    debug_file = os.path.join(STORAGE_DIR, f"debug_{booking_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(debug_file, 'w', encoding='utf-8') as f:
        json.dump(debug_data, f, indent=2, ensure_ascii=False)
    print(f"\nDEBUG: Saved debug data to {debug_file}")
    
    # Save the minimal tracking result
    with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(minimal, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved minimal tracking result to {STORAGE_FILE}:")
    print(json.dumps(minimal, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())



