"""OCR processing for genealogical documents.

This module handles OCR extraction from PDFs and images using Tesseract.
It preserves original documents and saves raw OCR output for traceability.
"""

import json
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytesseract
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


class OCRResult:
    """Structured OCR result with metadata."""

    def __init__(
        self,
        source_path: Path,
        page_number: int,
        text: str,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Initialize OCR result.

        Args:
            source_path: Path to the source document
            page_number: Page number (1-indexed)
            text: Extracted text
            confidence: OCR confidence score (0-100)
            metadata: Additional metadata
        """
        self.source_path = source_path
        self.page_number = page_number
        self.text = text
        self.confidence = confidence
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": str(self.source_path),
            "page": self.page_number,
            "text": self.text,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OCRResult":
        """Create OCRResult from dictionary."""
        return cls(
            source_path=Path(data["source"]),
            page_number=data["page"],
            text=data["text"],
            confidence=data.get("confidence"),
            metadata=data.get("metadata", {}),
        )


class OCRProcessor:
    """Process documents with OCR and save results."""

    def __init__(
        self,
        output_dir: Path | None = None,
        tesseract_config: str = "--psm 3",
        save_images: bool = False,
        engine: str = "tesseract",
        azure_endpoint: str | None = None,
        azure_key: str | None = None,
    ):
        """Initialize OCR processor.

        Args:
            output_dir: Directory to save OCR outputs (default: ./ocr_output)
            tesseract_config: Tesseract configuration string
            save_images: Whether to save extracted page images
            engine: OCR engine to use ('tesseract' or 'azure')
            azure_endpoint: Azure AI Document Intelligence endpoint
            azure_key: Azure AI Document Intelligence key
        """
        self.output_dir = output_dir or Path("./ocr_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tesseract_config = tesseract_config
        self.save_images = save_images
        self.engine = engine.lower()

        # Initialize Azure client if needed
        self.azure_client = None
        if self.engine == "azure":
            if not azure_endpoint or not azure_key:
                logger.warning(
                    "Azure OCR requested but credentials missing. Falling back to Tesseract."
                )
                self.engine = "tesseract"
            else:
                self.azure_client = DocumentIntelligenceClient(
                    endpoint=azure_endpoint, credential=AzureKeyCredential(azure_key)
                )

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results.

        Args:
            image: PIL Image object

        Returns:
            Preprocessed PIL Image object
        """
        # Convert PIL to OpenCV format
        cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # 1. Grayscale
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

        # 2. Orientation Detection and Correction (Deskew)
        # We use Tesseract's OSD for this as it's quite reliable
        try:
            osd = pytesseract.image_to_osd(image)
            angle = int(osd.split("\nOrientation in degrees: ")[1].split("\n")[0])
            if angle != 0:
                # Rotate the image
                (h, w) = gray.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, -angle, 1.0)
                gray = cv2.warpAffine(
                    gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
                )
        except Exception as e:
            logger.debug(f"Orientation detection failed: {e}")

        # 3. Adaptive Thresholding (helps with faint text/handwriting)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # 4. Denoising
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)

        # Convert back to PIL
        return Image.fromarray(denoised)

    def process_text_file(self, text_path: Path) -> OCRResult:
        """Read text from a plain text file.

        Args:
            text_path: Path to the text file

        Returns:
            OCRResult containing the text content
        """
        with open(text_path, encoding="utf-8") as f:
            text = f.read()

        return OCRResult(
            source_path=text_path,
            page_number=1,
            text=text.strip(),
            confidence=None,  # No OCR confidence for plain text files
            metadata={
                "file_type": "text",
                "encoding": "utf-8",
            },
        )

    def process_image(self, image_path: Path) -> OCRResult:
        """Extract text from a single image.

        Args:
            image_path: Path to the image file

        Returns:
            OCRResult containing extracted text and metadata
        """
        image = Image.open(image_path)

        if self.engine == "azure" and self.azure_client:
            return self._process_azure(image_path, [image])[0]

        # Tesseract path with preprocessing
        processed_image = self.preprocess_image(image)

        # Extract text with detailed data
        ocr_data = pytesseract.image_to_data(
            processed_image, config=self.tesseract_config, output_type=pytesseract.Output.DICT
        )

        # Get full text
        text = pytesseract.image_to_string(processed_image, config=self.tesseract_config)

        # Calculate average confidence
        confidences = [c for c in ocr_data["conf"] if c != -1]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            source_path=image_path,
            page_number=1,
            text=text.strip(),
            confidence=avg_confidence,
            metadata={
                "image_width": image.size[0],
                "image_height": image.size[1],
                "format": image.format,
                "mode": image.mode,
                "engine": "tesseract",
                "preprocessed": True,
            },
        )

    def _process_azure(self, doc_path: Path, images: list[Image.Image]) -> list[OCRResult]:
        """Process document using Azure AI Document Intelligence.

        Args:
            doc_path: Path to the source document
            images: List of PIL images (for metadata)

        Returns:
            List of OCRResult objects
        """
        if not self.azure_client:
            raise ValueError("Azure client not initialized")

        with open(doc_path, "rb") as f:
            poller = self.azure_client.begin_analyze_document(
                "prebuilt-read", AnalyzeDocumentRequest(bytes_source=f.read())
            )
            result: AnalyzeResult = poller.result()

        ocr_results = []
        for page in result.pages:
            # Combine lines into text
            lines = [line.content for line in page.lines]
            text = "\n".join(lines)

            # Azure doesn't give a single confidence score for the page,
            # but we can average the word confidences
            confidences = []
            for word in page.words:
                if hasattr(word, "confidence"):
                    confidences.append(word.confidence * 100)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            ocr_results.append(
                OCRResult(
                    source_path=doc_path,
                    page_number=page.page_number,
                    text=text,
                    confidence=avg_confidence,
                    metadata={
                        "image_width": page.width,
                        "image_height": page.height,
                        "unit": page.unit,
                        "engine": "azure",
                        "angle": page.angle,
                    },
                )
            )
        return ocr_results

    def process_pdf(self, pdf_path: Path, dpi: int = 300) -> list[OCRResult]:
        """Extract text from all pages of a PDF.

        Args:
            pdf_path: Path to the PDF file
            dpi: DPI for PDF to image conversion (higher = better quality)

        Returns:
            List of OCRResult, one per page
        """
        if self.engine == "azure" and self.azure_client:
            return self._process_azure(pdf_path, [])

        # Convert PDF pages to images
        images = convert_from_path(pdf_path, dpi=dpi)

        results = []
        for page_num, image in enumerate(images, start=1):
            # Optionally save the page image
            if self.save_images:
                image_output_path = self.output_dir / f"{pdf_path.stem}_page_{page_num}.png"
                image.save(image_output_path)

            # Preprocess for Tesseract
            processed_image = self.preprocess_image(image)

            # Extract text with detailed data
            ocr_data = pytesseract.image_to_data(
                processed_image, config=self.tesseract_config, output_type=pytesseract.Output.DICT
            )

            # Get full text
            text = pytesseract.image_to_string(processed_image, config=self.tesseract_config)

            # Calculate average confidence
            confidences = [c for c in ocr_data["conf"] if c != -1]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            result = OCRResult(
                source_path=pdf_path,
                page_number=page_num,
                text=text.strip(),
                confidence=avg_confidence,
                metadata={
                    "image_width": image.size[0],
                    "image_height": image.size[1],
                    "total_pages": len(images),
                    "dpi": dpi,
                    "engine": "tesseract",
                    "preprocessed": True,
                },
            )
            results.append(result)

        return results

    def process_document(self, doc_path: Path) -> list[OCRResult]:
        """Process a document (PDF or image) and save OCR output.

        Args:
            doc_path: Path to the document

        Returns:
            List of OCRResult objects

        Raises:
            ValueError: If file type is not supported
        """
        doc_path = Path(doc_path)

        if not doc_path.exists():
            raise FileNotFoundError(f"Document not found: {doc_path}")

        # Determine file type and process accordingly
        suffix = doc_path.suffix.lower()

        if suffix == ".pdf":
            results = self.process_pdf(doc_path)
        elif suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}:
            results = [self.process_image(doc_path)]
        elif suffix == ".txt":
            results = [self.process_text_file(doc_path)]
        else:
            raise ValueError(
                f"Unsupported file type: {suffix}. "
                "Supported types: .pdf, .png, .jpg, .jpeg, .tiff, .tif, .bmp, .txt"
            )

        # Save raw OCR output as JSON
        self._save_ocr_json(doc_path, results)

        return results

    def _save_ocr_json(self, source_path: Path, results: list[OCRResult]) -> Path:
        """Save OCR results to JSON file.

        Args:
            source_path: Original document path
            results: List of OCR results

        Returns:
            Path to saved JSON file
        """
        output_filename = f"{source_path.stem}_ocr.json"
        output_path = self.output_dir / output_filename

        data = {
            "source_document": str(source_path.absolute()),
            "total_pages": len(results),
            "pages": [result.to_dict() for result in results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    def load_ocr_json(self, json_path: Path) -> list[OCRResult]:
        """Load OCR results from JSON file.

        Args:
            json_path: Path to OCR JSON file

        Returns:
            List of OCRResult objects
        """
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        return [OCRResult.from_dict(page_data) for page_data in data["pages"]]
