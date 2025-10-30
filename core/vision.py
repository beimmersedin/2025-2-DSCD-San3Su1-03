# core/vision.py
import json, os, tempfile
from io import BytesIO
from PIL import Image
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


def upload_bytes_for_vision(img_bytes: bytes, client: OpenAI) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(img_bytes)
        tmp_path = tmp.name
    try:
        f = client.files.create(file=open(tmp_path, "rb"), purpose="vision")
        return f.id
    finally:
        try: os.unlink(tmp_path)
        except: pass


def analyze_photo_fileid(file_id: str, client: OpenAI) -> dict:
    sys = (
      "You are a precise vision tagger for Korean travel diaries. "
      "Return strict JSON only with keys: is_food(boolean), food_items(array of strings), "
      "place_type(string), objects(array of strings), tags(array of short Korean adjectives/nouns)."
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": [
                {"type": "text", "text": "Analyze this image and return STRICT JSON only."},
                {"type": "file", "file": {"id": file_id}},
            ]},
        ],
        temperature=0.2
    )
    return json.loads(resp.choices[0].message.content)


def generate_diary(photo_metadata: dict, user_request: dict, client: OpenAI) -> dict:
    sys = f"""
    You are a professional Korean travel influencer and food blogger.
    Output strictly JSON with keys: title, content, hashtags (array).
    Language: {user_request['language']}.
    Platform: {user_request['platform']}.
    Tone/Mood: {user_request['mood']}.
    Required elements: {', '.join(user_request['include_elements'])}.
    """
    usr = f"{json.dumps(photo_metadata, ensure_ascii=False)}"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": usr}
        ],
        temperature=0.5
    )
    return json.loads(resp.choices[0].message.content)
