from PIL import ImageDraw,Image,ImageOps
import numpy as np
import onnxruntime

anchors = [[(116,90),(156,198),(373,326)],[(30,61),(62,45),(59,119)],[(10,13),(16,30),(33,23)]]
anchors_yolo_tiny = [[(81, 82), (135, 169), (344, 319)], [(10, 14), (23, 27), (37, 58)]]
CLASSES=["target"]



class CaptchaResolver:
    def __init__(self, model_path="captcha.onnx"):
        self.session = onnxruntime.InferenceSession(model_path) 

    def _sigmoid(self, x):
        return 1 / (1 + np.exp(-1 * x))

    def _xywh2xyxy(self, x):
        y = np.copy(x)
        y[:, 0] = x[:, 0] - x[:, 2] / 2
        y[:, 1] = x[:, 1] - x[:, 3] / 2
        y[:, 2] = x[:, 0] + x[:, 2] / 2
        y[:, 3] = x[:, 1] + x[:, 3] / 2
        return y

    def _nms(self, dets, thresh):
        x1 = dets[:, 0]
        y1 = dets[:, 1]
        x2 = dets[:, 2]
        y2 = dets[:, 3]
        areas = (y2 - y1 + 1) * (x2 - x1 + 1)
        scores = dets[:, 4]
        keep = []
        index = scores.argsort()[::-1]

        while index.size > 0:
            i = index[0]
            keep.append(i)
            x11 = np.maximum(x1[i], x1[index[1:]])
            y11 = np.maximum(y1[i], y1[index[1:]])
            x22 = np.minimum(x2[i], x2[index[1:]])
            y22 = np.minimum(y2[i], y2[index[1:]])

            w = np.maximum(0, x22 - x11 + 1)
            h = np.maximum(0, y22 - y11 + 1)

            overlaps = w * h
            ious = overlaps / (areas[i] + areas[index[1:]] - overlaps)
            idx = np.where(ious <= thresh)[0]
            index = index[idx + 1]
        return keep

    def process_boxes(self, prediction, conf_thres=0.7, nms_thres=0.6):
        feature_map = np.squeeze(prediction)
        conf = feature_map[..., 4] > conf_thres
        box = feature_map[conf == True]

        cls_conf = box[..., 5:]
        cls = []
        for i in range(len(cls_conf)):
            cls.append(int(np.argmax(cls_conf[i])))
        all_cls = list(set(cls))

        output = []
        for i in range(len(all_cls)):
            curr_cls = all_cls[i]
            curr_cls_box = []
            
            for j in range(len(cls)):
                if cls[j] == curr_cls:
                    box[j][5] = curr_cls
                    curr_cls_box.append(box[j][:6])

            curr_cls_box = np.array(curr_cls_box)
            curr_cls_box = self._xywh2xyxy(curr_cls_box)
            curr_out_box = self._nms(curr_cls_box, nms_thres)

            for k in curr_out_box:
                output.append(curr_cls_box[k])
        output = np.array(output)
        return output

    def predict(self, image):
        org_img = image.resize((416, 416))
        img = org_img.convert("RGB")
        img = np.array(img).transpose(2, 0, 1)
        img = img.astype(dtype=np.float32)
        img /= 255.0
        img = np.expand_dims(img, axis=0)

        inputs = {self.session.get_inputs()[0].name: img}
        prediction = self.session.run(None, inputs)[0]
        return prediction

    def solve_gap(self, image):
        prediction = self.predict(image)
        boxes = self.process_boxes(prediction=prediction)
        if len(boxes) == 0:
            return 0
        else:
            # Calculate scaling ratio
            original_width = image.size[0]
            model_width = 416
            scale_ratio = original_width / model_width
            
            x_coordinate = boxes[..., :4][0][0] # Keep as float
            scaled_x = x_coordinate * scale_ratio
            
            return scaled_x
