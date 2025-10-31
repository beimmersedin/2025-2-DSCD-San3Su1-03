# core/vision.py
import json, base64
from io import BytesIO
from PIL import Image
from typing import Dict
from openai import OpenAI

def normalize_image(image_bytes: bytes, max_side=1600, quality=88) -> bytes:
    im = Image.open(BytesIO(image_bytes)).convert("RGB")
    w, h = im.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        im = im.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
    out = BytesIO()
    im.save(out, format="JPEG", quality=quality)
    return out.getvalue()


def _to_data_url(img_bytes: bytes) -> str:
    b64 = base64.b64encode(img_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"

def analyze_photo_bytes(img_bytes: bytes, client: OpenAI) -> Dict:
    data_url = _to_data_url(img_bytes)
    system_text = (
      "You are a precise vision tagger for Korean travel diaries. "
      "Return strict JSON only with keys: "
      "is_food(boolean), food_items(array of strings), place_type(string), "
      "objects(array of strings), tags(array of short Korean adjectives/nouns)."
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content":system_text}, 
            {"role": "user", "content": [
                {"type":"text","text":"Analyze this image and return STRICT JSON only."},
                {"type":"image_url","image_url":{"url": data_url}}
            ]}
        ], 
        temperature=0.2
    )
    return json.loads(resp.choices[0].message.content)

def generate_diary(photo_metadata: dict, user_request: dict, client: OpenAI) -> Dict:
    sys = f"""
    You are a professional Korean travel influencer and food blogger.
    Output strictly JSON with keys: title, content, hashtags (array).
    Language: {user_request['language']}.
    Platform: {user_request['platform']}.
    Tone/Mood: {user_request['mood']}.
    Required elements: {', '.join(user_request['include_elements'])}.
    """
    usr = json.dumps(photo_metadata, ensure_ascii=False)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type":"json_object"},
        messages=[
            {"role":"system","content": sys},
            {"role":"user","content": usr}
        ],
        temperature=0.5
    )
    
    return json.loads(resp.choices[0].message.content)
