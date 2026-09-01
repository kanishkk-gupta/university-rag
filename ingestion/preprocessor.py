"""
ingestion/preprocessor.py — Image preprocessing for robust OCR and table extraction.

Handles converting PIL images to OpenCV format, applying thresholding/binarization
to remove watermarks or scan artifacts, and returning cleaned PIL images for Tesseract.
"""

import cv2
import numpy as np
from PIL import Image

def preprocess_for_ocr(pil_image: Image.Image, apply_threshold: bool = True) -> Image.Image:
    """
    Preprocess a PIL image for OCR.
    
    If apply_threshold is True, applies adaptive thresholding which helps
    eliminate faint background watermarks and artifacts that confuse Tesseract,
    particularly on low-quality scans.
    """
    # Convert PIL Image to OpenCV format (numpy array)
    # Convert RGB to grayscale directly
    open_cv_image = np.array(pil_image.convert("L"))
    
    if not apply_threshold:
        # Just return the grayscale image
        return Image.fromarray(open_cv_image)
        
    # Apply Adaptive Gaussian Thresholding
    # Block size of 31 and C of 2 works well to keep dark text and drop faint watermarks
    thresh = cv2.adaptiveThreshold(
        open_cv_image, 
        255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 
        31, 
        2
    )
    
    # Convert back to PIL Image
    return Image.fromarray(thresh)
