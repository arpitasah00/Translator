from PIL import Image
import pytesseract

# Tesseract executable path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract"

# Full absolute path to the image
img = Image.open(r"D:\Major Project\Frontend P\Translator\Backend\test.png")
text = pytesseract.image_to_string(img, lang='eng+hin')
print(text)
