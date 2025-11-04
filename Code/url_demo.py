import os
import io
import torch
import requests
import pandas as pd
from PIL import Image
from torchvision import models, transforms
import open_clip
from tqdm import tqdm

# ==================================
# 1. 모델 로드
# ==================================
device = "cuda" if torch.cuda.is_available() else "cpu"

# Places365
places_model = models.resnet50(num_classes=365)
checkpoint = torch.utils.model_zoo.load_url(
    'http://places2.csail.mit.edu/models_places365/resnet50_places365.pth.tar',
    map_location=torch.device('cpu')
)
state_dict = {k.replace('module.', ''): v for k, v in checkpoint['state_dict'].items()}
places_model.load_state_dict(state_dict)
places_model.eval()

# OpenCLIP
clip_model, _, clip_preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
tokenizer = open_clip.get_tokenizer('ViT-B-32')
clip_model = clip_model.to(device).eval()

# Places365 클래스 목록
classes_file = 'https://raw.githubusercontent.com/csailvision/places365/master/categories_places365.txt'
classes = [line.strip().split(' ')[0][3:] for line in requests.get(classes_file).text.split('\n') if line]

# Places365 전처리
places_preprocess = transforms.Compose([
    transforms.Resize((500, 500)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225])
])

# ==================================
# 2. OpenCLIP 라벨셋 미리 임베딩
# ==================================
label_df = pd.read_csv("https://raw.githubusercontent.com/CSID-DGU/2025-2-DSCD-San3Su1-03/main/Code/Clip_label_1.csv", dtype=str)
variant_cols = [c for c in label_df.columns if c.startswith("Variant")]

text_labels = []
for _, row in label_df.iterrows():
    for c in variant_cols:
        if pd.notna(row[c]) and str(row[c]).strip():
            text_labels.append(row[c].strip())

with torch.no_grad():
    text_tokens = tokenizer(text_labels).to(device)
    text_features = clip_model.encode_text(text_tokens)
    text_features /= text_features.norm(dim=-1, keepdim=True)

# ==================================
# 3. URL 기반 라벨링 함수
# ==================================
def label_from_url(idx, url):
    try:
        # --- 이미지 다운로드 ---
        response = requests.get(url, timeout=10)
        image = Image.open(io.BytesIO(response.content)).convert("RGB")

        # --- 1단계: Places365 ---
        p_input = places_preprocess(image).unsqueeze(0)
        with torch.no_grad():
            output = places_model(p_input)
            probs = torch.nn.functional.softmax(output[0], dim=0)
        top3_prob, top3_catid = torch.topk(probs, 3)
        place_labels = [classes[i] for i in top3_catid]
        
        # --- 2단계: OpenCLIP ---
        matched_variants = []
        for plabel in place_labels:
            candidates = label_df[label_df["Places_Label"].str.contains(plabel, case=False, na=False)]
            for _, r in candidates.iterrows():
                for c in variant_cols:
                    if pd.notna(r[c]) and str(r[c]).strip():
                        matched_variants.append(str(r[c]).strip())
        if not matched_variants:
            return None
        
        # 후보 제한
        candidate_indices = [i for i, lbl in enumerate(text_labels) if lbl in matched_variants]
        if not candidate_indices:
            return None
        
        filtered_text_features = text_features[candidate_indices]
        filtered_labels = [text_labels[i] for i in candidate_indices]
        
        with torch.no_grad():
            image_tensor = clip_preprocess(image).unsqueeze(0).to(device)
            image_features = clip_model.encode_image(image_tensor)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            similarity = (100.0 * image_features @ filtered_text_features.T).softmax(dim=-1)
        
        top_probs, top_indices = similarity[0].topk(min(3, len(filtered_labels)))

        row = {"index": idx, "url": url}
        for i, idx2 in enumerate(top_indices):
            row[f"라벨{i+1}"] = filtered_labels[idx2]
            row[f"확률{i+1}(%)"] = round(top_probs[i].item() * 100, 2)
        return row
    
    except Exception as e:
        print(f"[오류] {idx}: {url} ({e})")
        return None

# ==================================
# 4. 실행부 (DB or CSV 입력)
# ==================================
def main():
    # 예시: DB에서 URL 리스트 불러온다고 가정
    urls = [
        "https://example.com/image1.jpg",
        "https://example.com/image2.png",
        # ...
    ]
    
    results = []
    for i, url in enumerate(tqdm(urls, total=len(urls)), start=1):
        r = label_from_url(i, url)
        if r:
            results.append(r)
    
    output_path = "C:/Users/jin01/Videos/Captures/DGU/2025-2/DSCD/Project/2025-2-DSCD-San3Su1-03/Code/final_output.csv"
    pd.DataFrame(results).to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n최종 CSV 저장 완료: {output_path}")

if __name__ == "__main__":
    main()
