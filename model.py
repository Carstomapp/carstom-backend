import cv2
import torch
import torchvision
import numpy as np
from PIL import Image
import segmentation_models_pytorch as smp

torch.set_num_threads(1)

class Rim_Detector:
    def __init__(self):
        self.model = smp.FPN('mobilenet_v2', in_channels=1)
        self.model.load_state_dict(torch.load("unet_mobile_net_v2.pt"))
        self.model.eval()

        self.image_transfom = torchvision.transforms.Compose(
            [
                torchvision.transforms.ToTensor(),
                torchvision.transforms.Resize(384),
                torchvision.transforms.CenterCrop(384),
                torchvision.transforms.Normalize(
                    mean=0.45,#(0.485, 0.456, 0.406),
                    std=0.225, #(0.229, 0.224, 0.225)
                ),
            ]
        )

    def __call__(self, image):
        with torch.no_grad():
            _input = self.image_transfom(image)[None]
            out = self.model(_input)[0][0].numpy()

        out = out - out.min()
        out /= out.max()
        mask = np.uint8((out > 0.3) * 255)
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contour = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)[0]

        if cv2.contourArea(contour) < 2000:
            return None

        ellipse = cv2.fitEllipse(contour)
        ellipse = [[ellipse[0][0], ellipse[0][1]], [ellipse[1][0], ellipse[1][1]], ellipse[2]]

        width, height = image.size
        min_size, max_size = (("width", width), ("height", height)) if width < height else (("height", height), ("width", width))
        ratio = min_size[1] / 384
        diff = (max_size[1] - min_size[1]) / 2
        if min_size[0] == "width":
            ellipse[0][1] += diff / ratio
        else:
            ellipse[0][0] += diff / ratio
        ellipse[0][1] *= ratio
        ellipse[0][0] *= ratio
        ellipse[1][1] *= ratio
        ellipse[1][0] *= ratio

        alpha = np.arccos(ellipse[1][0]/ellipse[1][1])
        beta = (ellipse[2] / 180) * np.pi

        pose = {
            "x": int(ellipse[0][0]),
            "y": int(ellipse[0][1]),
            "x_normal": np.cos(alpha) * np.cos(beta),
            "z_normal": np.sin(alpha) * np.cos(beta),
            "y_normal": np.sin(beta),
        }

        return pose
