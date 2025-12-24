#!/usr/bin/env python3
"""
Test script for email service
Run from back/ directory: python test_email.py
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Print current SMTP config
print("=" * 50)
print("SMTP Configuration Check:")
print("=" * 50)
print(f"SMTP_HOST: {os.getenv('SMTP_HOST', 'NOT SET')}")
print(f"SMTP_PORT: {os.getenv('SMTP_PORT', 'NOT SET')}")
print(f"SMTP_USER: {os.getenv('SMTP_USER', 'NOT SET')}")
print(f"SMTP_PASSWORD: {'*' * len(os.getenv('SMTP_PASSWORD', '')) if os.getenv('SMTP_PASSWORD') else 'NOT SET'}")
print(f"SMTP_FROM_NAME: {os.getenv('SMTP_FROM_NAME', 'NOT SET')}")
print("=" * 50)

# Test email service
from services.email_service import send_subscription_confirmation, get_smtp_config

config = get_smtp_config()
print(f"\nget_smtp_config() returns:")
print(f"  host: {config['host']}")
print(f"  port: {config['port']}")
print(f"  user: {config['user']}")
print(f"  password: {'*' * len(config['password']) if config['password'] else 'NOT SET'}")
print(f"  from_name: {config['from_name']}")

# Ask for test email
test_email = input("\nEnter your email to test (or press Enter to skip): ").strip()

if test_email:
    print(f"\nSending test email to {test_email}...")
    result = send_subscription_confirmation(test_email, "zh")
    print(f"Result: {result}")
    if result:
        print("✅ Email sent successfully! Check your inbox.")
    else:
        print("❌ Email sending failed. Check the error messages above.")
else:
    print("\nSkipping email test.")
