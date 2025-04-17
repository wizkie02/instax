from instagrapi import Client
import os
import json
import time
import threading
from queue import Queue

class InstagramClient:
    def __init__(self):
        self.client = Client()
        self.session_file = "instagram_session.json"
        self.user_cache = {}  # Cache cho các user đã tìm kiếm
        self.verification_code_queue = Queue()  # Queue để nhận mã xác thực từ UI
        self.verification_needed = False  # Flag để kiểm tra xem có đang cần mã xác thực không
        
    def login(self, username, password, verification_code=None):
        """Login to Instagram and save session"""
        try:
            # Reset trạng thái xác thực
            self.verification_needed = False
            
            # Nếu có mã xác thực, thử đăng nhập với mã đó
            if verification_code:
                self.verification_code_queue.put(verification_code)
                
            # Định nghĩa callback để xử lý yêu cầu mã xác thực
            def code_handler():
                self.verification_needed = True
                if self.verification_code_queue.empty():
                    # Nếu không có mã từ UI, trả về một mã không hợp lệ để báo lỗi
                    return "000000"
                return self.verification_code_queue.get(block=True, timeout=300)  # Đợi tối đa 5 phút
                
            # Đăng nhập với callback xử lý mã xác thực
            self.client.login(username, password, verification_code=code_handler)
            
            # Nếu đăng nhập thành công, lưu session
            self.save_session()
            print(f"Logged in successfully as {username}")
            return {"success": True, "verification_needed": False}
            
        except Exception as e:
            error_message = str(e)
            print(f"Login failed: {error_message}")
            
            # Nếu cần mã xác thực, trả về thông báo cho UI
            if self.verification_needed:
                return {"success": False, "verification_needed": True, "error": "Verification code required"}
            
            return {"success": False, "verification_needed": False, "error": error_message}
    
    def is_verification_needed(self):
        """Kiểm tra xem có đang cần mã xác thực không"""
        return self.verification_needed
        
    def submit_verification_code(self, code):
        """Gửi mã xác thực từ UI vào queue để xử lý"""
        if self.verification_needed:
            self.verification_code_queue.put(code)
            return True
        return False
    
    def save_session(self):
        """Save the current session to a file"""
        try:
            session_data = self.client.get_settings()
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f)
            print(f"Session saved to {self.session_file}")
            return True
        except Exception as e:
            print(f"Failed to save session: {str(e)}")
            return False
    
    def load_session(self):
        """Load session from file if available"""
        if not os.path.exists(self.session_file):
            print("No session file found")
            return False
        
        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)
            
            self.client.set_settings(session_data)
            self.client.login_by_sessionid(session_data.get("sessionid", ""))
            print("Session loaded successfully")
            return True
        except Exception as e:
            print(f"Failed to load session: {str(e)}")
            return False
    
    def search_user(self, username):
        """Search for a user by username and return their info"""
        try:
            user = self.client.user_info_by_username(username)
            user_data = {
                "username": user.username,
                "full_name": user.full_name,
                "user_id": user.pk,
                "is_private": user.is_private,
                "follower_count": user.follower_count,
                "following_count": user.following_count,
                "biography": user.biography,
                "external_url": user.external_url,
                "profile_pic_url": user.profile_pic_url
            }
            return user_data
        except Exception as e:
            print(f"Error searching for user: {str(e)}")
            return None
    
    def send_message(self, user_id=None, username=None, message=None):
        """Send a direct message to a user by ID or username"""
        try:
            # Kiểm tra xem có message không
            if not message:
                print("Không có nội dung tin nhắn để gửi")
                return False
                
            # Nếu có username nhưng không có user_id, tìm user_id từ username
            if username and not user_id:
                try:
                    # Tìm user_id từ username
                    user = self.client.user_info_by_username(username)
                    if not user:
                        print(f"Không tìm thấy người dùng: {username}")
                        return False
                    user_id = user.pk
                    print(f"Đã tìm thấy user_id: {user_id} từ username: {username}")
                except Exception as e:
                    print(f"Lỗi khi tìm user_id từ username: {str(e)}")
                    return False
            
            # Kiểm tra user_id
            if not user_id:
                print("Không có user_id để gửi tin nhắn")
                return False
                
            # Convert user_id to integer if it's a string
            if isinstance(user_id, str) and user_id.isdigit():
                user_id = int(user_id)
                
            # Send message and get the thread ID
            thread = self.client.direct_send(message, [user_id])
            
            print(f"Đã gửi tin nhắn thành công đến user ID {user_id}")
            return True
        except Exception as e:
            print(f"Lỗi khi gửi tin nhắn: {str(e)}")
            return False
            
    def follow_user(self, user_id=None, username=None):
        """Follow a user by ID or username"""
        try:
            # Ưu tiên sử dụng user_id nếu được cung cấp
            if user_id:
                # Convert user_id to integer if it's a string
                if isinstance(user_id, str) and user_id.isdigit():
                    user_id = int(user_id)
                    
                result = self.client.user_follow(user_id)
                print(f"Followed user with ID: {user_id}")
                return {"success": True, "user_id": user_id}
                
            # Nếu không có user_id, sử dụng username
            elif username:
                # Tìm kiếm user_id từ username
                user = self.client.user_info_by_username(username)
                if not user:
                    return {"success": False, "error": f"User not found: {username}"}
                    
                result = self.client.user_follow(user.pk)
                print(f"Followed user: {username} (ID: {user.pk})")
                return {"success": True, "username": username, "user_id": user.pk}
                
            else:
                return {"success": False, "error": "User ID or username is required"}
                
        except Exception as e:
            error_message = str(e)
            print(f"Error following user: {error_message}")
            return {"success": False, "error": error_message}