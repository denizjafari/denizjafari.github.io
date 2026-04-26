#!/usr/bin/env python3
"""
Book Recommendations Categorizer

This script categorizes book recommendations into four classes:
1. Technology & Innovation (AI, blockchain, computer science, emerging tech)
2. Economics & Business (macroeconomics, capitalism critiques, financial systems, entrepreneurship)
3. Personal Development & Growth (success, resilience, learning, intentional living, meaningful work, productivity)
4. Health & Medicine (medical field, human psychology, triathlon, endurance sports, mindset for peak performance)
"""

import json
import os
import re
from collections import defaultdict

# Define category keywords and patterns
CATEGORIES = {
    "Technology & Innovation": {
        "keywords": [
            "ai", "artificial intelligence", "blockchain", "computer science", "technology", 
            "automation", "autonomous", "driverless", "innovation", "digital", "software",
            "machine learning", "data science", "robotics", "cybersecurity", "cloud computing",
            "internet", "social media", "mobile", "web", "programming", "coding", "algorithm",
            "virtual reality", "augmented reality", "quantum computing", "biotechnology"
        ],
        "patterns": [
            r"ai\b", r"artificial intelligence", r"blockchain", r"computer science",
            r"technology", r"automation", r"autonomous", r"driverless", r"innovation",
            r"digital", r"software", r"machine learning", r"data science", r"robotics"
        ]
    },
    
    "Economics & Business": {
        "keywords": [
            "economics", "business", "finance", "investment", "stock market", "entrepreneurship",
            "capitalism", "market", "trade", "commerce", "startup", "venture capital",
            "management", "leadership", "strategy", "marketing", "sales", "operations",
            "accounting", "budgeting", "financial planning", "wealth", "money", "profit",
            "economy", "recession", "inflation", "monetary policy", "fiscal policy"
        ],
        "patterns": [
            r"economics", r"business", r"finance", r"investment", r"stock market",
            r"entrepreneurship", r"capitalism", r"market", r"trade", r"commerce",
            r"startup", r"venture capital", r"management", r"leadership", r"strategy"
        ]
    },
    
    "Personal Development & Growth": {
        "keywords": [
            "success", "resilience", "learning", "growth", "development", "mindset",
            "productivity", "habits", "goals", "motivation", "self-improvement",
            "intentional living", "meaningful work", "purpose", "balance", "wellness",
            "happiness", "fulfillment", "achievement", "excellence", "mastery",
            "creativity", "innovation", "problem solving", "communication", "relationships"
        ],
        "patterns": [
            r"success", r"resilience", r"learning", r"growth", r"development",
            r"mindset", r"productivity", r"habits", r"goals", r"motivation",
            r"self-improvement", r"intentional living", r"meaningful work", r"purpose"
        ]
    },
    
    "Health & Medicine": {
        "keywords": [
            "health", "medicine", "medical", "psychology", "mental health", "physical health",
            "triathlon", "endurance", "sports", "fitness", "exercise", "nutrition",
            "wellness", "recovery", "performance", "athlete", "training", "workout",
            "mindset", "peak performance", "biomechanics", "physiology", "anatomy",
            "therapy", "healing", "prevention", "wellbeing", "lifestyle"
        ],
        "patterns": [
            r"health", r"medicine", r"medical", r"psychology", r"mental health",
            r"physical health", r"triathlon", r"endurance", r"sports", r"fitness",
            r"exercise", r"nutrition", r"wellness", r"recovery", r"performance"
        ]
    },
    
    "Society and Culture": {
        "keywords": [
            "history", "historical", "sustainability", "sustainable", "culture", "cultural",
            "society", "social", "civilization", "anthropology", "sociology", "politics",
            "political", "government", "democracy", "human rights", "social justice",
            "environment", "environmental", "climate", "global", "world", "international",
            "transition", "change", "evolution", "progress", "development", "modernization",
            "tradition", "heritage", "identity", "diversity", "inclusion", "equality",
            "philosophy", "ethics", "morality", "values", "beliefs", "religion"
        ],
        "patterns": [
            r"history", r"historical", r"sustainability", r"sustainable", r"culture",
            r"cultural", r"society", r"social", r"civilization", r"anthropology",
            r"sociology", r"politics", r"political", r"government", r"democracy",
            r"human rights", r"social justice", r"environment", r"environmental",
            r"climate", r"global", r"world", r"international", r"transition",
            r"change", r"evolution", r"progress", r"development", r"modernization"
        ]
    }
}

def categorize_book(caption, date):
    """
    Categorize a book based on its caption and date.
    Returns the category with the highest confidence score.
    """
    caption_lower = caption.lower()
    
    # Calculate confidence scores for each category
    category_scores = {}
    
    for category, config in CATEGORIES.items():
        score = 0
        
        # Check keyword matches
        for keyword in config["keywords"]:
            if keyword in caption_lower:
                score += 2  # Keywords get higher weight
        
        # Check pattern matches
        for pattern in config["patterns"]:
            if re.search(pattern, caption_lower):
                score += 3  # Pattern matches get highest weight
        
        # Special case: if caption mentions specific categories explicitly
        if "ai" in caption_lower or "artificial intelligence" in caption_lower:
            if category == "Technology & Innovation":
                score += 5
        elif "entrepreneurship" in caption_lower or "startup" in caption_lower:
            if category == "Economics & Business":
                score += 5
        elif "triathlon" in caption_lower or "endurance" in caption_lower:
            if category == "Health & Medicine":
                score += 5
        elif "balance" in caption_lower or "mindset" in caption_lower:
            if category == "Personal Development & Growth":
                score += 5
        elif "history" in caption_lower or "sustainability" in caption_lower or "culture" in caption_lower:
            if category == "Society and Culture":
                score += 5
        
        category_scores[category] = score
    
    # Return category with highest score, or "Uncategorized" if no clear match
    if max(category_scores.values()) == 0:
        return "Uncategorized"
    
    return max(category_scores, key=category_scores.get)

def analyze_book_recommendations():
    """
    Load and categorize all book recommendations.
    """
    # Load the book recommendations
    json_file = "book_recommendations/book_recommendations.json"
    
    if not os.path.exists(json_file):
        print(f"Error: Could not find {json_file}")
        return None
    
    with open(json_file, 'r', encoding='utf-8') as f:
        books = json.load(f)
    
    print(f"Loaded {len(books)} book recommendations")
    print("=" * 60)
    
    # Categorize each book
    categorized_books = defaultdict(list)
    uncategorized = []
    
    for book in books:
        category = categorize_book(book['caption'], book['date'])
        book['category'] = category
        
        if category == "Uncategorized":
            uncategorized.append(book)
        else:
            categorized_books[category].append(book)
    
    # Display results
    print("\n📚 BOOK CATEGORIZATION RESULTS")
    print("=" * 60)
    
    for category in CATEGORIES.keys():
        count = len(categorized_books[category])
        print(f"\n{category}: {count} books")
        print("-" * len(category))
        
        for book in categorized_books[category]:
            # Extract a short title from the caption
            caption_words = book['caption'].split()[:8]
            short_title = " ".join(caption_words) + "..."
            print(f"  • {book['date']}: {short_title}")
    
    if uncategorized:
        print(f"\nUncategorized: {len(uncategorized)} books")
        print("-" * 20)
        for book in uncategorized:
            caption_words = book['caption'].split()[:8]
            short_title = " ".join(caption_words) + "..."
            print(f"  • {book['date']}: {short_title}")
    
    # Save categorized results
    output_file = "book_recommendations/categorized_books.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'categories': dict(categorized_books),
            'uncategorized': uncategorized,
            'summary': {
                'total_books': len(books),
                'categorized': len(books) - len(uncategorized),
                'uncategorized': len(uncategorized)
            }
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Categorized results saved to: {output_file}")
    
    # Create category summary files
    create_category_summaries(categorized_books, uncategorized)
    
    return categorized_books

def create_category_summaries(categorized_books, uncategorized):
    """
    Create summary files for each category.
    """
    # Create summaries directory
    summaries_dir = "book_recommendations/category_summaries"
    os.makedirs(summaries_dir, exist_ok=True)
    
    # Create summary for each category
    for category, books in categorized_books.items():
        filename = f"{summaries_dir}/{category.replace(' & ', '_').replace(' ', '_').lower()}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"{category.upper()}\n")
            f.write("=" * len(category) + "\n\n")
            f.write(f"Total books: {len(books)}\n\n")
            
            for book in books:
                f.write(f"Date: {book['date']}\n")
                f.write(f"Caption: {book['caption']}\n")
                f.write(f"Images: {', '.join(book['images'])}\n")
                f.write("-" * 80 + "\n\n")
    
    # Create uncategorized summary
    if uncategorized:
        filename = f"{summaries_dir}/uncategorized.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("UNCATEGORIZED BOOKS\n")
            f.write("=" * 20 + "\n\n")
            f.write(f"Total books: {len(uncategorized)}\n\n")
            
            for book in uncategorized:
                f.write(f"Date: {book['date']}\n")
                f.write(f"Caption: {book['caption']}\n")
                f.write(f"Images: {', '.join(book['images'])}\n")
                f.write("-" * 80 + "\n\n")
    
    print(f"📁 Category summaries saved to: {summaries_dir}/")

def main():
    """
    Main function to run the book categorization.
    """
    print("🔍 Book Recommendations Categorizer")
    print("=" * 40)
    
    try:
        categorized_books = analyze_book_recommendations()
        
        if categorized_books:
            print("\n✅ Book categorization completed successfully!")
            
            # Show some examples of categorization
            print("\n📖 EXAMPLES OF CATEGORIZATION:")
            print("-" * 40)
            
            for category, books in list(categorized_books.items())[:2]:  # Show first 2 categories
                if books:
                    example = books[0]
                    caption_preview = example['caption'][:100] + "..." if len(example['caption']) > 100 else example['caption']
                    print(f"\n{category}:")
                    print(f"  Example: {caption_preview}")
                    print(f"  Date: {example['date']}")
        
    except Exception as e:
        print(f"❌ Error during categorization: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 