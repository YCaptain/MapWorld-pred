import cv2
import numpy as np
import json

from PIL import Image


class SegmentOutputUtil:
    def __init__(self, pred, meta):
        self.pred = pred
        self.meta = meta

    @staticmethod
    def load_img(path):
        img = Image.open(path)
        # img = Image.eval(img, lambda a: 1 if a >= 128 else 0)
        return np.asarray(img, dtype=np.uint8)

    @staticmethod
    def get_contours(pred):
        kernel = np.ones((5, 5), dtype=np.uint8)
        opening = cv2.morphologyEx(pred, cv2.MORPH_OPEN, kernel)
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)
        contours, hierarchy = cv2.findContours(closing, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        cnt, hie = zip(*filter(lambda c: c[1][3] == -1, zip(contours, *hierarchy)))  # remove inner box
        return cnt, hie

    @staticmethod
    def get_bboxs(cnts):
        bboxs = list()
        for cnt in cnts:
            min_rect = cv2.minAreaRect(cnt)
            min_rect = np.int0(cv2.boxPoints(min_rect))
            bboxs.append(min_rect)
        return bboxs

    @staticmethod
    def show_bbox(pred_mask, rects):
        img = np.zeros((325, 325, 3), np.uint8)
        for rect in rects:
            cv2.drawContours(img, [rect], 0, (0, 255, 0), 2)  # green
        cv2.imshow("img", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    '''
    3D map JSON format:
    {
        "meta": {
            "x": 0,
            "y": 0
        }
        "building": 
        [
          {
              "coordinates": [
                {
                  "x": 20.355053213979282,
                  "y": -22.450252781908343,
                  "z": 0
                },
                {
                  "x": 20.355053213979282,
                  "y": -17.450252781908343,
                  "z": 0
                },
                {
                  "x": 25.355053213979282,
                  "y": -17.450252781908343,
                  "z": 0
                },
                {
                  "x": 25.355053213979282,
                  "y": -22.450252781908343,
                  "z": 0
                }
              ],
              "properties": {
                "height": 27.832069410709124
              }
          },
          ...
        ],
        "road":
        [
          {
              "coordinates": [
                {
                  "x": 20.355053213979282,
                  "y": -22.450252781908343,
                  "z": 0
                },
                {
                  "x": 20.355053213979282,
                  "y": -17.450252781908343,
                  "z": 0
                },
                {
                  "x": 25.355053213979282,
                  "y": -17.450252781908343,
                  "z": 0
                },
                {
                  "x": 25.355053213979282,
                  "y": -22.450252781908343,
                  "z": 0
                },
              ]
          },
          ...
        ]
    }
    '''

    @staticmethod
    def def_fun_scale(sc, meta):
        # flip y axis
        y = meta["h"]
        sc[1] = y - sc[1]
        sc = sc * 0.1
        return sc

    @staticmethod
    def encoding(items, meta, fun_prop=None, fun_scale=def_fun_scale.__func__):
        res = list()
        for a_item in items:
            targ = dict()
            coords = list()
            for c in a_item:
                coord = dict()
                if fun_scale is not None:
                    c = fun_scale(c, meta)
                coord["x"] = int(c[0])
                coord["y"] = int(c[1])
                coord["z"] = 0
                coords.append(coord)
            targ["coordinates"] = coords
            if fun_prop is not None:
                targ["properties"] = fun_prop(targ, meta)
            res.append(targ)
        return res

    def get_result(self):
        cnts = self.get_contours(self.pred)
        bboxs = self.get_bboxs(cnts[0])
        building = self.encoding(bboxs, self.meta)
        res = dict()
        res["meta"] = self.meta
        res["building"] = building
        return json.dumps(res)
