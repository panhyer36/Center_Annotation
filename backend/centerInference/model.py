"""Center Detection Model - Encapsulated Version"""
import torch
import torch.nn as nn
from torchvision.models import resnet34, ResNet34_Weights
from typing import List


class ResNetBackbone(nn.Module):
    """ResNet34 Backbone (single-channel input)"""

    def __init__(self, pretrained: bool = False):
        super().__init__()

        if pretrained:
            base_model = resnet34(weights=ResNet34_Weights.IMAGENET1K_V1)
        else:
            base_model = resnet34(weights=None)

        # Modify the first layer: change from 3 channels to 1 channel
        old_conv1 = base_model.conv1
        self.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)

        if pretrained:
            with torch.no_grad():
                self.conv1.weight = nn.Parameter(
                    old_conv1.weight.mean(dim=1, keepdim=True)
                )

        self.bn1 = base_model.bn1
        self.relu = base_model.relu
        self.maxpool = base_model.maxpool
        self.layer1 = base_model.layer1
        self.layer2 = base_model.layer2
        self.layer3 = base_model.layer3
        self.layer4 = base_model.layer4
        self.out_channels = [64, 128, 256, 512]

    def forward(self, x: torch.Tensor) -> List[torch.Tensor]:
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        c1 = self.layer1(x)
        c2 = self.layer2(c1)
        c3 = self.layer3(c2)
        c4 = self.layer4(c3)

        return [c1, c2, c3, c4]


class UpsampleBlock(nn.Module):
    """Upsampling Block"""

    def __init__(self, in_channels: int, out_channels: int, scale_factor: int = 2):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=scale_factor, mode="bilinear", align_corners=True)
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.upsample(x))


class HeatmapHead(nn.Module):
    """Heatmap Prediction Head"""

    def __init__(self, in_channels: int, num_landmarks: int = 5, hidden_channels: int = 256, output_stride: int = 2):
        super().__init__()
        self.up1 = UpsampleBlock(in_channels, hidden_channels)
        self.up2 = UpsampleBlock(hidden_channels, hidden_channels // 2)
        self.up3 = UpsampleBlock(hidden_channels // 2, hidden_channels // 4)
        self.up4 = UpsampleBlock(hidden_channels // 4, hidden_channels // 4) if output_stride == 2 else None
        self.final_conv = nn.Conv2d(hidden_channels // 4, num_landmarks, kernel_size=1)

    def forward(self, features: List[torch.Tensor]) -> torch.Tensor:
        x = features[-1]
        x = self.up1(x)
        x = self.up2(x)
        x = self.up3(x)
        if self.up4 is not None:
            x = self.up4(x)
        return torch.sigmoid(self.final_conv(x))


class CenterDetectionNet(nn.Module):
    """Center Point Detection Network"""

    def __init__(self, num_landmarks: int = 5, output_stride: int = 2):
        super().__init__()
        self.num_landmarks = num_landmarks
        self.backbone = ResNetBackbone(pretrained=False)
        self.head = HeatmapHead(
            in_channels=self.backbone.out_channels[-1],
            num_landmarks=num_landmarks,
            output_stride=output_stride,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone(x)
        return self.head(features)

    def get_landmarks(self, heatmaps: torch.Tensor, method: str = "weighted", threshold: float = 0.5) -> torch.Tensor:
        """Decode heatmaps to obtain landmark coordinates"""
        B, N, H, W = heatmaps.shape
        device = heatmaps.device
        coords = torch.zeros((B, N, 2), device=device)

        for b in range(B):
            for n in range(N):
                hm = heatmaps[b, n]
                if method == "argmax":
                    flat_idx = hm.argmax()
                    coords[b, n, 0] = (flat_idx % W).float()
                    coords[b, n, 1] = (flat_idx // W).float()
                else:  # weighted
                    max_val = hm.max()
                    if max_val > 0:
                        mask = hm > threshold * max_val
                        if mask.sum() > 0:
                            yy, xx = torch.meshgrid(
                                torch.arange(H, device=device, dtype=torch.float32),
                                torch.arange(W, device=device, dtype=torch.float32),
                                indexing="ij",
                            )
                            weights = hm[mask]
                            coords[b, n, 0] = (xx[mask] * weights).sum() / weights.sum()
                            coords[b, n, 1] = (yy[mask] * weights).sum() / weights.sum()
                        else:
                            flat_idx = hm.argmax()
                            coords[b, n, 0] = (flat_idx % W).float()
                            coords[b, n, 1] = (flat_idx // W).float()
        return coords


def load_model(checkpoint_path: str, device: str = "cpu") -> CenterDetectionNet:
    """Load model"""
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    config = checkpoint.get("config", {})
    input_size = config.get("input_size", (320, 320))
    heatmap_size = config.get("heatmap_size", (160, 160))
    output_stride = input_size[0] // heatmap_size[0]

    model = CenterDetectionNet(
        num_landmarks=config.get("num_landmarks", 5),
        output_stride=output_stride,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, config
