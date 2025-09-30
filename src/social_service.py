"""
Social Service - Backend API service for social features
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from supabase import Client
from .social_models import (
    CreatePostRequest, PostResponse, CommentRequest, CommentResponse,
    NewsFeedRequest, NewsFeedResponse, SocialUserProfileResponse, 
    PointsSummary, LeaderboardResponse, LeaderboardEntry, AchievementResponse,
    POINT_VALUES, LEVEL_THRESHOLDS, BADGES
)

logger = logging.getLogger(__name__)

class SocialService:
    """Backend service for handling social features"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        # Cache for user ID lookups to avoid repeated database queries
        self._user_id_cache = {}
    
    def _get_user_id(self, user_name: str) -> Optional[str]:
        """Get user_id from user_name with caching and case-insensitive lookup"""
        # Check cache first
        if user_name in self._user_id_cache:
            return self._user_id_cache[user_name]
        
        try:
            # First try exact match
            response = self.supabase.table("profiles").select("id").eq("user_name", user_name).execute()
            if response.data:
                user_id = response.data[0]["id"]
                # Cache the result
                self._user_id_cache[user_name] = user_id
                return user_id
            
            # If no exact match, try case-insensitive lookup
            response = self.supabase.table("profiles").select("id, user_name").ilike("user_name", user_name).execute()
            if response.data:
                user_id = response.data[0]["id"]
                actual_user_name = response.data[0]["user_name"]
                # Cache with both the actual and requested username
                self._user_id_cache[actual_user_name] = user_id
                self._user_id_cache[user_name] = user_id
                return user_id
            
            # Cache None for non-existent users to avoid repeated queries
            self._user_id_cache[user_name] = None
            return None
        except Exception as e:
            logger.error(f"Error getting user_id for {user_name}: {str(e)}")
            return None
    
    def _get_user_name(self, user_id: str) -> Optional[str]:
        """Get user_name from user_id"""
        try:
            response = self.supabase.table("profiles").select("user_name").eq("id", user_id).execute()
            if response.data:
                return response.data[0]["user_name"]
            return None
        except Exception as e:
            logger.error(f"Error getting user_name for {user_id}: {str(e)}")
            return None
    
    def _get_user_data(self, user_name: str) -> Optional[Dict[str, Any]]:
        """Get user data (id, avatar_url, user_level) in a single query with case-insensitive lookup"""
        try:
            # First try exact match
            response = self.supabase.table("profiles").select("id, avatar_url, user_level").eq("user_name", user_name).execute()
            if response.data:
                user_data = response.data[0]
                # Cache the user_id
                self._user_id_cache[user_name] = user_data["id"]
                return user_data
            
            # If no exact match, try case-insensitive lookup
            response = self.supabase.table("profiles").select("id, avatar_url, user_level, user_name").ilike("user_name", user_name).execute()
            if response.data:
                user_data = response.data[0]
                actual_user_name = user_data["user_name"]
                # Cache with the actual username
                self._user_id_cache[actual_user_name] = user_data["id"]
                self._user_id_cache[user_name] = user_data["id"]  # Also cache with requested name
                return user_data
            
            # Cache None for non-existent users
            self._user_id_cache[user_name] = None
            return None
        except Exception as e:
            logger.error(f"Error getting user data for {user_name}: {str(e)}")
            return None
    
    # ============================================================================
    # Post Management
    # ============================================================================
    
    def create_post(self, user_id: str, post_data: CreatePostRequest) -> PostResponse:
        """Create a new social post"""
        try:
            # Validate user_id exists
            user_response = self.supabase.table("profiles").select("user_name").eq("id", user_id).execute()
            if not user_response.data:
                raise Exception(f"User with ID {user_id} not found")
            
            user_name = user_response.data[0]["user_name"]
            
            # Create post
            post_id = str(uuid.uuid4())
            post_record = {
                "id": post_id,
                "user_id": user_id,
                "post_type": post_data.post_type.value,
                "title": post_data.title,
                "content": post_data.content,
                "visibility": post_data.visibility.value,
                "points_earned": POINT_VALUES.get("post_created", 10),
                "metadata": post_data.metadata or {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            response = self.supabase.table("social_posts").insert(post_record).execute()
            if not response.data:
                raise Exception("Failed to create post")
            
            # Award points to user (with error handling)
            try:
                self._award_points(user_name, "post_created", f"Created a {post_data.post_type.value} post", post_id)
            except Exception as e:
                logger.warning(f"Failed to award points for post creation: {str(e)}")
            
            # Check for first post achievement (with error handling)
            try:
                self._check_first_post_achievement(user_name)
            except Exception as e:
                logger.warning(f"Failed to check first post achievement: {str(e)}")
            
            return self._format_post_response(response.data[0], user_name)
            
        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            raise
    
    def get_post(self, post_id: str, current_user: Optional[str] = None) -> Optional[PostResponse]:
        """Get a specific post"""
        try:
            response = self.supabase.table("social_posts").select(
                "*, profiles!inner(user_name, avatar_url)"
            ).eq("id", post_id).eq("is_active", True).execute()
            if not response.data:
                return None
            
            # Get the actual user_name from the post's user_id via JOIN
            post = response.data[0]
            user_name = post.get("profiles", {}).get("user_name", "Unknown")
            # Add avatar_url to post data for _format_post_response
            post["author_avatar"] = post.get("profiles", {}).get("avatar_url")
            return self._format_post_response(post, user_name)
            
        except Exception as e:
            logger.error(f"Error getting post: {str(e)}")
            return None
    
    def update_post(self, post_id: str, user_name: str, update_data: Dict[str, Any]) -> Optional[PostResponse]:
        """Update a post (only by owner)"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return None
            
            # Check if user owns the post
            post_response = self.supabase.table("social_posts").select("user_id").eq("id", post_id).eq("is_active", True).execute()
            if not post_response.data or post_response.data[0]["user_id"] != user_id:
                return None
            
            # Prepare update data
            update_fields = {
                "updated_at": datetime.now().isoformat()
            }
            
            # Only update fields that are provided
            if "title" in update_data:
                update_fields["title"] = update_data["title"]
            if "content" in update_data:
                update_fields["content"] = update_data["content"]
            if "visibility" in update_data:
                update_fields["visibility"] = update_data["visibility"]
            if "metadata" in update_data:
                update_fields["metadata"] = update_data["metadata"]
            
            # Update the post
            response = self.supabase.table("social_posts").update(update_fields).eq("id", post_id).execute()
            if not response.data:
                return None
            
            # Return updated post
            updated_post = response.data[0]
            return self._format_post_response(updated_post, user_name)
            
        except Exception as e:
            logger.error(f"Error updating post: {str(e)}")
            return None

    def delete_post(self, post_id: str, user_name: str) -> bool:
        """Delete a post (soft delete)"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return False
            
            # Check if user owns the post
            post_response = self.supabase.table("social_posts").select("user_id").eq("id", post_id).execute()
            if not post_response.data or post_response.data[0]["user_id"] != user_id:
                return False
            
            # Soft delete
            self.supabase.table("social_posts").update({
                "is_active": False,
                "updated_at": datetime.now().isoformat()
            }).eq("id", post_id).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting post: {str(e)}")
            return False
    
    # ============================================================================
    # News Feed
    # ============================================================================
    
    def get_news_feed(self, user_id: str, request: NewsFeedRequest) -> NewsFeedResponse:
        """Get personalized news feed for user"""
        try:
            # Validate user_id exists and get user data in one query
            user_response = self.supabase.table("profiles").select("user_name, user_level").eq("id", user_id).execute()
            if not user_response.data:
                # Return empty feed for non-existent users instead of throwing error
                logger.warning(f"User with ID {user_id} not found, returning empty feed")
                return NewsFeedResponse(
                    posts=[],
                    total_posts=0,
                    current_page=request.page,
                    total_pages=0,
                    has_next=False
                )
            
            user_name = user_response.data[0]["user_name"]
            user_level = user_response.data[0]["user_level"]
            
            # Build query with JOIN to get user_name directly
            query = self.supabase.table("social_posts").select(
                "*, profiles!inner(user_name, avatar_url)"
            ).eq("is_active", True)
            
            # Apply filters
            if request.post_types:
                query = query.in_("post_type", [pt.value for pt in request.post_types])
            
            # No visibility filter in NewsFeedRequest
            
            # Order by creation date
            query = query.order("created_at", desc=True)
            
            # Pagination
            offset = (request.page - 1) * request.limit
            query = query.range(offset, offset + request.limit - 1)
            
            response = query.execute()
            posts = response.data if response.data else []
            
            # Format posts using data from JOIN
            formatted_posts = []
            for post in posts:
                post_user_name = post.get("profiles", {}).get("user_name", "Unknown")
                # Add avatar_url to post data for _format_post_response
                post["author_avatar"] = post.get("profiles", {}).get("avatar_url")
                formatted_posts.append(self._format_post_response(post, post_user_name))
            
            total_pages = max(1, (len(formatted_posts) + request.limit - 1) // request.limit)
            has_next = request.page < total_pages
            
            return NewsFeedResponse(
                posts=formatted_posts,
                total_posts=len(formatted_posts),
                current_page=request.page,
                total_pages=total_pages,
                has_next=has_next
            )
            
        except Exception as e:
            logger.error(f"Error getting news feed: {str(e)}")
            raise
    
    # ============================================================================
    # Interactions
    # ============================================================================
    
    def like_post(self, user_name: str, post_id: str) -> bool:
        """Like a post"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return False
            
            # Check if already liked
            existing_like = self.supabase.table("post_likes").select("*").eq("post_id", post_id).eq("user_id", user_id).execute()
            if existing_like.data:
                return False  # Already liked
            
            # Create like record
            like_record = {
                "id": str(uuid.uuid4()),
                "post_id": post_id,
                "user_id": user_id,
                "created_at": datetime.now().isoformat()
            }
            
            self.supabase.table("post_likes").insert(like_record).execute()
            
            # Update post likes count
            self.supabase.table("social_posts").update({
                "likes_count": self.supabase.table("social_posts").select("likes_count").eq("id", post_id).execute().data[0]["likes_count"] + 1
            }).eq("id", post_id).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error liking post: {str(e)}")
            return False
    
    def add_comment(self, user_name: str, post_id: str, comment_data: CommentRequest) -> CommentResponse:
        """Add a comment to a post"""
        try:
            # Get user data in a single optimized query
            user_data = self._get_user_data(user_name)
            if not user_data:
                raise Exception(f"User {user_name} not found")
            
            user_id = user_data["id"]
            author_avatar = user_data.get("avatar_url")
            
            # Create comment record
            comment_id = str(uuid.uuid4())
            comment_record = {
                "id": comment_id,
                "post_id": post_id,
                "user_id": user_id,
                "content": comment_data.content,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Insert comment and update post count in a single transaction
            # First insert the comment
            comment_response = self.supabase.table("post_comments").insert(comment_record).execute()
            if not comment_response.data:
                raise Exception("Failed to create comment")
            
            # Update post comments count - get current count and increment
            current_post = self.supabase.table("social_posts").select("comments_count").eq("id", post_id).execute()
            if current_post.data:
                current_count = current_post.data[0].get("comments_count", 0)
                self.supabase.table("social_posts").update({
                    "comments_count": current_count + 1
                }).eq("id", post_id).execute()
            
            return CommentResponse(
                id=comment_id,
                user_name=user_name,
                content=comment_data.content,
                likes_count=0,  # New comment starts with 0 likes
                is_liked=False,  # Default to not liked
                created_at=datetime.now().isoformat(),
                author_avatar=author_avatar
            )
            
        except Exception as e:
            logger.error(f"Error adding comment: {str(e)}")
            raise
    
    def get_post_comments(self, post_id: str, current_user: Optional[str] = None) -> List[CommentResponse]:
        """Get all comments for a post"""
        try:
            # Get comments for the post
            response = self.supabase.table("post_comments").select(
                "*, profiles!inner(user_name, avatar_url)"
            ).eq("post_id", post_id).order("created_at", desc=False).execute()
            
            if not response.data:
                return []
            
            comments = []
            for comment in response.data:
                comments.append(CommentResponse(
                    id=comment["id"],
                    user_name=comment["profiles"]["user_name"],
                    content=comment["content"],
                    likes_count=0,  # No likes functionality for now
                    is_liked=False,  # No likes functionality for now
                    created_at=comment["created_at"],
                    author_avatar=comment["profiles"].get("avatar_url")
                ))
            
            return comments
            
        except Exception as e:
            logger.error(f"Error getting post comments: {str(e)}")
            return []
    
    # ============================================================================
    # Social Connections
    # ============================================================================
    
    def follow_user(self, user_name: str, target_user: str) -> bool:
        """Follow another user"""
        try:
            follower_id = self._get_user_id(user_name)
            following_id = self._get_user_id(target_user)
            
            if not follower_id or not following_id:
                return False
            
            if follower_id == following_id:
                return False  # Can't follow yourself
            
            # Check if already following
            existing_follow = self.supabase.table("user_follows").select("*").eq("follower_user_id", follower_id).eq("following_user_id", following_id).execute()
            if existing_follow.data:
                return False  # Already following
            
            # Create follow record
            follow_record = {
                "id": str(uuid.uuid4()),
                "follower_user_id": follower_id,
                "following_user_id": following_id,
                "created_at": datetime.now().isoformat()
            }
            
            self.supabase.table("user_follows").insert(follow_record).execute()
            return True
            
        except Exception as e:
            logger.error(f"Error following user: {str(e)}")
            return False
    
    def get_user_followers(self, user_name: str) -> List[SocialUserProfileResponse]:
        """Get user's followers"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return []
            
            # Get followers
            followers_response = self.supabase.table("user_follows").select("follower_user_id").eq("following_user_id", user_id).execute()
            if not followers_response.data:
                return []
            
            # Get follower profiles
            follower_ids = [f["follower_user_id"] for f in followers_response.data]
            profiles_response = self.supabase.table("profiles").select("*").in_("id", follower_ids).execute()
            
            followers = []
            for profile in profiles_response.data:
                followers.append(SocialUserProfileResponse(
                    user_name=profile["user_name"],
                    user_level=profile["user_level"],
                    bio=profile["bio"],
                    avatar_url=profile["avatar_url"]
                ))
            
            return followers
            
        except Exception as e:
            logger.error(f"Error getting followers: {str(e)}")
            return []
    
    def get_user_following(self, user_name: str) -> List[SocialUserProfileResponse]:
        """Get users that the user is following"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return []
            
            # Get following
            following_response = self.supabase.table("user_follows").select("following_user_id").eq("follower_user_id", user_id).execute()
            if not following_response.data:
                return []
            
            # Get following profiles
            following_ids = [f["following_user_id"] for f in following_response.data]
            profiles_response = self.supabase.table("profiles").select("*").in_("id", following_ids).execute()
            
            following = []
            for profile in profiles_response.data:
                following.append(SocialUserProfileResponse(
                    user_name=profile["user_name"],
                    user_level=profile["user_level"],
                    bio=profile["bio"],
                    avatar_url=profile["avatar_url"]
                ))
            
            return following
            
        except Exception as e:
            logger.error(f"Error getting following: {str(e)}")
            return []
    
    # ============================================================================
    # Points System
    # ============================================================================
    
    def award_points_to_user_by_id(self, user_id: str, points: int, reason: str, activity_type: str = "manual", metadata: dict = None) -> dict:
        """Award points to a user by UUID (public method for external integration)"""
        try:
            if points <= 0:
                return {"success": False, "error": "Points must be positive"}
            
            # Validate that user exists in the main system
            user_response = self.supabase.table("profiles").select("user_name").eq("id", user_id).execute()
            if not user_response.data:
                return {"success": False, "error": f"User with ID '{user_id}' does not exist in the system"}
            
            # Create transaction record
            transaction_record = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "points": points,
                "transaction_type": activity_type,
                "description": reason,
                "related_id": None,
                "created_at": datetime.now().isoformat()
            }
            
            # Insert transaction
            self.supabase.table("point_transactions").insert(transaction_record).execute()
            
            # Update user's total points
            user_points_response = self.supabase.table("user_points").select("*").eq("user_id", user_id).execute()
            
            if user_points_response.data:
                # Update existing record
                current_points = user_points_response.data[0]
                new_total = current_points["total_points"] + points
                new_available = current_points["available_points"] + points
                new_level = self._calculate_level(new_total)
                
                # Check for level up
                level_up = new_level > current_points["level"]
                
                update_data = {
                    "total_points": new_total,
                    "available_points": new_available,
                    "level": new_level,
                    "updated_at": datetime.now().isoformat()
                }
                
                if level_up:
                    update_data["last_activity"] = datetime.now().isoformat()
                
                self.supabase.table("user_points").update(update_data).eq("user_id", user_id).execute()
                
                # Create level up achievement if applicable
                if level_up:
                    user_name = user_response.data[0]["user_name"]
                    self._create_level_up_achievement(user_name, new_level)
                
                return {
                    "success": True,
                    "points_awarded": points,
                    "total_points": new_total,
                    "level": new_level,
                    "level_up": level_up
                }
            else:
                # Create new record
                new_level = self._calculate_level(points)
                points_record = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "total_points": points,
                    "available_points": points,
                    "level": new_level,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                self.supabase.table("user_points").insert(points_record).execute()
                
                return {
                    "success": True,
                    "points_awarded": points,
                    "total_points": points,
                    "level": new_level,
                    "level_up": False
                }
            
        except Exception as e:
            logger.error(f"Error awarding points to user {user_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    def award_points_to_user(self, user_name: str, points: int, reason: str, activity_type: str = "manual", metadata: dict = None) -> dict:
        """Award points to a user (public method for external integration)"""
        try:
            if points <= 0:
                return {"success": False, "error": "Points must be positive"}
            
            # Validate that user exists in the main system
            user_id = self._get_user_id(user_name)
            if not user_id:
                return {"success": False, "error": f"User '{user_name}' does not exist in the system"}
            
            # Create transaction record
            transaction_record = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "points": points,
                "transaction_type": activity_type,
                "description": reason,
                "related_id": None,
                "created_at": datetime.now().isoformat()
            }
            
            # Insert transaction
            self.supabase.table("point_transactions").insert(transaction_record).execute()
            
            # Update user's total points
            user_points_response = self.supabase.table("user_points").select("*").eq("user_id", user_id).execute()
            
            if user_points_response.data:
                # Update existing record
                current_points = user_points_response.data[0]
                new_total = current_points["total_points"] + points
                new_available = current_points["available_points"] + points
                new_level = self._calculate_level(new_total)
                
                # Check for level up
                level_up = new_level > current_points["level"]
                
                update_data = {
                    "total_points": new_total,
                    "available_points": new_available,
                    "level": new_level,
                    "updated_at": datetime.now().isoformat()
                }
                
                if level_up:
                    update_data["last_activity"] = datetime.now().isoformat()
                
                self.supabase.table("user_points").update(update_data).eq("user_id", user_id).execute()
                
                # Create level up achievement if applicable
                if level_up:
                    self._create_level_up_achievement(user_name, new_level)
                
                return {
                    "success": True,
                    "points_awarded": points,
                    "total_points": new_total,
                    "level": new_level,
                    "level_up": level_up
                }
            else:
                # Create new record
                new_level = self._calculate_level(points)
                points_record = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "total_points": points,
                    "available_points": points,
                    "level": new_level,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                self.supabase.table("user_points").insert(points_record).execute()
                
                return {
                    "success": True,
                    "points_awarded": points,
                    "total_points": points,
                    "level": new_level,
                    "level_up": False
                }
            
        except Exception as e:
            logger.error(f"Error awarding points to {user_name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_user_points(self, user_name: str) -> PointsSummary:
        """Get user's points summary"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return PointsSummary(
                    total_points=0, 
                    available_points=0, 
                    redeemed_points=0,
                    level=1, 
                    next_level_points=100,
                    badges=[]
                )
            
            response = self.supabase.table("user_points").select("*").eq("user_id", user_id).execute()
            if not response.data:
                return PointsSummary(
                    total_points=0, 
                    available_points=0, 
                    redeemed_points=0,
                    level=1, 
                    next_level_points=100,
                    badges=[]
                )
            
            points_data = response.data[0]
            total_points = points_data["total_points"]
            level = points_data["level"]
            next_level_points = (level + 1) * 100  # Calculate points needed for next level
            
            return PointsSummary(
                total_points=total_points,
                available_points=points_data["available_points"],
                redeemed_points=points_data.get("redeemed_points", 0),
                level=level,
                next_level_points=next_level_points,
                badges=points_data.get("badges", [])
            )
            
        except Exception as e:
            logger.error(f"Error getting user points: {str(e)}")
            return PointsSummary(
                total_points=0, 
                available_points=0, 
                redeemed_points=0,
                level=1, 
                next_level_points=100,
                badges=[]
            )
    
    def get_leaderboard(self, user_name: str, limit: int = 10) -> LeaderboardResponse:
        """Get leaderboard"""
        try:
            # Get top users by points with user_name in a single JOIN query
            response = self.supabase.table("user_points").select(
                "*, profiles!inner(user_name)"
            ).order("total_points", desc=True).limit(limit).execute()
            
            leaderboard = []
            for i, user_points in enumerate(response.data, 1):
                # Extract user_name from the joined profiles data
                user_name_from_join = user_points.get("profiles", {}).get("user_name")
                if user_name_from_join:
                    leaderboard.append(LeaderboardEntry(
                        rank=i,
                        user_name=user_name_from_join,
                        total_points=user_points["total_points"],
                        level=user_points["level"],
                        badges=user_points.get("badges", []),
                        streak_days=user_points.get("streak_days", 0),
                        avatar_url=user_points.get("avatar_url")
                    ))
            
            # Get current user's rank using a more efficient approach
            current_user_rank = None
            if user_name:
                # Get current user's points and rank in a single query
                current_user_response = self.supabase.table("user_points").select(
                    "total_points, profiles!inner(user_name)"
                ).eq("profiles.user_name", user_name).execute()
                
                if current_user_response.data:
                    current_user_points = current_user_response.data[0]["total_points"]
                    # Count how many users have more points than current user
                    rank_response = self.supabase.table("user_points").select(
                        "id", count="exact"
                    ).gt("total_points", current_user_points).execute()
                    current_user_rank = (rank_response.count or 0) + 1
            
            # Get total users count
            total_users_response = self.supabase.table("user_points").select("id", count="exact").execute()
            total_users = total_users_response.count if total_users_response.count else 0
            
            return LeaderboardResponse(
                entries=leaderboard,
                user_rank=current_user_rank,
                total_users=total_users
            )
            
        except Exception as e:
            logger.error(f"Error getting leaderboard: {str(e)}")
            return LeaderboardResponse(entries=[], user_rank=None, total_users=0)
    
    # ============================================================================
    # Achievements
    # ============================================================================
    
    def get_user_achievements(self, user_name: str) -> List[AchievementResponse]:
        """Get user's achievements"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return []
            
            response = self.supabase.table("social_achievements").select("*").eq("user_id", user_id).order("unlocked_at", desc=True).execute()
            
            achievements = []
            for achievement in response.data:
                achievements.append(AchievementResponse(
                    id=achievement["id"],
                    achievement_id=achievement.get("achievement_id", achievement["id"]),
                    achievement_name=achievement["achievement_name"],
                    description=achievement["description"],
                    points_earned=achievement["points_earned"],
                    icon=achievement["icon"],
                    unlocked_at=achievement["unlocked_at"]
                ))
            
            return achievements
            
        except Exception as e:
            logger.error(f"Error getting achievements: {str(e)}")
            return []
    
    # ============================================================================
    # Privacy Settings
    # ============================================================================
    
    def get_user_privacy_settings(self, user_name: str) -> Dict[str, Any]:
        """Get user's privacy settings"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return {}
            
            response = self.supabase.table("user_privacy_settings").select("*").eq("user_id", user_id).execute()
            if not response.data:
                return {}
            
            return response.data[0]
            
        except Exception as e:
            logger.error(f"Error getting privacy settings: {str(e)}")
            return {}
    
    def update_user_privacy_settings(self, user_name: str, settings: Dict[str, Any]) -> bool:
        """Update user's privacy settings"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return False
            
            # Update or create settings
            self.supabase.table("user_privacy_settings").upsert({
                "user_id": user_id,
                **settings,
                "updated_at": datetime.now().isoformat()
            }).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating privacy settings: {str(e)}")
            return False
    
    # ============================================================================
    # Study Analytics
    # ============================================================================
    
    def record_word_study(self, user_name: str, word: str, language: str, level: str, study_type: str, context: str = None, difficulty_score: float = None) -> bool:
        """Record a word study session"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return False
            
            study_record = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "word": word,
                "language": language,
                "level": level,
                "study_type": study_type,
                "context": context,
                "difficulty_score": difficulty_score,
                "created_at": datetime.now().isoformat()
            }
            
            self.supabase.table("word_study_records").insert(study_record).execute()
            return True
            
        except Exception as e:
            logger.error(f"Error recording word study: {str(e)}")
            return False
    
    def get_global_word_analytics(self, user_name: str, word: str, language: str) -> Dict[str, Any]:
        """Get global analytics for a word"""
        try:
            # Get word analytics
            response = self.supabase.table("global_word_analytics").select("*").eq("word", word).eq("language", language).execute()
            
            if not response.data:
                return {
                    "word": word,
                    "language": language,
                    "total_studiers": 0,
                    "today_studiers": 0,
                    "this_week_studiers": 0,
                    "level_breakdown": {},
                    "study_types": {},
                    "average_difficulty": 0.0,
                    "popularity_trend": "stable"
                }
            
            return response.data[0]
            
        except Exception as e:
            logger.error(f"Error getting global word analytics: {str(e)}")
            return {}
    
    def get_user_study_insights(self, user_name: str) -> Dict[str, Any]:
        """Get user's study insights"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return {}
            
            response = self.supabase.table("user_study_insights").select("*").eq("user_id", user_id).execute()
            if not response.data:
                return {}
            
            return response.data[0]
            
        except Exception as e:
            logger.error(f"Error getting study insights: {str(e)}")
            return {}
    
    def get_trending_words(self, user_name: str, language: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending words for user's level"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return []
            
            # Get user's level
            user_response = self.supabase.table("profiles").select("user_level").eq("id", user_id).execute()
            user_level = user_response.data[0]["user_level"] if user_response.data else "A1"
            
            # Get trending words
            response = self.supabase.table("trending_content").select("*").eq("content_type", "word").eq("language", language).eq("level", user_level).order("popularity_score", desc=True).limit(limit).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error getting trending words: {str(e)}")
            return []
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def _format_post_response(self, post: Dict[str, Any], user_name: str) -> PostResponse:
        """Format post data for response"""
        try:
            return PostResponse(
                id=post["id"],
                user_name=user_name,
                post_type=post.get("post_type", "conversation"),
                title=post.get("title", ""),
                content=post.get("content", ""),
                visibility=post.get("visibility", "public"),
                likes_count=post.get("likes_count", 0),
                comments_count=post.get("comments_count", 0),
                shares_count=post.get("shares_count", 0),
                points_earned=post.get("points_earned", 0),
                is_liked=post.get("is_liked", False),
                author_avatar=post.get("author_avatar"),
                metadata=post.get("metadata", {}),
                created_at=post.get("created_at", datetime.now().isoformat()),
                updated_at=post.get("updated_at", datetime.now().isoformat())
            )
        except Exception as e:
            logger.error(f"Error formatting post response: {str(e)}")
            # Return a minimal response if formatting fails
            return PostResponse(
                id=post.get("id", ""),
                user_name=user_name,
                post_type=post.get("post_type", "conversation"),
                title=post.get("title", ""),
                content=post.get("content", ""),
                visibility=post.get("visibility", "public"),
                likes_count=0,
                comments_count=0,
                shares_count=0,
                points_earned=0,
                is_liked=False,
                author_avatar=None,
                metadata={},
                created_at=post.get("created_at", datetime.now().isoformat()),
                updated_at=post.get("updated_at", datetime.now().isoformat())
            )
    
    def _award_points(self, user_name: str, activity: str, description: str, related_id: str = None):
        """Award points for an activity"""
        try:
            points = POINT_VALUES.get(activity, 0)
            if points > 0:
                self.award_points_to_user(user_name, points, description, activity, {"related_id": related_id})
        except Exception as e:
            logger.error(f"Error awarding points: {str(e)}")
    
    def _check_first_post_achievement(self, user_name: str):
        """Check for first post achievement"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return
            
            # Check if user has any posts
            posts_response = self.supabase.table("social_posts").select("id").eq("user_id", user_id).execute()
            if len(posts_response.data) == 1:  # This is their first post
                self._create_achievement(user_name, "first_post", "First Post", "Congratulations on your first post!", 50, "🎉")
        except Exception as e:
            logger.error(f"Error checking first post achievement: {str(e)}")
    
    def _create_achievement(self, user_name: str, achievement_id: str, name: str, description: str, points: int, icon: str):
        """Create an achievement for a user"""
        try:
            user_id = self._get_user_id(user_name)
            if not user_id:
                return
            
            # Check if achievement already exists
            existing = self.supabase.table("social_achievements").select("id").eq("user_id", user_id).eq("achievement_id", achievement_id).execute()
            if existing.data:
                return  # Already has this achievement
            
            # Create achievement
            achievement_record = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "achievement_id": achievement_id,
                "achievement_name": name,
                "description": description,
                "points_earned": points,
                "icon": icon,
                "unlocked_at": datetime.now().isoformat()
            }
            
            self.supabase.table("social_achievements").insert(achievement_record).execute()
            
            # Award points
            self.award_points_to_user(user_name, points, f"Achievement: {name}", "achievement")
            
        except Exception as e:
            logger.error(f"Error creating achievement: {str(e)}")
    
    def _create_level_up_achievement(self, user_name: str, level: int):
        """Create level up achievement"""
        try:
            self._create_achievement(
                user_name,
                f"level_{level}",
                f"Level {level}",
                f"Congratulations on reaching level {level}!",
                level * 100,
                "⭐"
            )
        except Exception as e:
            logger.error(f"Error creating level up achievement: {str(e)}")
    
    def _calculate_level(self, total_points: int) -> int:
        """Calculate user level based on total points"""
        for level, threshold in LEVEL_THRESHOLDS.items():
            if total_points < threshold:
                return level - 1
        return max(LEVEL_THRESHOLDS.keys())
