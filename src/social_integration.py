"""
Social Integration - Automatically creates social posts for user achievements
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from supabase import Client
from .social_service import SocialService
from .social_models import CreatePostRequest, PostType, PostVisibility

logger = logging.getLogger(__name__)

class SocialIntegration:
    """Handles automatic social post creation for user achievements"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.social_service = SocialService(supabase_client)
    
    def create_achievement_post(self, user_name: str, achievement_name: str, description: str, points: int, icon: str) -> Optional[str]:
        """Create a social post for an achievement"""
        try:
            post_data = CreatePostRequest(
                post_type=PostType.ACHIEVEMENT,
                title=f"🎉 {achievement_name} Unlocked!",
                content=f"I just unlocked the '{achievement_name}' achievement! {description} (+{points} points)",
                visibility=PostVisibility.PUBLIC,
                metadata={
                    "achievement_name": achievement_name,
                    "points_earned": points,
                    "icon": icon,
                    "auto_generated": True
                }
            )
            
            post = self.social_service.create_post(user_name, post_data)
            logger.info(f"Created achievement post for {user_name}: {achievement_name}")
            return post.id
            
        except Exception as e:
            logger.error(f"Error creating achievement post for {user_name}: {str(e)}")
            return None
    
    def create_level_up_post(self, user_name: str, old_level: int, new_level: int) -> Optional[str]:
        """Create a social post for leveling up"""
        try:
            post_data = CreatePostRequest(
                post_type=PostType.LEVEL_UP,
                title=f"🚀 Level Up! {old_level} → {new_level}",
                content=f"I just leveled up from {old_level} to {new_level}! My language skills are improving! 💪",
                visibility=PostVisibility.PUBLIC,
                metadata={
                    "old_level": old_level,
                    "new_level": new_level,
                    "auto_generated": True
                }
            )
            
            post = self.social_service.create_post(user_name, post_data)
            logger.info(f"Created level up post for {user_name}: {old_level} → {new_level}")
            return post.id
            
        except Exception as e:
            logger.error(f"Error creating level up post for {user_name}: {str(e)}")
            return None
    
    def create_streak_post(self, user_name: str, streak_days: int) -> Optional[str]:
        """Create a social post for streak milestones"""
        try:
            if streak_days in [7, 14, 30, 60, 100]:  # Only post for significant milestones
                post_data = CreatePostRequest(
                    post_type=PostType.STREAK,
                    title=f"🔥 {streak_days} Day Streak!",
                    content=f"I've been practicing for {streak_days} days straight! Consistency is key to language learning success! 🎯",
                    visibility=PostVisibility.PUBLIC,
                    metadata={
                        "streak_days": streak_days,
                        "auto_generated": True
                    }
                )
                
                post = self.social_service.create_post(user_name, post_data)
                logger.info(f"Created streak post for {user_name}: {streak_days} days")
                return post.id
                
        except Exception as e:
            logger.error(f"Error creating streak post for {user_name}: {str(e)}")
            return None
    
    def create_conversation_post(self, user_name: str, partner_name: str, conversation_highlights: str) -> Optional[str]:
        """Create a social post for interesting conversation highlights"""
        try:
            post_data = CreatePostRequest(
                post_type=PostType.CONVERSATION,
                title=f"💬 Great conversation with {partner_name}!",
                content=f"I just had an amazing conversation with {partner_name}! {conversation_highlights}",
                visibility=PostVisibility.PUBLIC,
                metadata={
                    "partner_name": partner_name,
                    "auto_generated": True
                }
            )
            
            post = self.social_service.create_post(user_name, post_data)
            logger.info(f"Created conversation post for {user_name} with {partner_name}")
            return post.id
            
        except Exception as e:
            logger.error(f"Error creating conversation post for {user_name}: {str(e)}")
            return None
    
    def create_milestone_post(self, user_name: str, milestone_type: str, milestone_value: int, description: str) -> Optional[str]:
        """Create a social post for reaching milestones"""
        try:
            post_data = CreatePostRequest(
                post_type=PostType.MILESTONE,
                title=f"🏆 {milestone_type} Milestone Reached!",
                content=f"I just reached {milestone_value} {milestone_type}! {description}",
                visibility=PostVisibility.PUBLIC,
                metadata={
                    "milestone_type": milestone_type,
                    "milestone_value": milestone_value,
                    "auto_generated": True
                }
            )
            
            post = self.social_service.create_post(user_name, post_data)
            logger.info(f"Created milestone post for {user_name}: {milestone_type} = {milestone_value}")
            return post.id
            
        except Exception as e:
            logger.error(f"Error creating milestone post for {user_name}: {str(e)}")
            return None
    
    def check_and_create_auto_posts(self, user_name: str, user_data: Dict[str, Any]) -> None:
        """Check user data and create automatic social posts for achievements"""
        try:
            # Check for level up
            current_level = user_data.get("user_level", "A1")
            level_mapping = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
            numeric_level = level_mapping.get(current_level, 1)
            
            # Check if this is a new level (you might want to track previous level)
            # For now, we'll create a post if they're at a higher level
            if numeric_level >= 3:  # B1 or higher
                self.create_level_up_post(user_name, numeric_level - 1, numeric_level)
            
            # Check for streak milestones
            streak_days = user_data.get("streak_days", 0)
            if streak_days > 0:
                self.create_streak_post(user_name, streak_days)
            
            # Check for conversation milestones
            total_conversations = user_data.get("total_conversations", 0)
            if total_conversations > 0 and total_conversations % 10 == 0:  # Every 10 conversations
                self.create_milestone_post(
                    user_name, 
                    "conversations", 
                    total_conversations, 
                    f"Completed {total_conversations} conversations!"
                )
            
            # Check for message milestones
            total_messages = user_data.get("total_messages", 0)
            if total_messages > 0 and total_messages % 50 == 0:  # Every 50 messages
                self.create_milestone_post(
                    user_name, 
                    "messages", 
                    total_messages, 
                    f"Sent {total_messages} messages!"
                )
                
        except Exception as e:
            logger.error(f"Error checking auto posts for {user_name}: {str(e)}")
    
    def create_welcome_post(self, user_name: str) -> Optional[str]:
        """Create a welcome post for new users"""
        try:
            post_data = CreatePostRequest(
                post_type=PostType.MILESTONE,
                title="🌟 Welcome to PolyNot!",
                content=f"Hello everyone! I just joined PolyNot and I'm excited to start my language learning journey! 🚀",
                visibility=PostVisibility.PUBLIC,
                metadata={
                    "welcome_post": True,
                    "auto_generated": True
                }
            )
            
            post = self.social_service.create_post(user_name, post_data)
            logger.info(f"Created welcome post for {user_name}")
            return post.id
            
        except Exception as e:
            logger.error(f"Error creating welcome post for {user_name}: {str(e)}")
            return None
