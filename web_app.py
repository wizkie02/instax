from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import os
import json
from instagram_client import InstagramClient
import threading

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'

# Khởi tạo Instagram client
instagram_client = InstagramClient()

@app.route('/')
def index():
    logged_in = 'username' in session
    return render_template('index.html', logged_in=logged_in, username=session.get('username', ''))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        username = request.form['username']
        password = request.form['password']
        verification_code = request.form.get('verification_code')
        
        # Lưu thông tin đăng nhập vào session để sử dụng lại khi cần xác thực
        session['_instagram_username'] = username
        session['_instagram_password'] = password
        
        # Gọi hàm login với thông tin từ form
        result = instagram_client.login(username, password, verification_code)
        
        # Nếu cần xác thực 2 yếu tố
        if not result['success'] and result.get('verification_needed'):
            flash('Instagram yêu cầu mã xác thực. Vui lòng nhập mã đã được gửi đến email/điện thoại của bạn.', 'warning')
            return redirect(url_for('verification'))
        
        # Nếu đăng nhập thành công
        if result['success']:
            session['username'] = username
            # Xóa thông tin đăng nhập tạm thời
            session.pop('_instagram_username', None)
            session.pop('_instagram_password', None)
            
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('index'))
        else:
            flash(f'Đăng nhập thất bại. {result.get("error")}', 'danger')
    
    return render_template('login.html')

@app.route('/login-ajax', methods=['POST'])
def login_ajax():
    """API endpoint để xử lý đăng nhập qua AJAX"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username và password là bắt buộc'})
    
    # Lưu thông tin đăng nhập vào session để sử dụng lại khi cần xác thực
    session['_instagram_username'] = username
    session['_instagram_password'] = password
    
    # Thực hiện đăng nhập
    result = instagram_client.login(username, password)
    
    if result.get('success'):
        session['username'] = username
        session.pop('_instagram_username', None)
        session.pop('_instagram_password', None)
        return jsonify({'success': True})
    else:
        return jsonify({
            'success': False, 
            'verification_needed': result.get('verification_needed', False),
            'error': result.get('error', 'Lỗi đăng nhập không xác định')
        })

@app.route('/submit-verification-code', methods=['POST'])
def submit_verification_code():
    """API endpoint để xử lý mã xác thực qua AJAX"""
    data = request.json
    verification_code = data.get('verification_code')
    
    if not verification_code:
        return jsonify({'success': False, 'error': 'Mã xác thực là bắt buộc'})
    
    username = session.get('_instagram_username')
    password = session.get('_instagram_password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'})
    
    # Thử đăng nhập lại với mã xác thực
    result = instagram_client.login(username, password, verification_code)
    
    if result.get('success'):
        session['username'] = username
        # Xóa thông tin đăng nhập tạm thời
        session.pop('_instagram_username', None)
        session.pop('_instagram_password', None)
        return jsonify({'success': True})
    else:
        return jsonify({
            'success': False,
            'verification_needed': result.get('verification_needed', False),
            'error': result.get('error', 'Lỗi xác thực không xác định')
        })

@app.route('/verification', methods=['GET', 'POST'])
def verification():
    """Route xử lý xác thực hai yếu tố"""
    if request.method == 'POST':
        verification_code = request.form['verification_code']
        username = session.get('_instagram_username')
        password = session.get('_instagram_password')
        
        if not username or not password:
            flash('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'danger')
            return redirect(url_for('login'))
        
        # Thử đăng nhập lại với mã xác thực
        result = instagram_client.login(username, password, verification_code)
        
        if result['success']:
            session['username'] = username
            # Xóa thông tin đăng nhập tạm thời
            session.pop('_instagram_username', None)
            session.pop('_instagram_password', None)
            
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('index'))
        else:
            flash(f'Xác thực thất bại. {result.get("error")}', 'danger')
            if result.get('verification_needed'):
                return redirect(url_for('verification'))
            else:
                return redirect(url_for('login'))
    
    # Kiểm tra xem có phải đang trong quá trình xác thực không
    if not instagram_client.is_verification_needed() and not session.get('_instagram_username'):
        flash('Không có yêu cầu xác thực nào đang diễn ra.', 'warning')
        return redirect(url_for('login'))
        
    return render_template('verification.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Đã đăng xuất thành công!', 'success')
    return redirect(url_for('index'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    user_info = None
    
    if request.method == 'POST':
        # Kiểm tra đăng nhập trước khi thực hiện tìm kiếm
        if 'username' not in session and not instagram_client.load_session():
            flash('Vui lòng đăng nhập trước khi tìm kiếm.', 'warning')
            return redirect(url_for('login'))
        
        username = request.form['search_username']
        user_info = instagram_client.search_user(username)
        
        if not user_info:
            flash(f'Không tìm thấy người dùng với username: {username}', 'warning')
    
    return render_template('search.html', user_info=user_info)

@app.route('/send-message', methods=['GET', 'POST'])
def send_message():
    if request.method == 'POST':
        # Kiểm tra đăng nhập trước khi gửi tin nhắn
        if 'username' not in session and not instagram_client.load_session():
            flash('Vui lòng đăng nhập trước khi gửi tin nhắn.', 'warning')
            return redirect(url_for('login'))
        
        # Lấy loại gửi tin nhắn (qua user_id hoặc username)
        send_type = request.form.get('send_type', 'userid')
        message = request.form.get('message', '')
        
        if not message:
            flash('Vui lòng nhập nội dung tin nhắn.', 'warning')
            return render_template('send_message.html')
        
        # Gửi tin nhắn theo loại đã chọn
        if send_type == 'userid':
            user_id = request.form.get('user_id', '')
            if not user_id:
                flash('Vui lòng nhập User ID người nhận.', 'warning')
                return render_template('send_message.html')
                
            if instagram_client.send_message(user_id=user_id, message=message):
                flash('Tin nhắn đã được gửi thành công!', 'success')
            else:
                flash('Gửi tin nhắn thất bại. Vui lòng thử lại sau.', 'danger')
        else:  # send_type == 'username'
            username = request.form.get('username', '')
            if not username:
                flash('Vui lòng nhập Username người nhận.', 'warning')
                return render_template('send_message.html')
                
            if instagram_client.send_message(username=username, message=message):
                flash('Tin nhắn đã được gửi thành công đến ' + username + '!', 'success')
            else:
                flash('Gửi tin nhắn thất bại. Vui lòng thử lại sau.', 'danger')
    
    return render_template('send_message.html')

@app.route('/follow', methods=['GET', 'POST'])
def follow_user():
    result = None
    
    if request.method == 'POST':
        # Kiểm tra đăng nhập trước khi thực hiện theo dõi
        if 'username' not in session and not instagram_client.load_session():
            flash('Vui lòng đăng nhập trước khi theo dõi người dùng.', 'warning')
            return redirect(url_for('login'))
        
        user_id = request.form.get('user_id', '')
        username = request.form.get('username', '')
        
        if not user_id and not username:
            flash('Vui lòng cung cấp User ID hoặc Username để theo dõi.', 'warning')
        else:
            result = instagram_client.follow_user(user_id=user_id, username=username)
            
            if result.get('success'):
                if username:
                    flash(f'Đã theo dõi người dùng: {username} thành công!', 'success')
                else:
                    flash(f'Đã theo dõi người dùng với ID: {user_id} thành công!', 'success')
            else:
                flash(f'Theo dõi thất bại: {result.get("error")}', 'danger')
    
    return render_template('follow.html', result=result)

@app.route('/api/search', methods=['POST'])
def api_search():
    # Kiểm tra đăng nhập trước khi thực hiện tìm kiếm API
    if 'username' not in session and not instagram_client.load_session():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    username = data.get('username')
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    user_info = instagram_client.search_user(username)
    
    if not user_info:
        return jsonify({'error': f'User not found: {username}'}), 404
    
    return jsonify(user_info)

@app.route('/api/send-message', methods=['POST'])
def api_send_message():
    # Kiểm tra đăng nhập trước khi gửi tin nhắn API
    if 'username' not in session and not instagram_client.load_session():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    user_id = data.get('user_id')
    username = data.get('username')
    message = data.get('message')
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    if not user_id and not username:
        return jsonify({'error': 'Either user_id or username is required'}), 400
    
    # Ưu tiên sử dụng user_id nếu có
    if user_id:
        if instagram_client.send_message(user_id=user_id, message=message):
            return jsonify({'success': True, 'message': 'Message sent successfully to user ID: ' + str(user_id)})
        else:
            return jsonify({'success': False, 'error': 'Failed to send message to user ID: ' + str(user_id)}), 500
    else:
        # Sử dụng username nếu không có user_id
        if instagram_client.send_message(username=username, message=message):
            return jsonify({'success': True, 'message': 'Message sent successfully to username: ' + username})
        else:
            return jsonify({'success': False, 'error': 'Failed to send message to username: ' + username}), 500

@app.route('/api/follow', methods=['POST'])
def api_follow_user():
    # Kiểm tra đăng nhập trước khi thực hiện theo dõi qua API
    if 'username' not in session and not instagram_client.load_session():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    user_id = data.get('user_id')
    username = data.get('username')
    
    if not user_id and not username:
        return jsonify({'error': 'User ID or username is required'}), 400
    
    result = instagram_client.follow_user(user_id=user_id, username=username)
    
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/reachout', methods=['POST'])
def api_reachout():
    """API endpoint để thực hiện liên tiếp 3 bước: tìm kiếm, follow, và gửi DM cho người dùng"""
    # Kiểm tra đăng nhập trước khi thực hiện
    if 'username' not in session and not instagram_client.load_session():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    username = data.get('username')
    message = data.get('message')
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    result = {
        'success': False,
        'steps': {
            'search': False,
            'follow': False,
            'message': False
        },
        'user_info': None
    }
    
    # Bước 1: Tìm kiếm thông tin người dùng
    user_info = instagram_client.search_user(username)
    if not user_info:
        return jsonify({
            'success': False,
            'error': f'User not found: {username}',
            'steps': result['steps']
        }), 404
    
    result['steps']['search'] = True
    result['user_info'] = user_info
    
    # Bước 2: Follow người dùng
    user_id = user_info['user_id']
    follow_result = instagram_client.follow_user(user_id=user_id)
    if follow_result.get('success'):
        result['steps']['follow'] = True
    # Tiếp tục ngay cả khi follow thất bại
    
    # Bước 3: Gửi tin nhắn đến người dùng
    if instagram_client.send_message(user_id=user_id, message=message):
        result['steps']['message'] = True
        result['success'] = True
        return jsonify(result)
    else:
        result['error'] = 'Failed to send message'
        return jsonify(result), 500

@app.route('/reachout', methods=['GET', 'POST'])
def reachout():
    """Route để xử lý tính năng Reach Out trên web UI"""
    if request.method == 'POST':
        # Kiểm tra đăng nhập trước khi thực hiện
        if 'username' not in session and not instagram_client.load_session():
            flash('Vui lòng đăng nhập trước khi sử dụng tính năng này.', 'warning')
            return redirect(url_for('login'))
        
        username = request.form.get('username')
        message = request.form.get('message')
        
        if not username or not message:
            flash('Vui lòng nhập đầy đủ thông tin username và nội dung tin nhắn.', 'warning')
            return render_template('reachout.html')
        
        # Bước 1: Tìm kiếm người dùng
        user_info = instagram_client.search_user(username)
        if not user_info:
            flash(f'Không tìm thấy người dùng với username: {username}', 'danger')
            return render_template('reachout.html')
        
        # Bước 2: Follow người dùng
        user_id = user_info['user_id']
        follow_result = instagram_client.follow_user(user_id=user_id)
        
        # Bước 3: Gửi tin nhắn
        if instagram_client.send_message(user_id=user_id, message=message):
            flash(f'Đã thực hiện thành công tất cả các bước: Tìm kiếm, Follow và gửi tin nhắn đến {username}!', 'success')
        else:
            flash(f'Đã tìm kiếm và follow người dùng {username}, nhưng không thể gửi tin nhắn.', 'warning')
    
    return render_template('reachout.html', logged_in='username' in session, username=session.get('username', ''))

if __name__ == '__main__':
    # Tạo thư mục templates nếu chưa tồn tại
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Khởi động ứng dụng Flask trên cổng 8888
    app.run(host='0.0.0.0', port=8888, debug=True)