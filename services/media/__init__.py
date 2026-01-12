"""
Media Processing Services
מודול מרכזי לעיבוד מדיה - YouTube, תמונות, אודיו
"""

# YouTube Downloads
from .youtube import (
    download_youtube_video_dual,
    download_youtube_video,
    compress_video_smart,
    get_video_info
)

# Image Processing
from .image import (
    add_text_to_image,
    fetch_youtube_thumbnail,
    prepare_mp3_thumbnail,
    prepare_telegram_thumbnail
)

# Audio Processing
from .audio import update_mp3_tags

# FFmpeg Utilities
from .ffmpeg_utils import (
    get_video_dimensions,
    convert_to_compatible_format,
    compress_to_target_size
)

# Instagram Downloads
from .instagram import (
    download_instagram_story,
    download_instagram_reel,
    is_instagram_story_url,
    is_instagram_reel_url
)

# General Utilities
from .utils import (
    sanitize_filename,
    cleanup_files,
    update_cookies,
    get_file_extension,
    build_target_filename,
    get_next_update_filename,
    create_upload_copy
)

__all__ = [
    # YouTube
    'download_youtube_video_dual',
    'download_youtube_video',
    'compress_video_smart',
    'get_video_info',
    
    # Image
    'add_text_to_image',
    'fetch_youtube_thumbnail',
    'prepare_mp3_thumbnail',
    'prepare_telegram_thumbnail',
    
    # Audio
    'update_mp3_tags',
    
    # Instagram
    'download_instagram_story',
    'download_instagram_reel',
    'is_instagram_story_url',
    'is_instagram_reel_url',
    
    # FFmpeg
    'get_video_dimensions',
    'convert_to_compatible_format',
    'compress_to_target_size',
    
    # Utils
    'sanitize_filename',
    'cleanup_files',
    'update_cookies',
    'get_file_extension',
    'build_target_filename',
    'get_next_update_filename',
    'create_upload_copy',
]

