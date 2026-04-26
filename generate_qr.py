import sys
import argparse

try:
    import qrcode
except ImportError:
    print("Error: The 'qrcode' library is not installed.")
    print("Please install it by running: pip install \"qrcode[pil]\"")
    sys.exit(1)

def generate_qr_code(url, output_file="qr_code.png"):
    """
    Generates a QR code from the given URL and saves it as an image.
    """
    print(f"Generating QR code for: {url}")
    
    # Configure the QR code generator
    qr = qrcode.QRCode(
        version=1,  # Controls the size of the QR Code (1 is 21x21)
        error_correction=qrcode.constants.ERROR_CORRECT_L,  # About 7% or less errors can be corrected
        box_size=10,  # Size of each box in pixels
        border=4,  # Thickness of the border (minimum is 4)
    )
    
    # Add the target URL
    qr.add_data(url)
    qr.make(fit=True)

    # Create an image from the QR Code instance
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save the image
    img.save(output_file)
    print(f"Successfully saved QR code to: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a QR code from a website URL.")
    parser.add_argument("-u", "--url", type=str, help="The website URL to encode in the QR code")
    parser.add_argument("-o", "--output", type=str, default="website_qr.png", help="Output image filename (default: website_qr.png)")

    args = parser.parse_args()

    # Use command line argument if provided, otherwise prompt the user interactively
    website_url = args.url
    if not website_url:
        try:
            website_url = input("Enter the website link (e.g., https://denizjafari.com): ").strip()
            if not website_url:
                print("Error: A website URL is required.")
                sys.exit(1)
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(0)
    
    generate_qr_code(website_url, args.output)
