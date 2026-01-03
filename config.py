import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///soulsight.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

    GEMINI_MODEL = 'gemini-2.0-flash' 
    GEMINI_FALLBACK_MODELS = ['gemini-flash-latest']  

    GEMINI_COOLDOWN_SECONDS = 60 
    GEMINI_MAX_CALLS_PER_MINUTE = 1 
    GEMINI_DAILY_LIMIT = 15  
    
    GEMINI_COOLDOWN_SECONDS = 20  
    GEMINI_MAX_CALLS_PER_MINUTE = 5
    
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    RATELIMIT_DEFAULT = "100 per hour"
    
    ADMIN_EMAILS = ['admin@soulsight.ai']
    
    SESSION_COOKIE_SECURE = False  
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400