#!/usr/bin/env python3
"""
Test script for the new authentication system with password support.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_user_creation_with_password():
    """Test creating a user with password."""
    print("=== Testing User Creation with Password ===")
    
    user_data = {
        "user_name": "testuser_auth",
        "email": "tan+1@polynot.ai",
        "password": "SecurePassword123!",
        "user_level": "A2",
        "target_language": "English",
        "first_name": "Test",
        "last_name": "User",
        "native_language": "Spanish",
        "country": "Spain",
        "interests": "technology, music, travel",
        "bio": "Learning English for work",
        "learning_goals": "Improve business communication",
        "preferred_topics": "business, technology, travel"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/users/", json=user_data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 201:
            user = response.json()
            print("✅ User created successfully!")
            print(f"Username: {user['user_name']}")
            print(f"Email: {user['email']}")
            return user_data
        else:
            print(f"❌ Failed to create user: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return None

def test_login():
    """Test user login."""
    print("\n=== Testing User Login ===")
    
    login_data = {
        "email": "tan+1@polynot.ai",
        "password": "SecurePassword123!"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Login successful!")
            print(f"Username: {result['user']['user_name']}")
            print(f"Access Token: {result['access_token'][:50]}...")
            print(f"Expires At: {result['expires_at']}")
            return result['access_token']
        else:
            print(f"❌ Login failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error during login: {e}")
        return None

def test_login_with_wrong_password():
    """Test login with wrong password."""
    print("\n=== Testing Login with Wrong Password ===")
    
    login_data = {
        "email": "tan+1@polynot.ai",
        "password": "WrongPassword123!"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✅ Correctly rejected wrong password!")
        else:
            print(f"❌ Should have rejected wrong password: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during login test: {e}")

def test_login_with_nonexistent_user():
    """Test login with nonexistent user."""
    print("\n=== Testing Login with Nonexistent User ===")
    
    login_data = {
        "email": "tan+2@polynot.ai",
        "password": "SecurePassword123!"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✅ Correctly rejected nonexistent user!")
        else:
            print(f"❌ Should have rejected nonexistent user: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during login test: {e}")

def test_logout(access_token):
    """Test user logout."""
    print("\n=== Testing User Logout ===")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        response = requests.post(f"{BASE_URL}/auth/logout", headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Logout successful!")
        else:
            print(f"❌ Logout failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during logout: {e}")

def test_password_reset():
    """Test password reset functionality."""
    print("\n=== Testing Password Reset ===")
    
    try:
        response = requests.post(f"{BASE_URL}/auth/reset-password", json={"email": "tan+1@polynot.ai"})
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Password reset email sent!")
        else:
            print(f"❌ Password reset failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during password reset: {e}")

def test_user_creation_validation():
    """Test user creation validation."""
    print("\n=== Testing User Creation Validation ===")
    
    # Test without password
    user_data_no_password = {
        "user_name": "testuser_nopass",
        "email": "tan+3@polynot.ai",
        "user_level": "A2",
        "target_language": "English"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/users/", json=user_data_no_password)
        print(f"No password - Status Code: {response.status_code}")
        
        if response.status_code == 422:
            print("✅ Correctly rejected user without password!")
        else:
            print(f"❌ Should have rejected user without password: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing no password: {e}")
    
    # Test with short password
    user_data_short_password = {
        "user_name": "testuser_shortpass",
        "email": "tan+4@polynot.ai",
        "password": "123",
        "user_level": "A2",
        "target_language": "English"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/users/", json=user_data_short_password)
        print(f"Short password - Status Code: {response.status_code}")
        
        if response.status_code == 422:
            print("✅ Correctly rejected user with short password!")
        else:
            print(f"❌ Should have rejected user with short password: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing short password: {e}")

def main():
    """Run all authentication tests."""
    print("🚀 Starting Authentication System Tests\n")
    
    # Test user creation with password
    user_data = test_user_creation_with_password()
    
    if user_data:
        # Wait a moment for the user to be fully created
        time.sleep(2)
        
        # Test login
        access_token = test_login()
        
        if access_token:
            # Test logout
            test_logout(access_token)
        
        # Test login with wrong password
        test_login_with_wrong_password()
        
        # Test login with nonexistent user
        test_login_with_nonexistent_user()
        
        # Test password reset
        test_password_reset()
    
    # Test validation
    test_user_creation_validation()
    
    print("\n🎉 Authentication system tests completed!")

if __name__ == "__main__":
    main()
