from sqlmodel import SQLModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from enum import Enum
from pydantic import validator

# ============================================================================
# Social Feature Models for Backend API
# ============================================================================

class PostType(str, Enum):
    """Types of social posts"""
    ACHIEVEMENT = "achievement"
    LEVEL_UP = "level_up"
    STREAK = "streak"
    CONVERSATION = "conversation"
    LEARNING_TIP = "learning_tip"
    MILESTONE = "milestone"
    CHALLENGE = "challenge"

class PostVisibility(str, Enum):
    """Post visibility settings"""
    PUBLIC = "public"
    FRIENDS = "friends"
    PRIVATE = "private"
    LEVEL_RESTRICTED = "level_restricted"  # Only visible to users at same level
    STUDY_GROUP = "study_group"  # Visible to users studying same language/topics

# ============================================================================
# Request/Response Models for API Endpoints
# ============================================================================

class CreatePostRequest(SQLModel):
    """Request model for creating a social post"""
    post_type: PostType = Field(description="Type of post")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    visibility: PostVisibility = Field(default=PostVisibility.PUBLIC, description="Post visibility")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional post metadata")

class PostResponse(SQLModel):
    """Response model for social posts"""
    id: str = Field(description="Post ID")
    user_name: str = Field(description="Username of the post author")
    post_type: str = Field(description="Type of post")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    visibility: str = Field(description="Post visibility")
    likes_count: int = Field(description="Number of likes")
    comments_count: int = Field(description="Number of comments")
    shares_count: int = Field(description="Number of shares")
    points_earned: int = Field(description="Points earned for this post")
    is_liked: bool = Field(default=False, description="Whether current user liked this post")
    created_at: str = Field(description="Creation timestamp")
    author_avatar: Optional[str] = Field(description="Author's avatar URL")

class CommentRequest(SQLModel):
    """Request model for commenting on posts"""
    content: str = Field(description="Comment content")

class CommentResponse(SQLModel):
    """Response model for comments"""
    id: str = Field(description="Comment ID")
    user_name: str = Field(description="Username of the commenter")
    content: str = Field(description="Comment content")
    likes_count: int = Field(description="Number of likes on comment")
    is_liked: bool = Field(default=False, description="Whether current user liked this comment")
    created_at: str = Field(description="Creation timestamp")
    author_avatar: Optional[str] = Field(description="Commenter's avatar URL")

class NewsFeedRequest(SQLModel):
    """Request model for news feed"""
    page: int = Field(default=1, description="Page number")
    limit: int = Field(default=20, description="Number of posts per page")
    post_types: Optional[List[PostType]] = Field(default=None, description="Filter by post types")

class NewsFeedResponse(SQLModel):
    """Response model for news feed"""
    posts: List[PostResponse] = Field(description="List of posts")
    total_posts: int = Field(description="Total number of posts")
    current_page: int = Field(description="Current page number")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there are more pages")

class SocialUserProfileResponse(SQLModel):
    """Enhanced user profile response with social data"""
    user_name: str = Field(description="Username")
    first_name: Optional[str] = Field(description="First name")
    last_name: Optional[str] = Field(description="Last name")
    avatar_url: Optional[str] = Field(description="Avatar URL")
    bio: Optional[str] = Field(description="User bio")
    total_points: int = Field(description="Total points")
    level: int = Field(description="User level")
    badges: List[str] = Field(description="Earned badges")
    followers_count: int = Field(description="Number of followers")
    following_count: int = Field(description="Number of users following")
    posts_count: int = Field(description="Number of posts")
    is_following: bool = Field(default=False, description="Whether current user is following this user")

class FollowRequest(SQLModel):
    """Request model for following/unfollowing users"""
    action: str = Field(description="Action: 'follow' or 'unfollow'")

class PointsSummary(SQLModel):
    """User points summary"""
    total_points: int = Field(description="Total points earned")
    available_points: int = Field(description="Points available for redemption")
    redeemed_points: int = Field(description="Points already redeemed")
    level: int = Field(description="Current level")
    next_level_points: int = Field(description="Points needed for next level")
    badges: List[str] = Field(description="Earned badges")

class LeaderboardEntry(SQLModel):
    """Leaderboard entry model"""
    user_name: str = Field(description="Username")
    total_points: int = Field(description="Total points")
    level: int = Field(description="User level")
    rank: int = Field(description="Current rank")
    badges: List[str] = Field(description="User badges")
    streak_days: int = Field(description="Current streak")
    avatar_url: Optional[str] = Field(description="User avatar")

class LeaderboardResponse(SQLModel):
    """Leaderboard response"""
    entries: List[LeaderboardEntry] = Field(description="Leaderboard entries")
    user_rank: Optional[int] = Field(description="Current user's rank")
    total_users: int = Field(description="Total number of users")

# ============================================================================
# Intelligent Feed Models
# ============================================================================

class UserPrivacySettings(SQLModel):
    """User privacy settings"""
    user_name: str = Field(description="Username")
    show_posts_to_level: str = Field(default="same", description="Who can see posts: same, all, friends")
    show_achievements: bool = Field(default=True, description="Show achievements publicly")
    show_learning_progress: bool = Field(default=True, description="Show learning progress")
    allow_level_filtering: bool = Field(default=True, description="Allow level-based filtering")
    study_group_visibility: bool = Field(default=True, description="Visible to study groups")

class TrendingContent(SQLModel):
    """Trending content model"""
    content_type: str = Field(description="Type of content (word, phrase, topic)")
    content: str = Field(description="The trending content")
    language: str = Field(description="Language being studied")
    level: str = Field(description="Language level")
    popularity_score: float = Field(description="Popularity score")
    usage_count: int = Field(description="Number of times used")
    last_updated: str = Field(description="Last updated timestamp")

class SmartFeedRequest(SQLModel):
    """Enhanced feed request with intelligent filtering"""
    page: int = Field(default=1, description="Page number")
    limit: int = Field(default=20, description="Number of posts per page")
    post_types: Optional[List[PostType]] = Field(default=None, description="Filter by post types")
    level_filter: Optional[str] = Field(default=None, description="Filter by language level")
    language_filter: Optional[str] = Field(default=None, description="Filter by target language")
    include_trending: bool = Field(default=True, description="Include trending content")
    include_level_peers: bool = Field(default=True, description="Include posts from same level users")
    include_study_groups: bool = Field(default=True, description="Include study group content")
    personalization_score: float = Field(default=0.7, description="Personalization strength (0-1)")

class ContentRecommendation(SQLModel):
    """Content recommendation model"""
    content_id: str = Field(description="Content identifier")
    content_type: str = Field(description="Type of content")
    title: str = Field(description="Content title")
    content: str = Field(description="Content text")
    relevance_score: float = Field(description="Relevance score (0-1)")
    reason: str = Field(description="Why this was recommended")
    author_level: str = Field(description="Author's language level")
    target_language: str = Field(description="Target language")
    trending_score: Optional[float] = Field(default=None, description="Trending score if applicable")

class SmartFeedResponse(SQLModel):
    """Enhanced feed response with intelligent content"""
    posts: List[PostResponse] = Field(description="List of posts")
    recommendations: List[ContentRecommendation] = Field(description="Content recommendations")
    trending_content: List[TrendingContent] = Field(description="Trending content")
    total_posts: int = Field(description="Total number of posts")
    current_page: int = Field(description="Current page number")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there are more pages")
    feed_algorithm: str = Field(description="Algorithm used for feed generation")
    personalization_applied: bool = Field(description="Whether personalization was applied")

# ============================================================================
# Global Study Analytics Models
# ============================================================================

class WordStudyRecord(SQLModel):
    """Record of a word being studied by a user"""
    id: str = Field(description="Record ID")
    user_name: str = Field(description="Username")
    word: str = Field(description="Word being studied")
    language: str = Field(description="Target language")
    level: str = Field(description="User's language level")
    study_type: str = Field(description="Type of study (conversation, flashcard, exercise)")
    context: Optional[str] = Field(description="Context where word was encountered")
    difficulty_score: Optional[float] = Field(description="User's difficulty with this word (0-1)")
    created_at: str = Field(description="When word was studied")

class GlobalWordAnalytics(SQLModel):
    """Global analytics for a specific word"""
    word: str = Field(description="The word")
    language: str = Field(description="Language")
    total_studiers: int = Field(description="Total number of people who studied this word")
    today_studiers: int = Field(description="Number of people who studied this word today")
    this_week_studiers: int = Field(description="Number of people who studied this word this week")
    level_breakdown: Dict[str, int] = Field(description="Breakdown by language level")
    study_types: Dict[str, int] = Field(description="Breakdown by study type")
    average_difficulty: float = Field(description="Average difficulty score")
    popularity_trend: str = Field(description="Trend: increasing, stable, decreasing")
    last_updated: str = Field(description="Last updated timestamp")

class StudyInsights(SQLModel):
    """Study insights for a user"""
    user_name: str = Field(description="Username")
    words_studied_today: int = Field(description="Words studied today")
    words_studied_this_week: int = Field(description="Words studied this week")
    total_words_studied: int = Field(description="Total words studied")
    most_difficult_words: List[str] = Field(description="Most difficult words for this user")
    study_streak: int = Field(description="Current study streak in days")
    level_progress: Dict[str, Any] = Field(description="Progress within current level")
    global_rank: Optional[int] = Field(description="Global ranking among all users")
    level_rank: Optional[int] = Field(description="Ranking within user's level")

class WordRecommendation(SQLModel):
    """Word recommendation based on global analytics"""
    word: str = Field(description="Recommended word")
    language: str = Field(description="Language")
    level: str = Field(description="Appropriate level")
    reason: str = Field(description="Why this word is recommended")
    popularity_score: float = Field(description="How popular this word is")
    difficulty_score: float = Field(description="Estimated difficulty")
    study_count: int = Field(description="Number of people studying this word")
    trending: bool = Field(description="Whether this word is trending")

class StudyAnalyticsRequest(SQLModel):
    """Request for study analytics"""
    language: str = Field(description="Target language")
    level: Optional[str] = Field(default=None, description="Language level filter")
    time_period: str = Field(default="today", description="Time period: today, week, month")
    limit: int = Field(default=50, description="Number of results to return")

class StudyAnalyticsResponse(SQLModel):
    """Response for study analytics"""
    analytics: List[GlobalWordAnalytics] = Field(description="Word analytics")
    user_insights: Optional[StudyInsights] = Field(description="User-specific insights")
    recommendations: List[WordRecommendation] = Field(description="Word recommendations")
    total_words: int = Field(description="Total number of words analyzed")
    time_period: str = Field(description="Time period analyzed")
    last_updated: str = Field(description="Last updated timestamp")

class AchievementResponse(SQLModel):
    """Achievement response"""
    id: str = Field(description="Achievement ID")
    achievement_id: str = Field(description="Achievement identifier")
    achievement_name: str = Field(description="Achievement name")
    description: str = Field(description="Achievement description")
    points_earned: int = Field(description="Points earned for this achievement")
    icon: str = Field(description="Achievement icon")
    unlocked_at: str = Field(description="When achievement was unlocked")

# ============================================================================
# Point System Configuration
# ============================================================================

POINT_VALUES = {
    "post_created": 10,
    "post_liked": 1,
    "post_shared": 5,
    "comment_created": 3,
    "achievement_unlocked": 25,
    "level_up": 50,
    "streak_7_days": 30,
    "streak_30_days": 100,
    "conversation_completed": 5,
    "daily_login": 2,
    "profile_completed": 20,
    "first_post": 15,
    "first_comment": 5,
    "first_follow": 10,
    "milestone_reached": 40
}

LEVEL_THRESHOLDS = {
    1: 0,
    2: 100,
    3: 300,
    4: 600,
    5: 1000,
    6: 1500,
    7: 2200,
    8: 3000,
    9: 4000,
    10: 5000
}

BADGES = {
    "first_post": {"name": "First Post", "description": "Created your first post", "icon": "📝"},
    "social_butterfly": {"name": "Social Butterfly", "description": "Made 10 posts", "icon": "🦋"},
    "conversation_master": {"name": "Conversation Master", "description": "Completed 50 conversations", "icon": "💬"},
    "streak_warrior": {"name": "Streak Warrior", "description": "Maintained a 30-day streak", "icon": "🔥"},
    "level_explorer": {"name": "Level Explorer", "description": "Reached level 5", "icon": "⭐"},
    "community_helper": {"name": "Community Helper", "description": "Helped 20 users", "icon": "🤝"},
    "achievement_hunter": {"name": "Achievement Hunter", "description": "Unlocked 10 achievements", "icon": "🏆"},
    "point_collector": {"name": "Point Collector", "description": "Earned 1000 points", "icon": "💰"}
}
