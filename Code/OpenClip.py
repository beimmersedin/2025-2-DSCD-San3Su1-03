import os
import torch
import pandas as pd
from PIL import Image
import open_clip
from torchvision import transforms
from tqdm import tqdm

# (DSCD) 참고:
# 이 코드를 실행하려면 open_clip 라이브러리 설치 필요
# pip install open-clip-torch

# 1. 모델 및 토크나이저 불러오기
device = "cuda" if torch.cuda.is_available() else "cpu"
model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
tokenizer = open_clip.get_tokenizer('ViT-B-32')

# 2. 입력 데이터 로드
label_df = pd.read_csv("For_Clip_label.csv")       # OpenCLIP용 라벨 100개
places_df = pd.read_csv("places365_output.csv")    # Places365 결과 (파일명 포함)
labels = label_df.iloc[:, 0].tolist()              # 첫 번째 컬럼을 라벨 리스트로 사용

# 3. 텍스트 임베딩 미리 계산
with torch.no_grad():
    text_tokens = tokenizer(labels).to(device)
    text_features = model.encode_text(text_tokens)
    text_features /= text_features.norm(dim=-1, keepdim=True)

# 4. 이미지 라벨링 함수 정의
def label_with_openclip(image_path, top_k=3):
    try:
        image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
    except Exception as e:
        print(f"이미지 불러오기 실패: {image_path} ({e})")
        return None

    with torch.no_grad():
        image_features = model.encode_image(image)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)

    top_probs, top_labels = similarity[0].topk(top_k)
    results = [(labels[i], round(top_probs[j].item() * 100, 2))
               for j, i in enumerate(top_labels)]
    return results

# 5. 폴더 내 이미지 자동 라벨링
def run_openclip_labeling(image_folder, output_csv="openclip_output.csv", top_k=3):
    results = []

    for _, row in tqdm(places_df.iterrows(), total=len(places_df)):
        filename = row['파일명'] if '파일명' in row else row['image']
        image_path = os.path.join(image_folder, filename)
        if not os.path.exists(image_path):
            print(f"이미지 없음: {filename}")
            continue

        labels_found = label_with_openclip(image_path, top_k)
        if labels_found:
            record = {"파일명": filename}
            for i, (label, prob) in enumerate(labels_found, start=1):
                record[f"라벨{i}"] = label
                record[f"확률{i}(%)"] = prob
            results.append(record)

    pd.DataFrame(results).to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\nOpenCLIP 라벨링 완료: {output_csv}")

# 6. 실행 예시
if __name__ == "__main__":
    image_folder = "./"  # 이미지와 CSV가 있는 폴더
    run_openclip_labeling(image_folder)