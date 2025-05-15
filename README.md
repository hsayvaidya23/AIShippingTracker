# HMM Shipping Line Tracker

An AI-powered solution to automatically retrieve voyage numbers and arrival dates for HMM shipping bookings using seacargotracking.net.

## Features

- **Natural Language Automation**: Uses AI to navigate the shipping tracking website without hardcoded interactions
- **Process Persistence**: Stores successful interactions for future use
- **Adaptability**: Handles different booking IDs with minimal manual intervention
- **Optimized Browser Control**: Configurable viewport size and headless operation

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- Internet connection
- OpenAI API key (for GPT-4o model)

### Installation

1. **Clone or download this repository**

2. **Set up a Python environment**

   Using venv:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

   Or using uv (recommended):
   ```bash
   uv venv --python 3.11
   # On Windows:
   .venv\Scripts\activate
   # On Unix:
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   uv pip install -r requirements.txt
   # Or with regular pip:
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**

   ```bash
   playwright install
   ```

5. **Configure API Key**

   Create a `.env` file in the project root:
   ```
   GOOGLE_API_KEY=your_google_gemini_api_key_here
   ```
   
   For reference, see the example in `dot-env-example`.

## Usage

### First-Time Tracking

To track a shipping container using a booking ID:

```bash
# Windows (with browser visible)
run.bat YOUR_BOOKING_ID

# Windows (headless mode - no visible browser)
run.bat --headless YOUR_BOOKING_ID

# Unix (with browser visible)
python main.py YOUR_BOOKING_ID

# Unix (headless mode)
python main.py --headless YOUR_BOOKING_ID
```

If no booking ID is provided, the example ID `SINI25432400` will be used.

### Adaptive Tracking (After First Use)

For faster tracking of new booking IDs using stored interactions:

```bash
# Windows (with browser visible)
run_adaptive.bat YOUR_BOOKING_ID

# Windows (headless mode - no visible browser)
run_adaptive.bat --headless YOUR_BOOKING_ID

# Unix (with browser visible)
python adaptive_tracking.py YOUR_BOOKING_ID

# Unix (headless mode)
python adaptive_tracking.py --headless YOUR_BOOKING_ID
```

## How It Works

### Step 1: Initial Retrieval

The `main.py` script uses Browser Use and GPT-4o to:
1. Navigate to seacargotracking.net
2. Find and select the HMM carrier option
3. Enter the booking ID
4. Retrieve the voyage number and arrival date
5. Return the data in a JSON format

### Step 2: Process Persistence

The initial tracking process stores all browser interactions in `interactions/hmm_tracking_interactions.json`. This file contains:
- Timestamp of the tracking
- Booking ID used
- All successful browser steps and interactions

### Step 3: Adaptability

The `adaptive_tracking.py` script uses the stored interactions as a guide but can adapt to:
- Different booking IDs
- Changes in the website structure
- Potential errors or timeouts

## Advanced Configuration

### Browser Settings

The solution uses Browser Use's configuration options for optimal performance:

- **Viewport Size**: Set to 1280x720 for better site rendering
- **Headless Mode**: Can run without displaying a browser window

### LLM Settings

- **Model**: Uses GPT-4o for highest accuracy (89% on WebVoyager Dataset)
- **Temperature**: Set to 0.0 for consistent results

## Output Verification

The tool outputs data in a structured JSON format containing:
- `booking_id`: The input booking ID
- `voyage_number`: The retrieved voyage number
- `arrival_date`: The expected arrival date

You can verify this information by manually visiting seacargotracking.net and searching for the same booking ID.

## Troubleshooting

- **Browser Issues**: If the browser doesn't start, try running `playwright install` again
- **API Key Errors**: Ensure your OpenAI API key is correctly set in the `.env` file
- **Website Changes**: If the website structure changes significantly, delete the `interactions` folder to rebuild the interaction model
- **Resource Usage**: If experiencing high resource usage, try running in headless mode with `--headless` flag 