import qrcode
from PIL import Image, ImageDraw, ImageFont

# ---- SETTINGS ----
website_url = "https://denizjafari.com/"
logo_path   = "/Users/deniz/Documents/code/denizjafari.github.io/world-wide-web.png"
output_path = "business_card.png"

# Standard business card size: 3.5" x 2" at 300 DPI -> 1050 x 600 pixels
CARD_WIDTH = 1050
CARD_HEIGHT = 600
DPI = 300

# ---- CREATE QR CODE ----
qr = qrcode.QRCode(
    version=None,
    error_correction=qrcode.constants.ERROR_CORRECT_H,  # high error correction
    box_size=8,
    border=2,
)
qr.add_data(website_url)
qr.make(fit=True)

qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
# Convert white background to transparent
data = qr_img.getdata()
new_data = []
for item in data:
    # Change white (255, 255, 255) to transparent (0, 0, 0, 0)
    if item[:3] == (255, 255, 255):
        new_data.append((0, 0, 0, 0))
    else:
        new_data.append((0, 0, 0, 255))  # Make black pixels fully opaque
qr_img.putdata(new_data)

# Make QR bigger: ~95% of card height
qr_target_size = int(CARD_HEIGHT * 0.75)
qr_img = qr_img.resize((qr_target_size, qr_target_size), Image.Resampling.LANCZOS)
qr_width, qr_height = qr_img.size

# ---- OPEN & RESIZE LOGO FOR QR CODE ----
logo = Image.open(logo_path)
if logo.mode != "RGBA":
    logo = logo.convert("RGBA")

logo_size = int(qr_width * 0.22)
logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)

# Convert logo to black & white (preserving transparency)
logo_data = logo.getdata()
new_logo_data = []
for item in logo_data:
    if len(item) == 4:  # RGBA
        r, g, b, a = item
        if a == 0:  # Transparent
            new_logo_data.append((0, 0, 0, 0))
        else:  # Convert to black
            new_logo_data.append((0, 0, 0, 255))
    else:
        new_logo_data.append((0, 0, 0, 255))
logo.putdata(new_logo_data)

frame_size = logo_size + 20
frame_img = Image.new("RGBA", (frame_size, frame_size), (0, 0, 0, 0))  # Transparent background
draw_frame = ImageDraw.Draw(frame_img)

frame_thickness = 3
draw_frame.rectangle(
    [0, 0, frame_size - 1, frame_size - 1],
    outline="black",
    width=frame_thickness
)

logo_x = (frame_size - logo.width) // 2
logo_y = (frame_size - logo.height) // 2
frame_img.paste(logo, (logo_x, logo_y), mask=logo)

frame_x = (qr_width - frame_size) // 2
frame_y = (qr_height - frame_size) // 2
qr_img.paste(frame_img, (frame_x, frame_y))

# ---- CREATE BUSINESS CARD ----
card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))  # Transparent background
draw = ImageDraw.Draw(card)

# Frame thickness (needed for layout calculations)
frame_thickness = 10

# ---- LOAD FONTS ----
# Convert mm to points: 1 mm = 72/25.4 points ≈ 2.8346 points
heading_size_mm = 33
subtitle_size_mm = 17
heading_size_pt = int(heading_size_mm * 72 / 25.4)  # 10mm ≈ 28 points
subtitle_size_pt = int(subtitle_size_mm * 72 / 25.4)  # 7mm ≈ 20 points

try:
    heading_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", heading_size_pt)
    subtitle_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", subtitle_size_pt)
except:
    try:
        heading_font = ImageFont.truetype("/Library/Fonts/Arial.ttf", heading_size_pt)
        subtitle_font = ImageFont.truetype("/Library/Fonts/Arial.ttf", subtitle_size_pt)
    except:
        heading_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

# ---- TEXT CONTENT ----
name_text = "Deniz Jafari"
subtitle_text = "Biomedical x Robotics"

# Measure text sizes
if hasattr(draw, "textbbox"):
    name_bbox = draw.textbbox((0, 0), name_text, font=heading_font)
    name_width  = name_bbox[2] - name_bbox[0]
    name_height = name_bbox[3] - name_bbox[1]

    subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
    subtitle_width  = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_height = subtitle_bbox[3] - subtitle_bbox[1]
else:
    name_width, name_height = draw.textsize(name_text, font=heading_font)
    subtitle_width, subtitle_height = draw.textsize(subtitle_text, font=subtitle_font)

# ---- LAYOUT: TEXT LEFT, QR RIGHT, EQUAL MARGINS FROM FRAME ----
line_gap = 10 + subtitle_height  # gap between name and subtitle (base + one line of subtitle)

# Set margin from frame - start with a reasonable value
margin_from_frame = 30

# Position QR code first: right edge at CARD_WIDTH - frame - margin
qr_x = CARD_WIDTH - frame_thickness - margin_from_frame - qr_width
qr_y = (CARD_HEIGHT - qr_height) // 2

# Position name with same margin from left frame
name_x = frame_thickness + margin_from_frame
name_y = (CARD_HEIGHT - (name_height + line_gap + subtitle_height)) // 2

# Calculate gap between name end and QR start
name_end_x = name_x + name_width
gap_between = qr_x - name_end_x

# If gap is >= 50, reduce margin to make gap smaller
if gap_between >= 15:
    # Reduce margin to make gap less than 50
    # We want: (CARD_WIDTH - frame - margin - qr_width) - (frame + margin + name_width) < 50
    # Solve for margin: CARD_WIDTH - 2*frame - 2*margin - qr_width - name_width < 50
    # 2*margin > CARD_WIDTH - 2*frame - qr_width - name_width - 50
    # margin > (CARD_WIDTH - 2*frame - qr_width - name_width - 50) / 2
    target_gap = 12  # Less than 50
    margin_from_frame = int((CARD_WIDTH - 2*frame_thickness - qr_width - name_width - target_gap) / 2)
    # Recalculate positions with new margin
    qr_x = CARD_WIDTH - frame_thickness - margin_from_frame - qr_width
    name_x = frame_thickness + margin_from_frame

# Center subtitle exactly below the middle of "Deniz Jafari"
subtitle_x = name_x + (name_width - subtitle_width) // 2
subtitle_y = name_y + name_height + line_gap

# ---- DRAW ----
draw.text((name_x, name_y), name_text, fill="black", font=heading_font)
draw.text((subtitle_x, subtitle_y), subtitle_text, fill="black", font=subtitle_font)
card.paste(qr_img, (qr_x, qr_y), mask=qr_img if qr_img.mode == "RGBA" else None)

# ---- ADD FRAME AROUND CARD ----
# Draw frame using filled rectangles for each edge to ensure visibility
half_thickness = frame_thickness // 2
# Top edge
draw.rectangle(
    [0, 0, CARD_WIDTH, frame_thickness],
    fill="black"
)
# Bottom edge
draw.rectangle(
    [0, CARD_HEIGHT - frame_thickness, CARD_WIDTH, CARD_HEIGHT],
    fill="black"
)
# Left edge
draw.rectangle(
    [0, 0, frame_thickness, CARD_HEIGHT],
    fill="black"
)
# Right edge
draw.rectangle(
    [CARD_WIDTH - frame_thickness, 0, CARD_WIDTH, CARD_HEIGHT],
    fill="black"
)

# ---- ADD RECTANGLE WITH 3MM MARGIN ----
# Convert 3mm to pixels at 300 DPI: 3mm = 3 * (300/25.4) ≈ 35.43 pixels
margin_mm = 3
margin_pixels = int(margin_mm * (DPI / 25.4))

# Draw rectangle with margin from edges
draw.rectangle(
    [margin_pixels, margin_pixels, CARD_WIDTH - margin_pixels, CARD_HEIGHT - margin_pixels],
    outline="black",
    width=2
)

# ---- CONVERT TO BLACK & WHITE WITH TRANSPARENCY ----
# Ensure all non-transparent pixels are pure black
card_data = card.getdata()
new_card_data = []
for item in card_data:
    if len(item) == 4:  # RGBA
        r, g, b, a = item
        if a == 0:  # Already transparent
            new_card_data.append((0, 0, 0, 0))
        else:  # Make any visible pixel black
            new_card_data.append((0, 0, 0, 255))
    else:  # RGB
        new_card_data.append((0, 0, 0, 255))
card.putdata(new_card_data)

# ---- SAVE RESULT ----
card.save(output_path, format="PNG", dpi=(DPI, DPI))
print(f"Saved business card as {output_path} (black & white with transparent background)")
