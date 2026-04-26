# Instagram Book Recommendations Extractor

This Python script extracts book recommendations from your Instagram posts and organizes them into a separate folder with images and your opinions about the books.

## What it does

1. **Parses Instagram posts**: Reads through your `instagram/posts_1.html` file
2. **Identifies book recommendations**: Looks for posts with the `#bookrecommendations` hashtag
3. **Extracts content**: Captures captions, dates, and associated images
4. **Organizes data**: Creates a `book_recommendations` folder with:
   - All book-related images
   - A summary text file
   - A structured JSON file

## Requirements

- Python 3.6+
- BeautifulSoup4
- lxml parser

## Installation

1. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Make sure you have the `instagram` folder with your posts data
2. Run the script:
```bash
python extract_book_recommendations.py
```

## Output

The script will create a `book_recommendations` folder containing:

- **Images**: All book-related images from your posts, renamed with dates and captions
- **book_recommendations_summary.txt**: Human-readable summary of all book recommendations
- **book_recommendations.json**: Structured data for programmatic use

## Example Output

```
Instagram Book Recommendations Extractor
========================================

Created folder: book_recommendations

Extracting book recommendation posts...
Found book recommendation post from Jan 22, 2025 11:18 am
Caption: A great book with lessons on how to find balance, main key takeaways: Finding balance is about patience and maintenance...
Images: 1
--------------------------------------------------

Found 3 book recommendation posts

Copying images to book recommendations folder...
Copied: 474682905_18487831408013399_9116390239860485094_n_18089323159551667.jpg -> Jan_22_2025_11_18_am_A-great-book-with-lessons-on-how-to-find-balance_474682905_18487831408013399_9116390239860485094_n_18089323159551667.jpg

Creating summary files...
Created summary file: book_recommendations/book_recommendations_summary.txt
Created JSON file: book_recommendations/book_recommendations.json

✅ Extraction complete! Check the 'book_recommendations' folder for results.
Total book recommendations extracted: 3
```

## Data Structure

Each book recommendation includes:
- **Date**: When you posted about the book
- **Caption**: Your full review/opinion about the book
- **Images**: Book covers or related photos
- **Video**: Any video content (if present)

## Use Cases

- **Personal library**: Keep track of books you've recommended
- **Website content**: Use the extracted data to create a book recommendations page
- **Social media**: Repurpose your book reviews for other platforms
- **Data analysis**: Analyze your reading patterns and preferences

## Troubleshooting

- **No posts found**: Make sure your Instagram posts contain the `#bookrecommendations` hashtag
- **Images not found**: Ensure the image files exist in the expected folder structure
- **Encoding issues**: The script uses UTF-8 encoding for international characters

## Customization

You can modify the script to:
- Look for different hashtags
- Extract additional metadata
- Change the output folder structure
- Add more file formats 