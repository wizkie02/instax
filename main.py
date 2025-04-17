from instagram_client import InstagramClient
import argparse
import json
import os

def main():
    parser = argparse.ArgumentParser(description='Instagram Automation Tool')
    parser.add_argument('--username', type=str, help='Instagram username')
    parser.add_argument('--password', type=str, help='Instagram password')
    parser.add_argument('--search', type=str, help='Search for a user by username')
    parser.add_argument('--send-message', type=str, help='Send message to a user ID')
    parser.add_argument('--message-text', type=str, help='Message content to send')
    
    args = parser.parse_args()
    
    # Create an instance of InstagramClient
    client = InstagramClient()
    
    # Login with credentials
    if args.username and args.password:
        client.login(args.username, args.password)
    else:
        # Try to use saved session
        if not client.load_session():
            print("No saved session found. Please provide username and password.")
            return
    
    # Search for a user
    if args.search:
        user_info = client.search_user(args.search)
        if user_info:
            print(json.dumps(user_info, indent=4))
        else:
            print(f"User '{args.search}' not found")
    
    # Send message to a user
    if args.send_message and args.message_text:
        success = client.send_message(args.send_message, args.message_text)
        if success:
            print(f"Message sent successfully to user ID: {args.send_message}")
        else:
            print(f"Failed to send message to user ID: {args.send_message}")

if __name__ == "__main__":
    main()