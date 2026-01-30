import sys
import os

# Add the project root and back directory to the python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'back'))

from back.tools.technical_aggregator import get_all_technical_indicators

if __name__ == "__main__":
    print("="*60)
    print("TEST: Direct Aggregator Tool Call (Full Output)")
    print("="*60)
    
    try:
        # Test with multiple symbols
        print("Fetching technical data for BTC, ETH...")
        report = get_all_technical_indicators("BTC,ETH", timeframe="1d")
        
        print(f"Success! Report generated with {len(report)} characters.")
        
        # Save to file for full inspection
        output_file = "aggregated_report_test.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
            
        print(f"\nFull report saved to: {os.path.abspath(output_file)}")
        print("You can open this file to see the exact data structure returned by the tool.")
        
    except Exception as e:
        print(f"Tool call failed: {e}")
