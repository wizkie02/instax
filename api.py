from flask import Flask, request, jsonify, render_template
from instagram_client import InstagramClient
import os
import json
import uuid
from functools import wraps
import jwt
import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Cho phép các domain khác nhau truy cập API
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key_change_in_production')

# Lưu trữ client instances - mỗi user sẽ có một client riêng
instagram_clients = {}

# Thư mục lưu trữ phiên Instagram của người dùng
SESSIONS_DIR = "instagram_sessions"
if not os.path.exists(SESSIONS_DIR):
    os.makedirs(SESSIONS_DIR)

# Decorator để kiểm tra xác thực JWT
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'success': False, 'error': 'Token is missing'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_instagram_username = data['instagram_username']
            
            # Kiểm tra xem user đã có client chưa
            if current_instagram_username not in instagram_clients:
                # Tạo mới một client nếu chưa có
                instagram_clients[current_instagram_username] = InstagramClient()
                instagram_clients[current_instagram_username].session_file = f"{SESSIONS_DIR}/{current_instagram_username}.json"
                
                # Thử tải phiên Instagram nếu đã có
                try:
                    instagram_clients[current_instagram_username].load_session()
                except:
                    return jsonify({'success': False, 'error': 'Session expired or invalid. Please login again.'}), 401
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        
        return f(current_instagram_username, *args, **kwargs)
    
    return decorated

@app.route('/api/login', methods=['POST'])
def login():
    """Đăng nhập vào Instagram"""
    data = request.json
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({
            "success": False,
            "error": "Instagram username and password are required"
        }), 400
    
    instagram_username = data['username']
    password = data['password']
    verification_code = data.get('verification_code')
    
    # Tạo hoặc lấy client hiện có
    if instagram_username in instagram_clients:
        client = instagram_clients[instagram_username]
    else:
        client = InstagramClient()
        client.session_file = f"{SESSIONS_DIR}/{instagram_username}.json"
        instagram_clients[instagram_username] = client
    
    # Thực hiện đăng nhập
    result = client.login(instagram_username, password, verification_code)
    
    if result.get("success", False):
        # Tạo token JWT với thông tin instagram_username
        token = jwt.encode({
            'instagram_username': instagram_username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)  # Token có hiệu lực 7 ngày
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            "success": True,
            "message": f"Logged in successfully to Instagram as {instagram_username}",
            "token": token
        })
    elif result.get("verification_needed", False):
        # Trả về thông báo cần mã xác thực
        return jsonify({
            "success": False,
            "verification_needed": True,
            "message": "Verification code required. Use the same endpoint with verification_code parameter to complete login."
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": result.get("error", "Unknown error")
        }), 401

# Trang đăng nhập để lấy JWT token
@app.route('/token-login', methods=['GET'])
def token_login():
    """Hiển thị trang đăng nhập để lấy JWT token"""
    return render_template('token_login.html')

@app.route('/api/search', methods=['GET'])
@token_required
def search_user(current_instagram_username):
    """Tìm kiếm thông tin người dùng Instagram"""
    username = request.args.get('username')
    
    if not username:
        return jsonify({
            "success": False,
            "error": "Username parameter is required"
        }), 400
    
    client = instagram_clients[current_instagram_username]
    user_data = client.search_user(username)
    
    if user_data:
        return jsonify({
            "success": True,
            "user": user_data
        })
    else:
        return jsonify({
            "success": False,
            "error": f"User '{username}' not found or error occurred"
        }), 404

@app.route('/api/send-message', methods=['POST'])
@token_required
def send_message(current_instagram_username):
    """Gửi tin nhắn cho người dùng Instagram"""
    data = request.json
    
    if not data:
        return jsonify({
            "success": False,
            "error": "Request body is required"
        }), 400
    
    user_id = data.get('user_id')
    username = data.get('username')
    message = data.get('message')
    
    if not message:
        return jsonify({
            "success": False,
            "error": "Message content is required"
        }), 400
        
    if not user_id and not username:
        return jsonify({
            "success": False,
            "error": "Either user_id or username is required"
        }), 400
    
    client = instagram_clients[current_instagram_username]
    success = client.send_message(user_id=user_id, username=username, message=message)
    
    if success:
        return jsonify({
            "success": True,
            "message": f"Message sent successfully to {username or user_id}"
        })
    else:
        return jsonify({
            "success": False,
            "error": "Failed to send message"
        }), 500

@app.route('/api/follow', methods=['POST'])
@token_required
def follow_user(current_instagram_username):
    """Theo dõi người dùng Instagram"""
    data = request.json
    
    if not data:
        return jsonify({
            "success": False,
            "error": "Request body is required"
        }), 400
    
    user_id = data.get('user_id')
    username = data.get('username')
    
    if not user_id and not username:
        return jsonify({
            "success": False,
            "error": "Either user_id or username is required"
        }), 400
    
    client = instagram_clients[current_instagram_username]
    result = client.follow_user(user_id=user_id, username=username)
    
    if result.get("success", False):
        return jsonify(result)
    else:
        return jsonify(result), 500

@app.route('/api/verification-status', methods=['GET'])
@token_required
def verification_status(current_instagram_username):
    """Kiểm tra trạng thái xác thực Instagram"""
    client = instagram_clients[current_instagram_username]
    is_needed = client.is_verification_needed()
    
    return jsonify({
        "verification_needed": is_needed
    })

@app.route('/api/logout', methods=['POST'])
@token_required
def logout(current_instagram_username):
    """Đăng xuất khỏi Instagram và xóa phiên"""
    try:
        client = instagram_clients[current_instagram_username]
        session_file = client.session_file
        
        if os.path.exists(session_file):
            os.remove(session_file)
        
        # Xóa client khỏi dictionary
        if current_instagram_username in instagram_clients:
            del instagram_clients[current_instagram_username]
        
        return jsonify({
            "success": True,
            "message": "Logged out of Instagram successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error during logout: {str(e)}"
        }), 500

@app.route('/api/reachout', methods=['POST'])
@token_required
def reachout(current_instagram_username):
    """Tiếp cận người dùng Instagram: tìm kiếm, theo dõi và gửi tin nhắn"""
    data = request.json
    
    if not data or 'username' not in data or 'message' not in data:
        return jsonify({
            "success": False,
            "error": "Username and message are required"
        }), 400
    
    username = data['username']
    message = data['message']
    should_follow = data.get('follow', False)
    
    client = instagram_clients[current_instagram_username]
    
    # 1. Tìm kiếm người dùng
    user_data = client.search_user(username)
    
    if not user_data:
        return jsonify({
            "success": False,
            "error": f"User '{username}' not found"
        }), 404
    
    user_id = user_data["user_id"]
    result = {
        "search": {
            "success": True,
            "user": user_data
        }
    }
    
    # 2. Theo dõi người dùng nếu yêu cầu
    if should_follow:
        follow_result = client.follow_user(user_id=user_id)
        result["follow"] = follow_result
    
    # 3. Gửi tin nhắn
    message_success = client.send_message(user_id=user_id, message=message)
    result["message"] = {
        "success": message_success,
        "details": f"Message {'sent successfully' if message_success else 'failed to send'} to {username}"
    }
    
    # Kết quả tổng thể
    result["success"] = (
        (not should_follow or result.get("follow", {}).get("success", False)) and 
        result["message"]["success"]
    )
    
    return jsonify(result)

@app.route('/api/status', methods=['GET'])
@token_required
def status(current_instagram_username):
    """Kiểm tra thông tin phiên Instagram hiện tại"""
    client = instagram_clients[current_instagram_username]
    
    # Kiểm tra xem đã có phiên Instagram đăng nhập chưa
    is_logged_in = os.path.exists(client.session_file)
    
    return jsonify({
        "logged_in": is_logged_in,
        "instagram_username": current_instagram_username
    })

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Kiểm tra trạng thái hoạt động của API"""
    system_info = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0.0",
        "active_users": len(instagram_clients),
        "uptime": "Unknown",  # Có thể cải thiện bằng cách lưu thời điểm khởi động
        "sessions_count": len(os.listdir(SESSIONS_DIR)) if os.path.exists(SESSIONS_DIR) else 0
    }
    return jsonify(system_info)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)