import json
import os
import time
from enum import Enum

import torch
from PIL import Image
from torchvision import transforms

from backbone import resnet50_fpn_backbone, LastLevelP6P7
from draw_box_utils import draw_objs
from network_files import RetinaNet


def create_model(num_classes):
    # resNet50+fpn+retinanet
    # 注意，这里的norm_layer要和训练脚本中保持一致
    backbone = resnet50_fpn_backbone(norm_layer=torch.nn.BatchNorm2d,
                                     returned_layers=[2, 3, 4],
                                     extra_blocks=LastLevelP6P7(256, 256))
    model = RetinaNet(backbone, num_classes)

    return model


def time_synchronized():
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    return time.time()


def main(picture_path, result_picture_path, weights_path, label_json_path):
    # get devices
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    # print("using {} device.".format(device))

    # create model
    # 注意：不包含背景
    model = create_model(num_classes=20)

    # load train weights
    assert os.path.exists(weights_path), "{} file dose not exist.".format(weights_path)
    model.load_state_dict(torch.load(weights_path, map_location='cpu')["model"])
    model.to(device)

    # read class_indict
    assert os.path.exists(label_json_path), "json file {} dose not exist.".format(label_json_path)
    with open(label_json_path, 'r') as f:
        class_dict = json.load(f)

    category_index = {str(v): str(k) for k, v in class_dict.items()}

    # load image
    original_img = Image.open(picture_path).convert('RGB')

    # from pil image to tensor, do not normalize image
    data_transform = transforms.Compose([transforms.ToTensor()])
    img = data_transform(original_img)
    # expand batch dimension
    img = torch.unsqueeze(img, dim=0)

    model.eval()  # 进入验证模式
    with torch.no_grad():
        # init
        img_height, img_width = img.shape[-2:]
        init_img = torch.zeros((1, 3, img_height, img_width), device=device)
        model(init_img)

        t_start = time_synchronized()
        predictions = model(img.to(device))[0]
        t_end = time_synchronized()
        # print("inference+NMS time: {}".format(t_end - t_start))

        predict_boxes = predictions["boxes"].to("cpu").numpy()
        predict_classes = predictions["labels"].to("cpu").numpy()
        predict_scores = predictions["scores"].to("cpu").numpy()

        if len(predict_boxes) == 0:
            # print("没有检测到任何目标!")
            return run_status.no_detected

        plot_img = draw_objs(original_img,
                             predict_boxes,
                             predict_classes,
                             predict_scores,
                             category_index=category_index,
                             box_thresh=0.5,
                             line_thickness=3,
                             font='arial.ttf',
                             font_size=20)
        # plt.imshow(plot_img)
        # plt.show()
        # 保存预测的图片结果
        plot_img.save(result_picture_path)
        return run_status.detected


import sys


class run_status(Enum):
    detected = 1
    no_detected = 0
    failure = -1


# "C:\Users\大橘\Desktop\2.png"


if __name__ == '__main__':
    weights_path = r"T:/retinanet_voc_weights.pth"
    save_path = r'T:\saveImages\results'
    label_json_path = r'D:\MyPaper\deep-learning-for-image-processing\pytorch_object_detection\retinaNet' \
                      r'\pascal_voc_classes.json '

   # try:
    picture_path = sys.argv[1]
    file_name = os.path.basename(picture_path)
    result_picture_path = os.path.join(save_path, file_name)
    result = main(picture_path, result_picture_path, weights_path, label_json_path)
    print(result.value)
    # except:
    #     print(run_status.failure.value)
