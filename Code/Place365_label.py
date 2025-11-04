import torch
from torchvision import models, transforms
from PIL import Image
import requests
from io import BytesIO 
import os
import pandas as pd

# 1. Places365 모델 불러오기
model = models.resnet50(num_classes=365)
checkpoint = torch.utils.model_zoo.load_url(
    'http://places2.csail.mit.edu/models_places365/resnet50_places365.pth.tar',
    map_location=torch.device('cpu')  # ← 추가
)
state_dict = {str.replace(k, 'module.', ''): v for k, v in checkpoint['state_dict'].items()}
model.load_state_dict(state_dict)
model.eval()


# 2. 클래스 인덱스 불러오기
classes_file = 'https://raw.githubusercontent.com/csailvision/places365/master/categories_places365.txt'
classes = [line.strip().split(' ')[0][3:] for line in requests.get(classes_file).text.split('\n') if line]

# 3. 이미지 전처리 정의 (500x500 강제 리사이즈)
preprocess = transforms.Compose([
    transforms.Resize((500, 500)),  # 모든 이미지를 500x500으로 맞춤
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225])
])

# 4. 이미지 라벨링 함수 정의
def label_image(image_path):
    try:
        image = Image.open(image_path).convert("RGB")
        w, h = image.size
        if w < 1000 or h < 1000:
            print(f"작은 이미지 강제 확대: {os.path.basename(image_path)} ({w}x{h} → 500x500)")
    except Exception as e:
        print(f"이미지 로드 실패: {image_path} ({e})")
        return None

    input_tensor = preprocess(image).unsqueeze(0)
    with torch.no_grad():
        output = model(input_tensor)
        probs = torch.nn.functional.softmax(output[0], dim=0)
    top5_prob, top5_catid = torch.topk(probs, 5)

    labels = [(classes[top5_catid[i]], round(top5_prob[i].item() * 100, 2)) for i in range(5)]
    return labels


# 5. 폴더 내 모든 이미지 자동 라벨링
def label_folder_images(folder_path):
    results = []
    image_files = [f for f in os.listdir(folder_path)
                   if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    for idx, filename in enumerate(sorted(image_files), start=1):
        image_path = os.path.join(folder_path, filename)
        labels = label_image(image_path)
        if labels:
            # top3만 선택
            top3 = labels[:3]

            row = {
                "사진번호": idx,
                "파일명": filename
            }

            # 상위 3개 라벨과 확률 저장
            for i, (label, prob) in enumerate(top3, start=1):
                row[f"라벨{i}"] = label
                row[f"확률{i}(%)"] = prob

            # 최상위 라벨 1개 추가
            best_label, best_prob = top3[0]
            row["최상위라벨"] = best_label
            row["최상위확률(%)"] = best_prob

            results.append(row)
            print(f"{idx}: {filename} → {best_label} ({best_prob}%)")

    # 지정된 경로에 CSV 저장
    output_path = "C:/Users/jin01/Videos/Captures/DGU/2025-2/DSCD/Project/2025-2-DSCD-San3Su1-03/Code/places365_output.csv"
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\nCSV 파일 저장 완료: {output_path}")

# 6. 실행 예시
if __name__ == "__main__":
    folder_path = "C:/Users/jin01/Videos/Captures/DGU/2025-2/DSCD/Project/2025-2-DSCD-San3Su1-03/Code/ai_test_images"
    label_folder_images(folder_path)


