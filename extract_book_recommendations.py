#!/usr/bin/env python3
"""
Instagram Book Recommendations Extractor

This script parses Instagram posts from posts_1.html and extracts book recommendations,
then organizes them into a separate folder with images and opinions.
"""

import os
import re
import shutil
from bs4 import BeautifulSoup
from datetime import datetime
import json

def create_book_recommendations_folder():
    """Create the book recommendations folder if it doesn't exist."""
    folder_name = "book_recommendations"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"Created folder: {folder_name}")
    return folder_name

def extract_book_posts(html_file_path):
    """Extract posts that contain book recommendations."""
    with open(html_file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Find all post containers
    post_containers = soup.find_all('div', class_='pam _3-95 _2ph- _a6-g uiBoxWhite noborder')
    
    book_posts = []
    
    for post in post_containers:
        # Look for the caption (h2 element)
        caption_elem = post.find('h2', class_='_3-95 _2pim _a6-h _a6-i')
        
        if caption_elem:
            caption = caption_elem.get_text(strip=True)
            
            # Check if this post contains book recommendations
            if '#bookrecommendations' in caption.lower():
                # Extract date
                date_elem = post.find('div', class_='_3-94 _a6-o')
                date = date_elem.get_text(strip=True) if date_elem else "Unknown date"
                
                # Extract images
                images = []
                img_elements = post.find_all('img', class_='_a6_o _3-96')
                for img in img_elements:
                    src = img.get('src', '')
                    if src:
                        # Extract the filename from the src
                        filename = src.split('/')[-1]
                        images.append(filename)
                
                # Extract video if present
                video_elem = post.find('video', class_='_a6_o _3-96')
                video = None
                if video_elem:
                    src = video_elem.get('src', '')
                    if src:
                        video = src.split('/')[-1]
                
                book_posts.append({
                    'caption': caption,
                    'date': date,
                    'images': images,
                    'video': video,
                    'post_element': post
                })
                
                print(f"Found book recommendation post from {date}")
                print(f"Caption: {caption[:100]}...")
                print(f"Images: {len(images)}")
                print("-" * 50)
    
    return book_posts

def copy_images_to_folder(book_posts, instagram_folder, book_folder):
    """Copy book-related images to the book recommendations folder."""
    copied_images = []
    
    for post in book_posts:
        post_images = []
        
        for img_filename in post['images']:
            # Look for the image in the instagram posts folder
            source_path = None
            
            # Search through all date folders
            for date_folder in os.listdir(instagram_folder):
                date_path = os.path.join(instagram_folder, date_folder)
                if os.path.isdir(date_path):
                    # Check if this is a posts folder
                    posts_path = os.path.join(date_path, 'posts')
                    if os.path.exists(posts_path):
                        # Look for the image in this posts folder
                        for file in os.listdir(posts_path):
                            if file == img_filename:
                                source_path = os.path.join(posts_path, file)
                                break
                        if source_path:
                            break
                    # Also check the date folder directly
                    for file in os.listdir(date_path):
                        if file == img_filename:
                            source_path = os.path.join(date_path, file)
                            break
                    if source_path:
                        break
            
            # If still not found, try a more flexible search
            if not source_path:
                source_path = find_image_flexibly(instagram_folder, img_filename)
            
            if source_path and os.path.exists(source_path):
                # Create a unique filename for the book recommendations folder
                base_name, ext = os.path.splitext(img_filename)
                # Use date and caption to create a meaningful filename
                date_str = post['date'].replace(' ', '_').replace(',', '').replace(':', '_')
                safe_caption = re.sub(r'[^\w\s-]', '', post['caption'][:30]).strip()
                safe_caption = re.sub(r'[-\s]+', '-', safe_caption)
                new_filename = f"{date_str}_{safe_caption}_{base_name}{ext}"
                
                dest_path = os.path.join(book_folder, new_filename)
                
                try:
                    shutil.copy2(source_path, dest_path)
                    post_images.append(new_filename)
                    print(f"Copied: {img_filename} -> {new_filename}")
                except Exception as e:
                    print(f"Error copying {img_filename}: {e}")
            else:
                print(f"Could not find image: {img_filename}")
        
        copied_images.append({
            'date': post['date'],
            'caption': post['caption'],
            'images': post_images,
            'video': post['video']
        })
    
    return copied_images

def find_image_flexibly(instagram_folder, img_filename):
    """More flexible image finding by searching recursively and checking partial matches."""
    source_path = None
    
    # First, try to find the exact filename recursively
    for root, dirs, files in os.walk(instagram_folder):
        for file in files:
            if file == img_filename:
                return os.path.join(root, file)
    
    # If not found, try to find files with similar names (partial match)
    base_name, ext = os.path.splitext(img_filename)
    
    # Try to find files that contain the main part of the filename
    for root, dirs, files in os.walk(instagram_folder):
        for file in files:
            if file.endswith(ext) and base_name in file:
                # Check if this looks like the right file
                if len(file) > len(base_name) * 0.8:  # At least 80% match
                    print(f"Found similar image: {file} (was looking for {img_filename})")
                    return os.path.join(root, file)
    
    return None

def create_summary_file(book_data, book_folder):
    """Create a summary file with all book recommendations."""
    summary_path = os.path.join(book_folder, "book_recommendations_summary.txt")
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("BOOK RECOMMENDATIONS FROM INSTAGRAM POSTS\n")
        f.write("=" * 50 + "\n\n")
        
        for i, book in enumerate(book_data, 1):
            f.write(f"RECOMMENDATION #{i}\n")
            f.write(f"Date: {book['date']}\n")
            f.write(f"Caption: {book['caption']}\n")
            f.write(f"Images: {', '.join(book['images']) if book['images'] else 'None'}\n")
            if book['video']:
                f.write(f"Video: {book['video']}\n")
            f.write("-" * 40 + "\n\n")
    
    print(f"Created summary file: {summary_path}")

def create_json_file(book_data, book_folder):
    """Create a JSON file with structured book data."""
    json_path = os.path.join(book_folder, "book_recommendations.json")
    
    # Clean up the data for JSON serialization
    json_data = []
    for book in book_data:
        json_data.append({
            'date': book['date'],
            'caption': book['caption'],
            'images': book['images'],
            'video': book['video']
        })
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"Created JSON file: {json_path}")

def main():
    """Main function to extract book recommendations."""
    print("Instagram Book Recommendations Extractor")
    print("=" * 40)
    
    # Paths
    instagram_folder = "instagram"
    html_file = os.path.join(instagram_folder, "posts_1.html")
    
    # Check if files exist
    if not os.path.exists(html_file):
        print(f"Error: Could not find {html_file}")
        return
    
    if not os.path.exists(instagram_folder):
        print(f"Error: Could not find {instagram_folder} folder")
        return
    
    # Debug: Show Instagram folder structure
    print("\nInstagram folder structure:")
    print("-" * 30)
    for item in os.listdir(instagram_folder):
        item_path = os.path.join(instagram_folder, item)
        if os.path.isdir(item_path):
            print(f"📁 {item}/")
            # Show subdirectories
            try:
                subitems = os.listdir(item_path)
                for subitem in subitems[:5]:  # Show first 5 items
                    subitem_path = os.path.join(item_path, subitem)
                    if os.path.isdir(subitem_path):
                        print(f"  📁 {subitem}/")
                    else:
                        print(f"  📄 {subitem}")
                if len(subitems) > 5:
                    print(f"  ... and {len(subitems) - 5} more items")
            except PermissionError:
                print(f"  (Permission denied to access {item})")
        else:
            print(f"📄 {item}")
    
    # Create book recommendations folder
    book_folder = create_book_recommendations_folder()
    
    # Extract book posts
    print("\nExtracting book recommendation posts...")
    book_posts = extract_book_posts(html_file)
    
    if not book_posts:
        print("No book recommendation posts found!")
        return
    
    print(f"\nFound {len(book_posts)} book recommendation posts")
    
    # Copy images to book recommendations folder
    print("\nCopying images to book recommendations folder...")
    book_data = copy_images_to_folder(book_posts, instagram_folder, book_folder)
    
    # Create summary files
    print("\nCreating summary files...")
    create_summary_file(book_data, book_folder)
    create_json_file(book_data, book_folder)
    
    print(f"\n✅ Extraction complete! Check the '{book_folder}' folder for results.")
    print(f"Total book recommendations extracted: {len(book_data)}")

if __name__ == "__main__":
    main() 