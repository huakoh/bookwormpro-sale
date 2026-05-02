# 计算机视觉指南

## 数据增强

```python
import torchvision.transforms as T
from torchvision.transforms import v2
import albumentations as A

# torchvision 增强
train_transform = T.Compose([
    T.Resize((256, 256)),
    T.RandomCrop(224),
    T.RandomHorizontalFlip(p=0.5),
    T.RandomRotation(15),
    T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

val_transform = T.Compose([
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# Albumentations（更强大）
train_transform = A.Compose([
    A.RandomResizedCrop(224, 224),
    A.HorizontalFlip(p=0.5),
    A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.2, rotate_limit=15),
    A.OneOf([
        A.GaussNoise(),
        A.GaussianBlur(),
        A.MotionBlur(),
    ], p=0.3),
    A.Normalize(),
    A.pytorch.ToTensorV2()
])
```

## 图像分类

### 预训练模型

```python
import torchvision.models as models
from torchvision.models import ResNet50_Weights

# 加载预训练模型
model = models.resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)

# 修改分类头
num_classes = 10
model.fc = nn.Linear(model.fc.in_features, num_classes)

# 冻结特征提取层
for param in model.parameters():
    param.requires_grad = False
for param in model.fc.parameters():
    param.requires_grad = True

# EfficientNet
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights
model = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)

# Vision Transformer
from torchvision.models import vit_b_16, ViT_B_16_Weights
model = vit_b_16(weights=ViT_B_16_Weights.IMAGENET1K_V1)
model.heads.head = nn.Linear(model.heads.head.in_features, num_classes)
```

### timm 库

```python
import timm

# 列出可用模型
timm.list_models('resnet*')

# 加载模型
model = timm.create_model('resnet50', pretrained=True, num_classes=10)

# 获取模型配置
model.default_cfg
```

## 目标检测

### YOLOv8

```python
from ultralytics import YOLO

# 加载预训练模型
model = YOLO('yolov8n.pt')  # n, s, m, l, x

# 推理
results = model('image.jpg')
for result in results:
    boxes = result.boxes
    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0]
        conf = box.conf[0]
        cls = box.cls[0]
        print(f"类别: {cls}, 置信度: {conf:.2f}, 边界框: ({x1:.0f}, {y1:.0f}, {x2:.0f}, {y2:.0f})")

# 训练自定义数据
model.train(
    data='dataset.yaml',
    epochs=100,
    imgsz=640,
    batch=16,
    device=0
)

# 导出
model.export(format='onnx')
```

### dataset.yaml 格式

```yaml
path: /path/to/dataset
train: images/train
val: images/val

names:
  0: cat
  1: dog
  2: bird
```

## 图像分割

### 语义分割

```python
from torchvision.models.segmentation import deeplabv3_resnet50

model = deeplabv3_resnet50(pretrained=True)
model.classifier[4] = nn.Conv2d(256, num_classes, kernel_size=1)

# 推理
model.eval()
with torch.no_grad():
    output = model(image)['out']
    pred = output.argmax(1)
```

### U-Net

```python
class UNet(nn.Module):
    def __init__(self, in_channels=3, num_classes=1):
        super().__init__()
        
        # Encoder
        self.enc1 = self._block(in_channels, 64)
        self.enc2 = self._block(64, 128)
        self.enc3 = self._block(128, 256)
        self.enc4 = self._block(256, 512)
        
        self.pool = nn.MaxPool2d(2)
        
        # Bottleneck
        self.bottleneck = self._block(512, 1024)
        
        # Decoder
        self.upconv4 = nn.ConvTranspose2d(1024, 512, 2, stride=2)
        self.dec4 = self._block(1024, 512)
        self.upconv3 = nn.ConvTranspose2d(512, 256, 2, stride=2)
        self.dec3 = self._block(512, 256)
        self.upconv2 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.dec2 = self._block(256, 128)
        self.upconv1 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.dec1 = self._block(128, 64)
        
        self.conv = nn.Conv2d(64, num_classes, 1)
    
    def _block(self, in_ch, out_ch):
        return nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True)
        )
    
    def forward(self, x):
        # Encoder
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        
        # Bottleneck
        b = self.bottleneck(self.pool(e4))
        
        # Decoder
        d4 = self.dec4(torch.cat([self.upconv4(b), e4], dim=1))
        d3 = self.dec3(torch.cat([self.upconv3(d4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.upconv2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.upconv1(d2), e1], dim=1))
        
        return self.conv(d1)
```

## OCR

```python
from paddleocr import PaddleOCR

# 初始化
ocr = PaddleOCR(use_angle_cls=True, lang='ch')

# 识别
result = ocr.ocr('image.jpg', cls=True)

for line in result[0]:
    bbox = line[0]
    text = line[1][0]
    confidence = line[1][1]
    print(f"文本: {text}, 置信度: {confidence:.2f}")
```

## 评估指标

```python
# 分类
from sklearn.metrics import accuracy_score, classification_report

# 检测 mAP
# 使用 COCO API
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

coco_gt = COCO('annotations.json')
coco_dt = coco_gt.loadRes('predictions.json')
coco_eval = COCOeval(coco_gt, coco_dt, 'bbox')
coco_eval.evaluate()
coco_eval.accumulate()
coco_eval.summarize()

# 分割 IoU
def iou_score(pred, target, num_classes):
    ious = []
    for cls in range(num_classes):
        pred_mask = (pred == cls)
        target_mask = (target == cls)
        intersection = (pred_mask & target_mask).sum()
        union = (pred_mask | target_mask).sum()
        if union == 0:
            ious.append(1.0)
        else:
            ious.append(intersection / union)
    return np.mean(ious)
```

## 可视化

```python
import cv2
import matplotlib.pyplot as plt

# 绘制边界框
def draw_boxes(image, boxes, labels, scores, class_names):
    for box, label, score in zip(boxes, labels, scores):
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        text = f'{class_names[label]}: {score:.2f}'
        cv2.putText(image, text, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return image

# 可视化分割结果
def visualize_segmentation(image, mask, num_classes):
    colors = plt.cm.tab20(np.linspace(0, 1, num_classes))[:, :3] * 255
    colored_mask = colors[mask]
    overlay = cv2.addWeighted(image, 0.7, colored_mask.astype(np.uint8), 0.3, 0)
    return overlay
```
