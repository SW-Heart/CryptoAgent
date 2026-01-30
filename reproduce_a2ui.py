
import sys
import os

# Set up path to import back modules
sys.path.append(os.path.abspath("back"))

from back.tools.market_tools import generate_market_ticker_a2ui

try:
    print("Generating BTC ticker...")
    output = generate_market_ticker_a2ui("BTC")
    print("--- RAW OUTPUT START ---")
    print(output)
    print("--- RAW OUTPUT END ---")
    
    # Check JSON validity
    import json
    import re
    # Mimic frontend regex
    pattern = r"```a2ui\s*([\s\S]*?)```"
    match = re.search(pattern, output)
    if match:
        json_str = match.group(1)
        print(f"\nExtracted JSON string (len={len(json_str)}):")
        print(f"'{json_str}'")
        try:
            parsed = json.loads(json_str)
            print("\n✅ JSON Parse Success!")
            # print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON Parse Failed: {e}")
    else:
        print("\n❌ Regex mismatch!")

except Exception as e:
    print(f"Error: {e}")
