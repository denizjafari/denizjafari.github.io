import qrcode
from PIL import Image, ImageDraw

# ---- SETTINGS ----
website_url = "https://denizjafari.com/"      # <-- change this
logo_path   = "/Users/deniz/Documents/code/denizjafari.github.io/world-wide-web.png"
output_path = "qr_with_logo.png"

# ---- CREATE QR CODE ----
qr = qrcode.QRCode(
    version=None,  # let it pick size automatically
    error_correction=qrcode.constants.ERROR_CORRECT_H,  # high error correction (important for logo)
    box_size=10,
    border=4,
)
qr.add_data(website_url)
qr.make(fit=True)

# Create QR code with black on white background (standard colors)
qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

# ---- OPEN & RESIZE LOGO ----
logo = Image.open(logo_path)

# Convert logo to RGBA if needed
if logo.mode != "RGBA":
    logo = logo.convert("RGBA")

# Resize logo to be ~20-25% of QR code size
qr_width, qr_height = qr_img.size
logo_size = int(qr_width * 0.22)  # 22% of QR width
logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)

# ---- CREATE SQUARE FRAME FOR LOGO ----
frame_size = logo_size + 20  # Add padding around logo for frame
frame_img = Image.new("RGB", (frame_size, frame_size), "white")
draw_frame = ImageDraw.Draw(frame_img)

# Draw white square frame with black border
frame_thickness = 3
draw_frame.rectangle(
    [0, 0, frame_size - 1, frame_size - 1],
    outline="black",
    width=frame_thickness
)

# Paste logo in center of frame
logo_x = (frame_size - logo.width) // 2
logo_y = (frame_size - logo.height) // 2
frame_img.paste(logo, (logo_x, logo_y), mask=logo)

# ---- PASTE FRAMED LOGO IN CENTER OF QR CODE ----
frame_x = (qr_width - frame_size) // 2
frame_y = (qr_height - frame_size) // 2

qr_img.paste(frame_img, (frame_x, frame_y))

# ---- SAVE RESULT ----
qr_img.save(output_path)
print(f"Saved QR code with logo as {output_path}")
