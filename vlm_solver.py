import base64
import json
import logging
import os
from openai import OpenAI

class VLMCaptchaResolver:
    def __init__(self):
        self.api_key = os.getenv("VLM_API_KEY")
        self.base_url = os.getenv("VLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
        self.model = os.getenv("VLM_MODEL", "glm-4v")
        
        if not self.api_key:
            logging.warning("VLM_API_KEY is not set! VLM solver will fail.")
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def encode_image(self, image_data):
        """
        Encode image bytes to base64 string
        """
        return base64.b64encode(image_data).decode('utf-8')

    def solve_gap(self, image):
        """
        Solve the gap position using VLM
        :param image: PIL Image object
        :return: Gap center X coordinate (normalized to image width if needed, but here we return pixel offset)
        """
        try:
            # Convert PIL Image to bytes
            from io import BytesIO
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            base64_image = self.encode_image(buffered.getvalue())
            
            # Prompt for the model
            prompt = """
            You are an expert in image processing. 
            Task: Find the missing puzzle piece (the gap) in this image.
            Output: Return ONLY a JSON object with the bounding box of the gap. 
            Format: {"ymin": <int>, "xmin": <int>, "ymax": <int>, "xmax": <int>} 
            The coordinates should be normalized to 1000x1000 scale.
            """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            logging.info(f"Raw VLM Content: {content}")
            
            # Clean up json string if needed (sometimes models wrap in ```json ... ```)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
                
            result = json.loads(content)
            logging.info(f"Parsed VLM Result: {result}")
            
            # Calculate center X in 1000x1000 scale
            x_center_normalized = (result['xmin'] + result['xmax']) / 2
            
            # Convert to actual image width
            real_width = image.width
            logging.info(f"Image Width: {real_width}, Normalized Center X: {x_center_normalized}")
            
            real_x_offset = (x_center_normalized / 1000) * real_width
            
            return real_x_offset
            
        except Exception as e:
            logging.error(f"VLM Solver failed: {e}")
            # Fallback or re-raise? For now return 0 or raise
            raise e
