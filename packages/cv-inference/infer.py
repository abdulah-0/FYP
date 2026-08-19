"""
Computer Vision Fire & Smoke Inference Module.
Wraps the pretrained SigLIP2 Forest-Fire-Detection classifier (prithivMLmods/Forest-Fire-Detection).
Accepts image inputs (file path, PIL Image, bytes, or numpy array) and produces class probabilities
and a continuous normalized vision risk score for the multi-modal fusion engine.
"""

import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
import numpy as np
from PIL import Image

logger = logging.getLogger("cv_inference")

DEFAULT_MODEL_NAME = "prithivMLmods/Forest-Fire-Detection"
DEFAULT_ID2LABEL = {"0": "Fire", "1": "Normal", "2": "Smoke"}


class VisionFireClassifier:
    """
    Inference wrapper for Pretrained SigLIP2 Forest Fire & Smoke Detection.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        cache_dir: Optional[str] = None,
        device: Optional[str] = None,
        lazy_load: bool = True,
        auto_download: bool = False
    ):
        self.model_name = model_name
        self.cache_dir = cache_dir or str(Path(__file__).parent / "model_cache")
        self.device = device
        self.auto_download = auto_download
        self.model = None
        self.processor = None
        self.id2label = DEFAULT_ID2LABEL
        self._is_loaded = False

        if not lazy_load:
            self._load_model()

    def _get_device(self):
        if self.device:
            return self.device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _load_model(self):
        if self._is_loaded:
            return

        import torch
        from transformers import AutoModelForImageClassification, SiglipImageProcessorPil

        device = self._get_device()
        
        # Try local cache first
        try:
            self.processor = SiglipImageProcessorPil.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                local_files_only=True
            )
            self.model = AutoModelForImageClassification.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                local_files_only=True
            )
            self.model.to(device)
            self.model.eval()

            if hasattr(self.model.config, "id2label") and self.model.config.id2label:
                self.id2label = {str(k): str(v) for k, v in self.model.config.id2label.items()}

            self._is_loaded = True
            return
        except Exception:
            pass

        if self.auto_download:
            try:
                self.processor = SiglipImageProcessorPil.from_pretrained(
                    self.model_name,
                    cache_dir=self.cache_dir
                )
                self.model = AutoModelForImageClassification.from_pretrained(
                    self.model_name,
                    cache_dir=self.cache_dir
                )
                self.model.to(device)
                self.model.eval()

                if hasattr(self.model.config, "id2label") and self.model.config.id2label:
                    self.id2label = {str(k): str(v) for k, v in self.model.config.id2label.items()}

                self._is_loaded = True
            except Exception as e:
                logger.warning(f"Could not download remote model '{self.model_name}' ({e}). Using offline vision analysis mode.")
                self._is_loaded = False
                self.model = None

    def _prepare_image(self, image_input: Union[str, Path, bytes, Image.Image, np.ndarray]) -> Image.Image:
        """Converts diverse image formats into an RGB PIL Image."""
        if isinstance(image_input, (str, Path)):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image path does not exist: {image_input}")
            return Image.open(image_input).convert("RGB")
        elif isinstance(image_input, bytes):
            return Image.open(io.BytesIO(image_input)).convert("RGB")
        elif isinstance(image_input, Image.Image):
            return image_input.convert("RGB")
        elif isinstance(image_input, np.ndarray):
            if len(image_input.shape) == 3 and image_input.shape[2] == 3:
                return Image.fromarray(image_input.astype(np.uint8)).convert("RGB")
            elif len(image_input.shape) == 2:
                return Image.fromarray(image_input.astype(np.uint8)).convert("RGB")
            else:
                raise ValueError(f"Unsupported numpy array image shape: {image_input.shape}")
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    def _heuristic_vision_fallback(self, image: Image.Image) -> Dict[str, float]:
        """
        Color / HSV combustion signature heuristic for offline mode or network fallback.
        Calculates red/orange/yellow flame and desaturated grey smoke pixel ratios.
        """
        img_np = np.array(image.resize((128, 128)))
        r, g, b = img_np[:, :, 0], img_np[:, :, 1], img_np[:, :, 2]

        # Flame detection condition: High red, moderate green, low blue
        flame_mask = (r > 180) & (g > 50) & (r > g * 1.2) & (g > b * 1.3)
        flame_ratio = np.mean(flame_mask)

        # Smoke detection condition: High lightness, low color saturation (grey haze)
        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        saturation = np.where(max_c == 0, 0, (max_c - min_c) / (max_c + 1e-5))
        smoke_mask = (max_c > 120) & (saturation < 0.25)
        smoke_ratio = np.mean(smoke_mask)

        p_fire = float(np.clip(flame_ratio * 4.0, 0.01, 0.98))
        p_smoke = float(np.clip(smoke_ratio * 2.5, 0.01, 0.95))
        p_normal = float(np.clip(1.0 - (p_fire + p_smoke), 0.01, 0.99))

        # Softmax normalization
        total = p_fire + p_smoke + p_normal
        return {
            "Fire": round(p_fire / total, 4),
            "Normal": round(p_normal / total, 4),
            "Smoke": round(p_smoke / total, 4)
        }

    def classify_image(
        self,
        image_input: Union[str, Path, bytes, Image.Image, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Classifies an image and outputs probabilities and fusion vision risk score.

        Returns:
            Dict containing:
                - probabilities: Dict[str, float] (e.g. {"Fire": 0.85, "Normal": 0.05, "Smoke": 0.10})
                - predicted_label: str ("Fire", "Normal", "Smoke")
                - confidence: float
                - vision_score: float [0.0, 1.0]
        """
        pil_img = self._prepare_image(image_input)

        if not self._is_loaded and self.model is None:
            try:
                self._load_model()
            except Exception:
                pass

        if self._is_loaded and self.model is not None and self.processor is not None:
            import torch
            device = self._get_device()
            inputs = self.processor(images=pil_img, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.nn.functional.softmax(logits, dim=1).squeeze().tolist()

            if isinstance(probs, float):
                probs = [probs]

            prob_dict = {}
            for i, p in enumerate(probs):
                label_name = self.id2label.get(str(i), f"Class_{i}")
                prob_dict[label_name] = round(float(p), 4)

            fire_p = prob_dict.get("Fire", 0.0)
            smoke_p = prob_dict.get("Smoke", 0.0)
            normal_p = prob_dict.get("Normal", round(1.0 - (fire_p + smoke_p), 4))
        else:
            # Fallback heuristic
            prob_dict = self._heuristic_vision_fallback(pil_img)
            fire_p = prob_dict["Fire"]
            smoke_p = prob_dict["Smoke"]
            normal_p = prob_dict["Normal"]

        prob_dict = {
            "Fire": round(fire_p, 4),
            "Normal": round(normal_p, 4),
            "Smoke": round(smoke_p, 4)
        }

        best_label = max(prob_dict.items(), key=lambda x: x[1])[0]
        confidence = prob_dict[best_label]

        # Continuous normalized vision risk score for fusion engine [0.0 - 1.0]
        # Active flame = 1.0 weight, Smoke = 0.65 weight
        vision_score = round(float(np.clip(fire_p * 1.0 + smoke_p * 0.65, 0.0, 1.0)), 4)

        return {
            "probabilities": prob_dict,
            "predicted_label": best_label,
            "confidence": confidence,
            "vision_score": vision_score
        }


def classify_image(image_input: Union[str, Path, bytes, Image.Image, np.ndarray]) -> Dict[str, Any]:
    """Convenience functional interface."""
    classifier = VisionFireClassifier()
    return classifier.classify_image(image_input)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Classify Fire & Smoke from an Image")
    parser.add_argument("image_path", type=str, help="Path to image file")
    args = parser.parse_args()

    clf = VisionFireClassifier()
    res = clf.classify_image(args.image_path)
    print("\n--- Vision Inference Result ---")
    print(f"Predicted Class : {res['predicted_label']} ({res['confidence'] * 100:.1f}%)")
    print(f"Vision Score    : {res['vision_score']} / 1.0000")
    print(f"Probabilities   : {res['probabilities']}")
