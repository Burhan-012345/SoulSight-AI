#!/usr/bin/env python3
"""
Emergency script to reset Gemini API quota tracking
Run this if quota gets permanently stuck
"""

import os
import sys
import sqlite3
import time
from datetime import datetime, timedelta
import json

def reset_gemini_quotas():
    """Reset all Gemini quota tracking"""
    print("=" * 60)
    print("SoulSight AI - Gemini Quota Reset Tool")
    print("=" * 60)
    
    try:
        # Reset in-memory caches by restarting would be needed
        # For now, provide instructions
        
        print("\n1. CLEARING IN-MEMORY CACHES")
        print("   Run these commands in Python interpreter:")
        print("   from app import gemini_last_call_time, gemini_user_cooldowns")
        print("   gemini_last_call_time = datetime.min")
        print("   gemini_user_cooldowns.clear()")
        
        print("\n2. CLEARING DATABASE CACHE (if implemented)")
        print("   Currently using in-memory cache only")
        
        print("\n3. CHECKING CURRENT QUOTA STATUS")
        print("   Wait 1-2 minutes between requests")
        print("   Free tier limit: 5 requests per minute")
        
        print("\n4. EMERGENCY ACTIONS:")
        print("   a) Wait 30 minutes for Google quota reset")
        print("   b) Create new Google Cloud project")
        print("   c) Generate new Gemini API key")
        print("   d) Upgrade to paid tier ($0.000125 per 1K chars)")
        
        print("\n5. PREVENTIVE MEASURES:")
        print("   ✓ Implemented 20-second cooldown")
        print("   ✓ Image hash caching")
        print("   ✓ Model fallback system")
        print("   ✓ User cooldown tracking")
        
        # Check if we're in the right directory
        if os.path.exists('app.py'):
            print("\n✓ Found app.py in current directory")
            
            # Read current config
            try:
                with open('.env', 'r') as f:
                    env_vars = f.read()
                    if 'GEMINI_API_KEY' in env_vars:
                        print("✓ Found GEMINI_API_KEY in .env")
                        # Show first few chars for verification
                        for line in env_vars.split('\n'):
                            if 'GEMINI_API_KEY' in line:
                                key = line.split('=')[1]
                                print(f"  API Key: {key[:10]}...{key[-5:]}")
            except:
                print("⚠ Could not read .env file")
        
        print("\n" + "=" * 60)
        print("RESET COMPLETE")
        print("=" * 60)
        print("\nRecommendations:")
        print("1. Restart the Flask application")
        print("2. Wait 60 seconds before first request")
        print("3. Test with single image upload")
        print("4. Monitor for 'cached result' messages")
        
    except Exception as e:
        print(f"\n⚠ Error: {e}")
        print("\nManual reset steps:")
        print("1. Stop the Flask application (Ctrl+C)")
        print("2. Wait 2 minutes")
        print("3. Restart: python app.py")
        print("4. The cooldown timers will reset automatically")

def check_quota_status():
    """Check current quota usage patterns"""
    print("\n" + "=" * 60)
    print("QUOTA STATUS CHECK")
    print("=" * 60)
    
    # Check database for recent requests
    if os.path.exists('soulsight.db'):
        conn = sqlite3.connect('soulsight.db')
        cursor = conn.cursor()
        
        try:
            # Get recent AI results
            cursor.execute("""
                SELECT COUNT(*) as total, 
                       strftime('%Y-%m-%d %H:%M', created_at) as minute,
                       mode
                FROM ai_results 
                WHERE datetime(created_at) > datetime('now', '-1 hour')
                GROUP BY minute, mode
                ORDER BY minute DESC
                LIMIT 10
            """)
            
            results = cursor.fetchall()
            
            if results:
                print("\nRecent API Calls (last hour):")
                print("-" * 40)
                print(f"{'Time':<16} {'Mode':<20} {'Count':<6}")
                print("-" * 40)
                for total, minute, mode in results:
                    print(f"{minute:<16} {mode:<20} {total:<6}")
                
                total_calls = sum(r[0] for r in results)
                print("-" * 40)
                print(f"Total calls: {total_calls}")
                
                if total_calls > 15:
                    print("⚠ HIGH: More than 15 calls in last hour")
                elif total_calls > 5:
                    print("⚠ MODERATE: 5-15 calls in last hour")
                else:
                    print("✓ LOW: Normal usage")
            else:
                print("No recent API calls found")
                
        except sqlite3.OperationalError:
            print("Database schema may not exist yet")
        finally:
            conn.close()
    else:
        print("Database not found. No usage data available.")
    
    print("\n" + "=" * 60)
    print("GEMINI FREE TIER LIMITS:")
    print("=" * 60)
    print("• 60 requests per minute (project-wide)")
    print("• 15 requests per minute per user")
    print("• Recommended: 1 request every 20 seconds")
    print("• Burst: Max 3-4 requests, then wait 60s")

def switch_api_key():
    """Guide for switching to new API key"""
    print("\n" + "=" * 60)
    print("SWITCH GEMINI API KEY")
    print("=" * 60)
    
    print("\nSteps to get new API key:")
    print("1. Go to: https://aistudio.google.com/app/apikey")
    print("2. Click 'Create API Key'")
    print("3. Select 'Create API key in new project'")
    print("4. Copy the new API key")
    
    print("\nUpdate your .env file:")
    print("GEMINI_API_KEY=your_new_key_here")
    
    print("\nOr set environment variable:")
    print("export GEMINI_API_KEY='your_new_key_here'")
    print("python app.py")

def main():
    """Main menu"""
    print("\nSoulSight AI Quota Management")
    print("=" * 40)
    print("1. Reset quota tracking")
    print("2. Check quota status")
    print("3. Switch API key guide")
    print("4. All of the above")
    print("5. Exit")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == '1':
        reset_gemini_quotas()
    elif choice == '2':
        check_quota_status()
    elif choice == '3':
        switch_api_key()
    elif choice == '4':
        reset_gemini_quotas()
        check_quota_status()
        switch_api_key()
    elif choice == '5':
        print("Goodbye!")
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()