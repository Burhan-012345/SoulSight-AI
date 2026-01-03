import os
import io
import requests
import json
import uuid
import base64
import tempfile
from datetime import datetime, timedelta, date
from pathlib import Path
from functools import wraps

import google.generativeai as genai
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from PIL import Image
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from gtts import gTTS
import sqlalchemy as sa

from config import Config
import hashlib
import time
from threading import Lock
from functools import lru_cache

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[app.config['RATELIMIT_DEFAULT']]
)

# Configure Gemini
genai.configure(api_key=app.config['GEMINI_API_KEY'])

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    profile_pic = db.Column(db.String(500))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships with cascade delete
    images = db.relationship('UserImage', backref='user', 
                             lazy=True, 
                             cascade='all, delete-orphan',
                             passive_deletes=True)
    favorites = db.relationship('Favorite', backref='user', 
                                lazy=True, 
                                cascade='all, delete-orphan',
                                passive_deletes=True)

class UserImage(db.Model):
    __tablename__ = 'images'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100))
    file_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships with cascade delete
    ai_results = db.relationship('AIResult', backref='image', 
                                 lazy=True, 
                                 cascade='all, delete-orphan',
                                 passive_deletes=True)
    
    def __repr__(self):
        return f'<UserImage {self.id}: {self.original_filename}>'

class AIResult(db.Model):
    __tablename__ = 'ai_results'
    
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id', ondelete='CASCADE'), nullable=False)
    mode = db.Column(db.String(100), nullable=False)
    prompt = db.Column(db.Text)
    result_text = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.String(50))
    language = db.Column(db.String(10), default='en')
    tone = db.Column(db.String(50))
    length = db.Column(db.String(50))
    processing_time = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships with cascade delete
    favorites = db.relationship('Favorite', backref='ai_result', 
                                lazy=True, 
                                cascade='all, delete-orphan',
                                passive_deletes=True)
    
    def __repr__(self):
        return f'<AIResult {self.id} for Image {self.image_id}>'

class Favorite(db.Model):
    __tablename__ = 'favorites'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    ai_result_id = db.Column(db.Integer, db.ForeignKey('ai_results.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate favorites
    __table_args__ = (db.UniqueConstraint('user_id', 'ai_result_id', name='unique_user_favorite'),)
    
    def __repr__(self):
        return f'<Favorite {self.id}: User {self.user_id} -> Result {self.ai_result_id}>'

# ============================================
# GEMINI API CONFIGURATIONS
# ============================================

gemini_cooldown_lock = Lock()
gemini_last_call_time = datetime.min 
gemini_user_cooldowns = {}  

# Daily quota tracking
gemini_daily_counts = {}  # user_id -> count
gemini_daily_reset_date = date.today()
gemini_daily_lock = Lock()

# Request cache for duplicate images/prompts
gemini_request_cache = {}  
image_hash_cache = {}

# Free tier limits
FREE_TIER_DAILY_LIMIT = 15  # Stay under 20 with buffer
FREE_TIER_COOLDOWN = 60  # 60 seconds between calls

def calculate_image_hash(image_path):
    """Calculate MD5 hash of image file for duplicate detection"""
    try:
        with open(image_path, 'rb') as f:
            file_hash = hashlib.md5()
            chunk = f.read(8192)
            while chunk:
                file_hash.update(chunk)
                chunk = f.read(8192)
        return file_hash.hexdigest()
    except Exception as e:
        print(f"Hash calculation error: {e}")
        return None

def check_daily_quota(user_id):
    """Check if user has exceeded daily quota"""
    with gemini_daily_lock:
        # Reset daily counts if it's a new day
        today = date.today()
        global gemini_daily_reset_date
        if today != gemini_daily_reset_date:
            gemini_daily_counts.clear()
            gemini_daily_reset_date = today
            print(f"Daily quota reset for new day: {today}")
        
        # Check user's daily count
        user_count = gemini_daily_counts.get(user_id, 0)
        daily_limit = FREE_TIER_DAILY_LIMIT
        
        if user_count >= daily_limit:
            return False, user_count, daily_limit
        
        return True, user_count, daily_limit

def increment_daily_count(user_id):
    """Increment user's daily API call count"""
    with gemini_daily_lock:
        gemini_daily_counts[user_id] = gemini_daily_counts.get(user_id, 0) + 1
        return gemini_daily_counts[user_id]

def check_gemini_cooldown(user_id=None):
    """
    Check if we can make a Gemini API call based on global and user cooldowns
    Returns: (can_call, wait_seconds, message)
    """
    with gemini_cooldown_lock:
        now = datetime.now()
        
        # Global cooldown check
        time_since_last_call = (now - gemini_last_call_time).total_seconds()
        if time_since_last_call < FREE_TIER_COOLDOWN:
            wait_time = FREE_TIER_COOLDOWN - time_since_last_call
            return False, wait_time, f"Global cooldown active. Please wait {wait_time:.0f} seconds."
        
        # User-specific cooldown check
        if user_id:
            last_user_call = gemini_user_cooldowns.get(user_id, datetime.min)
            time_since_user_call = (now - last_user_call).total_seconds()
            if time_since_user_call < FREE_TIER_COOLDOWN:
                wait_time = FREE_TIER_COOLDOWN - time_since_user_call
                return False, wait_time, f"Please wait {wait_time:.0f} seconds before another analysis."
        
        return True, 0, "OK"

def update_gemini_call_time(user_id=None):
    """Update last call time after successful Gemini API call"""
    with gemini_cooldown_lock:
        global gemini_last_call_time
        gemini_last_call_time = datetime.now()
        if user_id:
            gemini_user_cooldowns[user_id] = datetime.now()

def get_cached_result(image_hash, mode, custom_prompt, tone, length, language, question):
    """Check if we have a cached result for this exact request"""
    cache_key = f"{image_hash}:{mode}:{custom_prompt}:{tone}:{length}:{language}:{question}"
    return gemini_request_cache.get(cache_key)

def cache_result(image_hash, mode, custom_prompt, tone, length, language, question, result):
    """Cache a Gemini result for future requests"""
    cache_key = f"{image_hash}:{mode}:{custom_prompt}:{tone}:{length}:{language}:{question}"
    gemini_request_cache[cache_key] = result
    # Limit cache size to prevent memory issues
    if len(gemini_request_cache) > 1000:
        # Remove oldest entries (first 100)
        keys_to_remove = list(gemini_request_cache.keys())[:100]
        for key in keys_to_remove:
            del gemini_request_cache[key]

def get_available_gemini_models():
    """Get list of available Gemini models"""
    try:
        models = genai.list_models()
        available_models = []
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                available_models.append({
                    'name': model.name,
                    'display_name': model.display_name,
                    'description': model.description,
                    'supported_methods': model.supported_generation_methods
                })
        return available_models
    except Exception as e:
        print(f"Error listing models: {e}")
        return []

# ============================================
# UPDATED HELPER FUNCTIONS
# ============================================

def get_image_category(image_path):
    """Detect image category using Gemini WITH COOLDOWN"""
    print("Skipping automatic category detection to save API quota")
    return 'Other'

def process_image_with_gemini(image_path, mode='detailed_description', custom_prompt=None, 
                             tone='neutral', length='medium', language='en', question=None,
                             user_id=None):
    """Process image with Google Gemini API WITH COOLDOWN AND CACHING"""
    
    # Check daily quota first
    if user_id:
        has_quota, current_count, daily_limit = check_daily_quota(user_id)
        if not has_quota:
            return {
                'text': f"⚠️ Daily quota exceeded. You've used {current_count} of {daily_limit} requests today. Quota resets at midnight UTC.",
                'confidence': 'Low',
                'processing_time': 0,
                'cached': False,
                'cooldown': 3600,  # 1 hour
                'quota_exceeded': True
            }
    
    # Check cooldown
    can_call, wait_time, message = check_gemini_cooldown(user_id)
    if not can_call:
        return {
            'text': f"⚠️ {message}",
            'confidence': 'Low',
            'processing_time': 0,
            'cached': False,
            'cooldown': wait_time
        }
    
    # Calculate image hash for caching
    image_hash = calculate_image_hash(image_path)
    if image_hash:
        # Check cache first
        cached_result = get_cached_result(image_hash, mode, custom_prompt, tone, length, language, question)
        if cached_result:
            print(f"Using cached result for image hash: {image_hash[:8]}...")
            return {
                'text': cached_result['text'],
                'confidence': cached_result.get('confidence', 'Medium'),
                'processing_time': cached_result.get('processing_time', 0),
                'cached': True,
                'cooldown': 0,
                'quota_exceeded': False
            }
    
    try:
        start_time = datetime.now()
        
        # Try models in order (use simpler models first for free tier)
        models_to_try = [
            'gemini-2.0-flash',          # More likely to have separate quota
            'gemini-flash-latest',       # Latest flash model
            'gemini-1.5-flash-latest',   # Fallback
        ]
        
        # Add config model if specified
        if app.config.get('GEMINI_MODEL'):
            models_to_try = [app.config['GEMINI_MODEL']] + models_to_try
        
        # Remove duplicates
        models_to_try = list(dict.fromkeys(models_to_try))
        
        print(f"Models to try: {models_to_try}")
        
        last_error = None
        
        for model_name in models_to_try:
            try:
                print(f"Attempting with model: {model_name}")
                
                # Clean model name if it has 'models/' prefix
                if model_name.startswith('models/'):
                    model_name_clean = model_name.replace('models/', '')
                else:
                    model_name_clean = model_name
                
                model = genai.GenerativeModel(model_name_clean)
                img = Image.open(image_path)
                
                # Base prompts based on mode
                prompts = {
                    'caption': "Generate a concise, emotionally resonant caption for this image.",
                    'detailed_description': "Provide a detailed, emotionally rich description of this image, capturing its essence, mood, and significance.",
                    'educational': "Explain this image from an educational perspective. What can be learned from it? What concepts does it illustrate?",
                    'creative_story': "Create a romantic, emotionally engaging story or poem inspired by this image.",
                    'keywords': "Generate relevant keywords and tags for this image, focusing on emotional and descriptive elements."
                }
                
                # Language mapping
                languages = {
                    'en': 'English',
                    'hi': 'Hindi',
                    'ur': 'Urdu'
                }
                
                # Tone mapping
                tones = {
                    'formal': 'Use a formal, professional tone.',
                    'casual': 'Use a casual, conversational tone.',
                    'romantic': 'Use a romantic, poetic, emotionally expressive tone.'
                }
                
                # Length mapping
                lengths = {
                    'short': 'Provide a brief response (1-2 sentences).',
                    'medium': 'Provide a detailed response (3-5 sentences).',
                    'long': 'Provide an extensive, comprehensive response (6+ sentences).'
                }
                
                # Construct final prompt
                base_prompt = prompts.get(mode, prompts['detailed_description'])
                language_instruction = f"Respond in {languages.get(language, 'English')}."
                tone_instruction = tones.get(tone, '')
                length_instruction = lengths.get(length, '')
                
                if custom_prompt:
                    final_prompt = f"{custom_prompt}\n{language_instruction}\n{tone_instruction}\n{length_instruction}"
                elif question:
                    final_prompt = f"{question}\n{language_instruction}\n{tone_instruction}"
                else:
                    final_prompt = f"{base_prompt}\n{language_instruction}\n{tone_instruction}\n{length_instruction}"
                
                print(f"Prompt: {final_prompt[:100]}...")
                
                # Generate response
                try:
                    response = model.generate_content([final_prompt, img])
                    
                    # Check if response has text
                    if not response.text:
                        raise Exception("Empty response from model")
                        
                except Exception as api_error:
                    error_str = str(api_error)
                    if "429" in error_str or "quota" in error_str.lower():
                        last_error = api_error
                        print(f"Model {model_name} quota exceeded: {error_str[:100]}")
                        # Don't continue to other models - quota is per project
                        break
                    elif "404" in error_str or "not found" in error_str.lower():
                        print(f"Model {model_name} not found, trying next model...")
                        continue
                    elif "503" in error_str or "unavailable" in error_str.lower():
                        print(f"Model {model_name} unavailable, trying next model...")
                        continue
                    else:
                        raise api_error
                
                # Calculate processing time
                processing_time = (datetime.now() - start_time).total_seconds()
                
                # Estimate confidence
                text_length = len(response.text)
                if text_length > 100:
                    confidence = "High"
                elif text_length > 50:
                    confidence = "Medium"
                else:
                    confidence = "Low"
                
                result_data = {
                    'text': response.text,
                    'confidence': confidence,
                    'processing_time': processing_time,
                    'cached': False,
                    'cooldown': 0,
                    'model_used': model_name_clean,
                    'quota_exceeded': False
                }
                
                # Cache the result if we have a hash
                if image_hash:
                    cache_result(image_hash, mode, custom_prompt, tone, length, language, question, result_data)
                
                # Update cooldown tracker
                update_gemini_call_time(user_id)
                
                # Increment daily quota count
                if user_id:
                    new_count = increment_daily_count(user_id)
                    print(f"User {user_id} daily count: {new_count}/{FREE_TIER_DAILY_LIMIT}")
                
                print(f"Success with model: {model_name_clean}")
                return result_data
                
            except Exception as model_error:
                last_error = model_error
                print(f"Model {model_name} failed: {model_error}")
                continue  # Try next model
        
        # If all models fail
        if last_error:
            error_str = str(last_error)
            if "429" in error_str or "quota" in error_str.lower():
                return {
                    'text': f"⚠️ Free tier quota reached for today. Daily limit: {FREE_TIER_DAILY_LIMIT} requests. Please try again tomorrow or consider upgrading.",
                    'confidence': 'Low',
                    'processing_time': 0,
                    'cached': False,
                    'cooldown': 86400,  # 24 hours
                    'quota_exceeded': True
                }
            elif "404" in error_str:
                return {
                    'text': f"⚠️ Model configuration error. Please contact support.",
                    'confidence': 'Low',
                    'processing_time': 0,
                    'cached': False,
                    'cooldown': 0,
                    'quota_exceeded': False
                }
            else:
                return {
                    'text': f"⚠️ Error: {error_str[:150]}",
                    'confidence': 'Low',
                    'processing_time': 0,
                    'cached': False,
                    'cooldown': 300,  # 5 minutes
                    'quota_exceeded': False
                }
        
        return {
            'text': "⚠️ All models failed. Please try again later.",
            'confidence': 'Low',
            'processing_time': 0,
            'cached': False,
            'cooldown': 300,
            'quota_exceeded': False
        }
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'text': f"⚠️ System error: {str(e)[:150]}",
            'confidence': 'Low',
            'processing_time': 0,
            'cached': False,
            'cooldown': 300,
            'quota_exceeded': False
        }

def clean_old_files(user_id=None):
    """Clean up old temporary files and orphaned uploads"""
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        all_files = os.listdir(upload_folder)
        
        # Remove .gitkeep from the list if it exists
        if '.gitkeep' in all_files:
            all_files.remove('.gitkeep')
        
        # Get all valid file paths from database
        if user_id:
            valid_files = [img.filename for img in UserImage.query.filter_by(user_id=user_id).all()]
        else:
            valid_files = [img.filename for img in UserImage.query.all()]
        
        # Delete orphaned files
        deleted_count = 0
        for filename in all_files:
            if filename not in valid_files:
                file_path = os.path.join(upload_folder, filename)
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"Cleaned orphaned file: {filename}")
                except Exception as e:
                    print(f"Error cleaning file {filename}: {e}")
        
        if deleted_count > 0:
            print(f"Cleaned {deleted_count} orphaned files")
            
        # Also clean up Gemini cache periodically
        cleanup_gemini_cache()
            
    except Exception as e:
        print(f"Error cleaning old files: {e}")

# ============================================
# AUTHENTICATION FUNCTIONS
# ============================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# ROUTES
# ============================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login')
def login():
    if current_user.is_authenticated:
        flash('You are already logged in!', 'info')
        return redirect(url_for('dashboard'))
    
    # Generate Google OAuth URL
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={app.config['GOOGLE_CLIENT_ID']}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"redirect_uri={url_for('google_callback', _external=True, _scheme='http')}&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    return render_template('login.html', google_auth_url=google_auth_url)

@app.route('/google-callback')
def google_callback():
    try:
        # Get authorization code
        code = request.args.get('code')
        if not code:
            flash('No authorization code received', 'error')
            return redirect(url_for('login'))
        
        print(f"Received authorization code: {code[:20]}...")
        
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'code': code,
            'client_id': app.config['GOOGLE_CLIENT_ID'],
            'client_secret': app.config['GOOGLE_CLIENT_SECRET'],
            'redirect_uri': url_for('google_callback', _external=True, _scheme='http'),
            'grant_type': 'authorization_code'
        }
        
        # Make request to Google
        token_response = requests.post(token_url, data=token_data)
        
        if token_response.status_code != 200:
            flash(f'Token exchange failed: {token_response.text}', 'error')
            return redirect(url_for('login'))
        
        token_json = token_response.json()
        
        # Get ID token
        id_token_str = token_json.get('id_token')
        if not id_token_str:
            flash('No ID token received', 'error')
            return redirect(url_for('login'))
        
        # Verify ID token
        try:
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                app.config['GOOGLE_CLIENT_ID']
            )
            
            # Check if token is expired
            if idinfo['exp'] < datetime.utcnow().timestamp():
                flash('Token expired, please try again', 'error')
                return redirect(url_for('login'))
                
        except ValueError as e:
            flash(f'Invalid token: {str(e)}', 'error')
            return redirect(url_for('login'))
        
        # Get user info
        google_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', email.split('@')[0])
        profile_pic = idinfo.get('picture', '')
        
        print(f"Google Login Attempt: {email}, {name}, {google_id}")
        
        # Check if user exists
        user = User.query.filter_by(google_id=google_id).first()
        
        if not user:
            # Check if email exists with different Google ID
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                # Update existing user with new Google ID
                existing_user.google_id = google_id
                existing_user.profile_pic = profile_pic
                existing_user.name = name
                user = existing_user
                print(f"Updated existing user: {email}")
            else:
                # Create new user
                user = User(
                    google_id=google_id,
                    name=name,
                    email=email,
                    profile_pic=profile_pic,
                    is_admin=email in app.config.get('ADMIN_EMAILS', [])
                )
                db.session.add(user)
                print(f"Created new user: {email}")
        else:
            # Update user info
            user.name = name
            user.profile_pic = profile_pic
            user.last_login = datetime.utcnow()
            print(f"Updated existing user info: {email}")
        
        db.session.commit()
        
        # Login user
        login_user(user, remember=True)
        print(f"User logged in successfully: {email}")
        
        # Flash success message
        flash(f'Welcome to SoulSight AI, {name}!', 'success')
        
        # Clean up any orphaned files for this user
        clean_old_files(user.id)
        
        # Redirect to dashboard
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        print(f"Google OAuth error: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Authentication failed: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    """Logout user and clean session"""
    user_name = current_user.name
    logout_user()
    session.clear()
    flash(f'Goodbye, {user_name}! You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
@limiter.limit("30 per minute")
def dashboard():
    """User dashboard with image history"""
    try:
        # Get user's images with AI results
        user_images = UserImage.query.filter_by(user_id=current_user.id)\
            .order_by(UserImage.created_at.desc())\
            .limit(50)\
            .all()
        
        # Get favorites
        favorites = Favorite.query.filter_by(user_id=current_user.id)\
            .join(AIResult)\
            .order_by(Favorite.created_at.desc())\
            .all()
        
        # Get daily quota info
        has_quota, current_count, daily_limit = check_daily_quota(current_user.id)
        
        return render_template('dashboard.html', 
                             images=user_images, 
                             favorites=favorites,
                             quota_used=current_count,
                             quota_limit=daily_limit,
                             has_quota=has_quota)
    
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('index'))
    
@app.route('/history')
@login_required
@limiter.limit("30 per minute")
def history():
    """Separate history page with all user images"""
    try:
        # Get all user images with AI results
        user_images = UserImage.query.filter_by(user_id=current_user.id)\
            .order_by(UserImage.created_at.desc())\
            .all()
        
        # Group images with their results for easier templating
        images_with_results = []
        for image in user_images:
            results = AIResult.query.filter_by(image_id=image.id)\
                .order_by(AIResult.created_at.desc())\
                .all()
            images_with_results.append({
                'image': image,
                'results': results
            })
        
        # Get daily quota info
        has_quota, current_count, daily_limit = check_daily_quota(current_user.id)
        
        return render_template('history.html', 
                             images_with_results=images_with_results,
                             quota_used=current_count,
                             quota_limit=daily_limit,
                             has_quota=has_quota)
    
    except Exception as e:
        flash(f'Error loading history: {str(e)}', 'error')
        return redirect(url_for('dashboard'))
    
@app.route('/history/delete-all', methods=['DELETE'])
@login_required
@limiter.limit("5 per minute")  # Very restrictive for this destructive action
def delete_all_history():
    """Delete all user's images and analyses"""
    try:
        user_id = current_user.id
        
        # Get all user images to delete files
        user_images = UserImage.query.filter_by(user_id=user_id).all()
        
        # Delete all image files
        deleted_files = 0
        for image in user_images:
            if os.path.exists(image.file_path):
                os.remove(image.file_path)
                deleted_files += 1
                print(f"Deleted file: {image.file_path}")
        
        # Get counts before deletion for response
        image_count = len(user_images)
        
        # Get all results count
        result_count = 0
        for image in user_images:
            result_count += len(image.ai_results)
        
        # Delete all user's data from database
        # Delete favorites first (foreign key constraint)
        Favorite.query.filter_by(user_id=user_id).delete()
        
        # Delete all AI results for user's images
        for image in user_images:
            AIResult.query.filter_by(image_id=image.id).delete()
        
        # Delete all user images
        UserImage.query.filter_by(user_id=user_id).delete()
        
        db.session.commit()
        
        print(f"Deleted all history for user {user_id}: {image_count} images, {result_count} results, {deleted_files} files")
        
        return jsonify({
            'success': True,
            'message': f'Deleted {image_count} images and {result_count} analyses successfully',
            'stats': {
                'images_deleted': image_count,
                'results_deleted': result_count,
                'files_deleted': deleted_files
            }
        })
        
    except Exception as e:
        print(f"Delete all history error: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
@app.route('/history/export-json')
@login_required
def export_history_json():
    """Export all user history as JSON"""
    try:
        # Get all user images with results
        user_images = UserImage.query.filter_by(user_id=current_user.id)\
            .order_by(UserImage.created_at.desc())\
            .all()
        
        # Prepare data
        history_data = []
        for image in user_images:
            results = AIResult.query.filter_by(image_id=image.id)\
                .order_by(AIResult.created_at.desc())\
                .all()
            
            image_data = {
                'image_id': image.id,
                'filename': image.original_filename,
                'category': image.category,
                'upload_date': image.created_at.isoformat(),
                'file_size_mb': round(image.file_size / (1024 * 1024), 2) if image.file_size else None,
                'analyses': []
            }
            
            for result in results:
                image_data['analyses'].append({
                    'id': result.id,
                    'mode': result.mode,
                    'prompt': result.prompt,
                    'result': result.result_text,
                    'confidence': result.confidence,
                    'language': result.language,
                    'processing_time': result.processing_time,
                    'created_at': result.created_at.isoformat()
                })
            
            history_data.append(image_data)
        
        # Create JSON response
        return jsonify({
            'success': True,
            'user_id': current_user.id,
            'user_email': current_user.email,
            'export_date': datetime.utcnow().isoformat(),
            'total_images': len(history_data),
            'total_analyses': sum(len(img['analyses']) for img in history_data),
            'history': history_data
        })
        
    except Exception as e:
        print(f"Export history error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def upload_image():
    """Handle image upload"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG'}), 400
    
    try:
        # Generate unique filename
        unique_filename = generate_unique_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save file
        file.save(file_path)
        
        # Verify file was saved
        if not os.path.exists(file_path):
            return jsonify({'error': 'Failed to save image'}), 500
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Validate file size (max 16MB)
        if file_size > 16 * 1024 * 1024:
            os.remove(file_path)
            return jsonify({'error': 'File size exceeds 16MB limit'}), 400
        
        # Detect category
        category = get_image_category(file_path)
        
        # Save to database
        user_image = UserImage(
            user_id=current_user.id,
            filename=unique_filename,
            original_filename=secure_filename(file.filename),
            file_path=file_path,
            category=category,
            file_size=file_size
        )
        db.session.add(user_image)
        db.session.commit()
        
        print(f"Image uploaded successfully: {unique_filename} by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'image_id': user_image.id,
            'filename': unique_filename,
            'category': category,
            'preview_url': url_for('static', filename=f'uploads/{unique_filename}'),
            'file_size': file_size
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/process', methods=['POST'])
@login_required
@limiter.limit("2 per minute")  
def process_image():
    """Process image with AI - WITH COOLDOWN ENFORCEMENT"""
    data = request.json
    image_id = data.get('image_id')
    mode = data.get('mode', 'detailed_description')
    custom_prompt = data.get('custom_prompt', '')
    tone = data.get('tone', 'neutral')
    length = data.get('length', 'medium')
    language = data.get('language', 'en')
    question = data.get('question', '')
    
    # Validate image ownership
    user_image = UserImage.query.filter_by(id=image_id, user_id=current_user.id).first()
    if not user_image:
        return jsonify({'error': 'Image not found or access denied'}), 404
    
    # Verify image file exists
    if not os.path.exists(user_image.file_path):
        return jsonify({'error': 'Image file not found'}), 404
    
    # Check daily quota
    has_quota, current_count, daily_limit = check_daily_quota(current_user.id)
    if not has_quota:
        return jsonify({
            'error': 'quota_exceeded',
            'message': f'Daily quota exceeded. Used {current_count} of {daily_limit} requests.',
            'current_count': current_count,
            'daily_limit': daily_limit,
            'retry_after': 3600
        }), 429
    
    # Check cooldown before proceeding
    can_call, wait_time, message = check_gemini_cooldown(current_user.id)
    if not can_call:
        return jsonify({
            'error': 'cooldown',
            'message': message,
            'wait_time': wait_time,
            'retry_after': int(wait_time)
        }), 429
    
    try:
        # Process image with Gemini (now includes caching)
        result = process_image_with_gemini(
            user_image.file_path,
            mode=mode,
            custom_prompt=custom_prompt,
            tone=tone,
            length=length,
            language=language,
            question=question,
            user_id=current_user.id
        )
        
        # Check if this was a cached response
        if result.get('cached'):
            # Find existing result in database
            existing_result = AIResult.query.filter_by(
                image_id=user_image.id,
                mode=mode,
                prompt=custom_prompt if custom_prompt else question,
                tone=tone,
                length=length,
                language=language
            ).first()
            
            if existing_result:
                return jsonify({
                    'success': True,
                    'cached': True,
                    'result_id': existing_result.id,
                    'text': result['text'],
                    'confidence': result['confidence'],
                    'processing_time': result['processing_time'],
                    'mode': mode,
                    'language': language,
                    'quota_exceeded': False
                })
        
        # If quota was exceeded in the processing
        if result.get('quota_exceeded'):
            return jsonify({
                'error': 'quota_exceeded',
                'message': result['text'],
                'current_count': current_count,
                'daily_limit': daily_limit,
                'retry_after': result.get('cooldown', 3600)
            }), 429
        
        # Save new AI result to database
        ai_result = AIResult(
            image_id=user_image.id,
            mode=mode,
            prompt=custom_prompt if custom_prompt else question,
            result_text=result['text'],
            confidence=result['confidence'],
            language=language,
            tone=tone,
            length=length,
            processing_time=result['processing_time']
        )
        db.session.add(ai_result)
        db.session.commit()
        
        print(f"AI processing completed for image {image_id} by user {current_user.id} (Cached: {result.get('cached', False)})")
        
        return jsonify({
            'success': True,
            'cached': result.get('cached', False),
            'result_id': ai_result.id,
            'text': result['text'],
            'confidence': result['confidence'],
            'processing_time': result['processing_time'],
            'mode': mode,
            'language': language,
            'cooldown': result.get('cooldown', 0),
            'daily_used': current_count + 1,
            'daily_limit': daily_limit,
            'quota_exceeded': False
        })
        
    except Exception as e:
        print(f"Processing error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/favorite/<int:result_id>', methods=['POST', 'DELETE'])
@login_required
def toggle_favorite(result_id):
    """Toggle favorite status for AI result"""
    # Verify result exists and belongs to user
    ai_result = AIResult.query.join(UserImage).filter(
        AIResult.id == result_id,
        UserImage.user_id == current_user.id
    ).first()
    
    if not ai_result:
        return jsonify({'error': 'Result not found or access denied'}), 404
    
    if request.method == 'POST':
        # Check if already favorited
        existing = Favorite.query.filter_by(
            user_id=current_user.id,
            ai_result_id=result_id
        ).first()
        
        if not existing:
            favorite = Favorite(
                user_id=current_user.id,
                ai_result_id=result_id
            )
            db.session.add(favorite)
            db.session.commit()
            print(f"Added favorite: user {current_user.id} -> result {result_id}")
        
        return jsonify({'success': True, 'favorited': True})
    
    else:  # DELETE
        favorite = Favorite.query.filter_by(
            user_id=current_user.id,
            ai_result_id=result_id
        ).first()
        
        if favorite:
            db.session.delete(favorite)
            db.session.commit()
            print(f"Removed favorite: user {current_user.id} -> result {result_id}")
        
        return jsonify({'success': True, 'favorited': False})

@app.route('/result/<int:result_id>')
@login_required
def get_result(result_id):
    """Get AI result by ID"""
    result = AIResult.query.get_or_404(result_id)
    
    # Verify ownership
    if result.image.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    return jsonify({
        'text': result.result_text,
        'confidence': result.confidence,
        'mode': result.mode,
        'language': result.language,
        'created_at': result.created_at.isoformat(),
        'image_url': url_for('static', filename=f'uploads/{result.image.filename}')
    })

@app.route('/delete/<int:image_id>', methods=['DELETE'])
@login_required
def delete_image(image_id):
    """Delete an image and all related data"""
    user_image = UserImage.query.filter_by(id=image_id, user_id=current_user.id).first()
    if not user_image:
        return jsonify({'error': 'Image not found or access denied'}), 404
    
    try:
        # Get the file path before deleting from database
        file_path = user_image.file_path
        
        # Delete from database (cascade will delete related records)
        db.session.delete(user_image)
        db.session.commit()
        
        # Delete file from filesystem
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
        else:
            print(f"File not found (already deleted?): {file_path}")
        
        # Return success with image ID for UI removal
        return jsonify({
            'success': True,
            'image_id': image_id,
            'message': 'Image and all related data deleted successfully'
        })
        
    except Exception as e:
        print(f"Delete error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/delete-account', methods=['DELETE'])
@login_required
def delete_account():
    """Delete user account and all associated data"""
    try:
        user_id = current_user.id
        user_email = current_user.email
        
        # Get all user images to delete files
        user_images = UserImage.query.filter_by(user_id=user_id).all()
        
        # Delete image files
        for image in user_images:
            if os.path.exists(image.file_path):
                os.remove(image.file_path)
        
        # Logout user
        logout_user()
        
        # Delete user from database (cascade will delete all related data)
        user = User.query.get(user_id)
        db.session.delete(user)
        db.session.commit()
        
        # Clear session
        session.clear()
        
        print(f"Deleted account for user {user_id} ({user_email})")
        
        return jsonify({
            'success': True,
            'message': 'Account and all associated data deleted successfully'
        })
        
    except Exception as e:
        print(f"Account deletion error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/text-to-speech/<int:result_id>')
@login_required
@limiter.limit("30 per minute")
def text_to_speech(result_id):
    """Convert AI result text to speech"""
    result = AIResult.query.get_or_404(result_id)
    
    # Verify ownership
    if result.image.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    try:
        # Create temporary file for audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            # Generate speech
            tts = gTTS(text=result.result_text, lang=result.language)
            tts.save(tmp.name)
            
            # Return audio file
            return send_file(
                tmp.name,
                mimetype='audio/mpeg',
                as_attachment=True,
                download_name=f'soulsight-{result_id}.mp3'
            )
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/<int:result_id>/<format>')
@login_required
def export_result(result_id, format):
    """Export AI result as TXT or PDF"""
    result = AIResult.query.get_or_404(result_id)
    
    # Verify ownership
    if result.image.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    if format == 'txt':
        # Export as text file
        output = io.StringIO()
        output.write(f"SoulSight AI Result\n")
        output.write(f"===================\n\n")
        output.write(f"Mode: {result.mode}\n")
        output.write(f"Confidence: {result.confidence}\n")
        output.write(f"Language: {result.language}\n")
        output.write(f"Generated: {result.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        output.write(result.result_text)
        
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/plain',
            as_attachment=True,
            download_name=f'soulsight-{result_id}.txt'
        )
    
    elif format == 'pdf':
        # Export as PDF
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        
        # Add content
        pdf.setTitle(f"SoulSight AI Result - {result_id}")
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, 750, "SoulSight AI Result")
        
        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, 730, f"Mode: {result.mode}")
        pdf.drawString(50, 715, f"Confidence: {result.confidence}")
        pdf.drawString(50, 700, f"Language: {result.language}")
        pdf.drawString(50, 685, f"Generated: {result.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Add result text
        pdf.setFont("Helvetica", 12)
        text = pdf.beginText(50, 650)
        text.setFont("Helvetica", 12)
        text.setLeading(14)
        
        # Split text into lines
        lines = []
        words = result.result_text.split()
        line = ""
        for word in words:
            if len(line) + len(word) < 70:
                line += word + " "
            else:
                lines.append(line)
                line = word + " "
        if line:
            lines.append(line)
        
        for line in lines[:30]:  # Limit to first 30 lines
            text.textLine(line)
        
        pdf.drawText(text)
        pdf.save()
        
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'soulsight-{result_id}.pdf'
        )
    
    else:
        abort(400)

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    try:
        # Get statistics
        total_users = User.query.count()
        total_images = UserImage.query.count()
        total_results = AIResult.query.count()
        
        # Most used modes
        mode_stats = db.session.query(
            AIResult.mode,
            db.func.count(AIResult.id).label('count')
        ).group_by(AIResult.mode).order_by(db.desc('count')).all()
        
        # Recent activity
        recent_images = UserImage.query\
            .order_by(UserImage.created_at.desc())\
            .limit(10)\
            .all()
        
        # Gemini usage stats
        gemini_status = get_gemini_status()
        
        return render_template('admin.html',
                             total_users=total_users,
                             total_images=total_images,
                             total_results=total_results,
                             mode_stats=mode_stats,
                             recent_images=recent_images,
                             gemini_status=gemini_status)
    
    except Exception as e:
        flash(f'Error loading admin dashboard: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/admin/delete-user/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """Admin: Delete user account"""
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    user = User.query.get_or_404(user_id)
    
    try:
        user_email = user.email
        
        # Get all user images to delete files
        user_images = UserImage.query.filter_by(user_id=user_id).all()
        
        # Delete image files
        for image in user_images:
            if os.path.exists(image.file_path):
                os.remove(image.file_path)
        
        # Delete from database (cascade will delete all related records)
        db.session.delete(user)
        db.session.commit()
        
        print(f"Admin deleted user {user_id} ({user_email})")
        
        return jsonify({'success': True, 'message': f'User {user_email} deleted successfully'})
        
    except Exception as e:
        print(f"Admin delete error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================
# INFO PAGES
# ============================================

@app.route('/privacy')
def privacy_policy():
    return render_template('info/privacy.html')

@app.route('/terms')
def terms_of_service():
    return render_template('info/terms.html')

@app.route('/about')
def about():
    return render_template('info/about.html')

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(400)
def bad_request_error(error):
    return render_template('error/400.html'), 400

@app.errorhandler(401)
def unauthorized_error(error):
    return render_template('error/401.html'), 401

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('error/403.html'), 403

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error/404.html'), 404

@app.errorhandler(405)
def method_not_allowed_error(error):
    return render_template('error/405.html'), 405

@app.errorhandler(408)
def request_timeout_error(error):
    return render_template('error/408.html'), 408

@app.errorhandler(429)
def too_many_requests_error(error):
    return render_template('error/429.html'), 429

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error/500.html'), 500

@app.errorhandler(503)
def service_unavailable_error(error):
    return render_template('error/503.html'), 503

# ============================================
# GEMINI STATUS AND MANAGEMENT
# ============================================

def get_gemini_status():
    """Get current Gemini API status for monitoring"""
    with gemini_cooldown_lock:
        now = datetime.now()
        time_since_last_call = (now - gemini_last_call_time).total_seconds()
        
        # Get daily quota info
        with gemini_daily_lock:
            total_daily_calls = sum(gemini_daily_counts.values())
        
        return {
            'last_call_time': gemini_last_call_time.isoformat() if gemini_last_call_time > datetime.min else 'Never',
            'seconds_since_last_call': time_since_last_call,
            'cooldown_active': time_since_last_call < FREE_TIER_COOLDOWN,
            'active_users': len(gemini_user_cooldowns),
            'cache_size': len(gemini_request_cache),
            'cooldown_seconds': FREE_TIER_COOLDOWN,
            'daily_reset_date': gemini_daily_reset_date.isoformat(),
            'total_daily_calls': total_daily_calls,
            'daily_limit': FREE_TIER_DAILY_LIMIT,
            'user_breakdown': gemini_daily_counts
        }

@app.route('/api/gemini-status')
@login_required
def gemini_status():
    """Get current Gemini API status"""
    status = get_gemini_status()
    return jsonify(status)

@app.route('/api/user-quota')
@login_required
def user_quota():
    """Get current user's quota status"""
    has_quota, current_count, daily_limit = check_daily_quota(current_user.id)
    can_call, wait_time, message = check_gemini_cooldown(current_user.id)
    
    return jsonify({
        'user_id': current_user.id,
        'daily_used': current_count,
        'daily_limit': daily_limit,
        'has_quota': has_quota,
        'can_call': can_call,
        'wait_time': wait_time,
        'message': message,
        'cooldown_seconds': FREE_TIER_COOLDOWN
    })

@app.route('/api/reset-cooldown', methods=['POST'])
@login_required
@admin_required
def reset_cooldown():
    """Admin: Reset Gemini cooldown manually"""
    with gemini_cooldown_lock:
        global gemini_last_call_time
        old_time = gemini_last_call_time
        gemini_last_call_time = datetime.min
        gemini_user_cooldowns.clear()
        
        print(f"Admin {current_user.email} reset cooldown from {old_time}")
        
        return jsonify({
            'success': True,
            'message': 'Cooldown reset successfully',
            'previous_last_call': old_time.isoformat() if old_time > datetime.min else 'Never'
        })

def cleanup_gemini_cache():
    """Clean up old cache entries to prevent memory issues"""
    with gemini_cooldown_lock:
        # Simple cleanup: if cache too big, clear it
        if len(gemini_request_cache) > 1000:
            print(f"Cleaning Gemini cache: {len(gemini_request_cache)} entries")
            gemini_request_cache.clear()
            print("Gemini cache cleared")
        
        # Clean up old user cooldowns (older than 1 hour)
        now = datetime.now()
        users_to_remove = []
        for user_id, last_call in gemini_user_cooldowns.items():
            if (now - last_call).total_seconds() > 3600:  # 1 hour
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del gemini_user_cooldowns[user_id]
        
        if users_to_remove:
            print(f"Cleaned {len(users_to_remove)} old user cooldowns")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def generate_unique_filename(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    return unique_filename

def init_db():
    """Initialize database and create tables"""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("Database tables created successfully")
            
            # Check if admin user exists
            admin_email = app.config.get('ADMIN_EMAILS', [''])[0]
            if admin_email:
                admin = User.query.filter_by(email=admin_email).first()
                if not admin:
                    admin = User(
                        google_id='admin_' + uuid.uuid4().hex[:20],
                        name='Admin',
                        email=admin_email,
                        profile_pic='',
                        is_admin=True
                    )
                    db.session.add(admin)
                    db.session.commit()
                    print(f"Admin user created: {admin_email}")
                else:
                    print(f"Admin user already exists: {admin_email}")
            
            # Clean orphaned files on startup
            clean_old_files()
            
        except Exception as e:
            print(f"Database initialization error: {e}")
            import traceback
            traceback.print_exc()

@app.route('/debug/models')
def debug_models():
    """List available Gemini models"""
    try:
        available_models = get_available_gemini_models()
        
        # Also show current configuration
        current_config = {
            'primary_model': app.config.get('GEMINI_MODEL'),
            'fallback_models': app.config.get('GEMINI_FALLBACK_MODELS', []),
            'api_key_set': bool(app.config.get('GEMINI_API_KEY')),
            'cooldown_seconds': FREE_TIER_COOLDOWN,
            'daily_limit': FREE_TIER_DAILY_LIMIT
        }
        
        return jsonify({
            'available_models': available_models,
            'current_config': current_config,
            'total_available': len(available_models),
            'suggestion': 'Use gemini-2.0-flash or gemini-flash-latest for free tier'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test-model/<model_name>')
@login_required
def test_model(model_name):
    """Test if a specific Gemini model works"""
    try:
        # Clean model name
        if model_name.startswith('models/'):
            model_name_clean = model_name.replace('models/', '')
        else:
            model_name_clean = model_name
        
        print(f"Testing model: {model_name_clean}")
        
        # Try to create model
        model = genai.GenerativeModel(model_name_clean)
        
        # Simple test prompt
        test_prompt = "Hello, are you working?"
        
        try:
            response = model.generate_content(test_prompt)
            return jsonify({
                'success': True,
                'model': model_name_clean,
                'response': response.text,
                'message': 'Model is working correctly'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'model': model_name_clean,
                'error': str(e),
                'message': 'Model failed'
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting SoulSight AI...")
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"Free Tier Settings: {FREE_TIER_DAILY_LIMIT} requests/day, {FREE_TIER_COOLDOWN}s cooldown")
    
    # Initialize database
    init_db()
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)