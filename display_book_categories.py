#!/usr/bin/env python3
"""
Display Book Categories
Simple script to show book titles organized by category
"""

import json

def display_book_categories():
    """Display all books organized by category with readable titles."""
    
    # Load the categorized books
    with open('book_recommendations/categorized_books.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("📚 BOOK RECOMMENDATIONS BY CATEGORY")
    print("=" * 60)
    
    # Display each category
    for category, books in data['categories'].items():
        print(f"\n🔹 {category.upper()}: {len(books)} books")
        print("-" * (len(category) + 10))
        
        for i, book in enumerate(books, 1):
            # Extract a meaningful title from the caption
            caption = book['caption']
            words = caption.split()[:10]  # First 10 words
            title = " ".join(words) + "..." if len(caption) > 50 else caption
            
            print(f"  {i:2d}. {book['date']}")
            print(f"      {title}")
            print()
    
    # Show uncategorized books
    if data['uncategorized']:
        print(f"\n❓ UNCATEGORIZED: {len(data['uncategorized'])} books")
        print("-" * 30)
        
        for i, book in enumerate(data['uncategorized'], 1):
            caption = book['caption']
            words = caption.split()[:10]
            title = " ".join(words) + "..." if len(caption) > 50 else caption
            
            print(f"  {i:2d}. {book['date']}")
            print(f"      {title}")
            print()
    
    # Summary
    print("📊 SUMMARY")
    print("-" * 20)
    print(f"Total books: {data['summary']['total_books']}")
    print(f"Categorized: {data['summary']['categorized']}")
    print(f"Uncategorized: {data['summary']['uncategorized']}")

if __name__ == "__main__":
    display_book_categories() 