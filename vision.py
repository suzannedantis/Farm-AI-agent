import base64
import requests
from PIL import Image
import io


def encode_image_to_base64(image_file) -> str:
    img = Image.open(image_file)
    if max(img.size) > 1024:
        img.thumbnail((1024, 1024), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def diagnose_crop_image(image_file, crop_type: str, groq_api_key: str) -> dict:
    """
    Analyze a crop photo using Llama 4 Vision via Groq.
    Returns a dict with:
      - 'summary': human-readable bullet diagnosis (for display)
      - 'query': auto-generated symptom description to feed the agent
      - 'raw': full model text
    """
    try:
        b64 = encode_image_to_base64(image_file)

        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                f"You are an expert plant pathologist.\n"
                                f"Crop type: {crop_type if crop_type else 'unknown'}.\n\n"
                                f"Analyze this crop image and respond in EXACTLY this format:\n\n"
                                f"SYMPTOMS: <one sentence describing visible symptoms>\n"
                                f"DISEASE: <most likely disease or deficiency name>\n"
                                f"CATEGORY: <one of: fungal / bacterial / viral / pest / nutrient / abiotic>\n"
                                f"SEVERITY: <mild / moderate / severe>\n"
                                f"BULLETS:\n"
                                f"- <observation 1>\n"
                                f"- <observation 2>\n"
                                f"- <observation 3>\n\n"
                                f"Be factual and concise. Do not hallucinate."
                            ),
                        },
                    ],
                }
            ],
            "max_tokens": 400,
            "temperature": 0.1,
        }

        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]

        # Parse structured fields
        symptoms = _extract_field(raw, "SYMPTOMS")
        disease = _extract_field(raw, "DISEASE")
        category = _extract_field(raw, "CATEGORY")
        severity = _extract_field(raw, "SEVERITY")

        # Auto-generate the query that replaces the manual text area
        crop_label = crop_type if crop_type else "crop"
        query = (
            f"{crop_label} showing {symptoms} "
            f"Suspected: {disease}. Severity: {severity}."
        ).strip()

        return {
            "summary": raw,
            "query": query,
            "disease": disease,
            "category": category,
            "severity": severity,
            "raw": raw,
            "error": None,
        }

    except Exception as e:
        return {
            "summary": f"Image analysis failed: {e}",
            "query": "",
            "disease": "",
            "category": "",
            "severity": "",
            "raw": "",
            "error": str(e),
        }


def _extract_field(text: str, field: str) -> str:
    for line in text.splitlines():
        if line.upper().startswith(field + ":"):
            return line.split(":", 1)[1].strip()
    return ""