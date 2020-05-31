import torch
from pathlib import Path

from mapworld.ttypes import *

from parse_config import ConfigParser

import model as module_arch
import utils.crf as postps_crf

try:
    from mwfrontend import MapWorldMain
    from mwfrontend.ttypes import *

    enable_client = True
except ModuleNotFoundError:
    print("Frontend protocol not found, client functions disabled.")
    enable_client = False


class ServerMain:

    def __init__(self, client, tmp_path, n_gpu_use=0):
        if enable_client:
            self.client = client
        else:
            self.client = None
        self.n_gpu_use = n_gpu_use

        self.logger = None
        self.device = None
        self.model = None
        self.postprocessor = None
        self.crop_size = 325
        self.prescale = 1.0
        self.batch_size = 4

        self.tmp_path = tmp_path
        self.pred_th = None
        self.cfg = None

    def set_prescale(self, prescale):
        self.prescale = prescale

    def set_batch_size(self, batch_size):
        self.batch_size = batch_size

    def send_progress(self, total, count, img_path):
        if self.client:
            res = ProgsReq(total, count, img_path)
            self.client.NotifyProgress(res)

    def send_result(self, label_path, json_path):
        if self.client:
            res = ResultReq(label_path, json_path)
            self.client.NotifyResult(res)

    def pred(self, paths, metas, m_cfg):
        self.cfg = m_cfg
        res = Response()
        if len(paths) != len(metas):
            res.code = -2
            res.msg = "The length of images and meta is not same."
            return res
        if self.pred_th is not None:
            if self.pred_th.is_alive():
                res.code = -3
                res.msg = "There is a task running, please wait it finish."
            return res
        try:
            self.device = torch.device('cuda:0' if self.n_gpu_use > 0 else 'cpu')
            torch.set_grad_enabled(False)
            m_cfg["save_dir"] = str(self.tmp_path)
            config = ConfigParser(m_cfg, Path(m_cfg["path"]))
            self.logger = config.get_logger('PredServer')
            self.model = config.init_obj('arch', module_arch)
            self.logger.info('Loading checkpoint: {} ...'.format(config.resume))
            if self.n_gpu_use > 0:
                checkpoint = torch.load(config.resume)
            else:
                checkpoint = torch.load(config.resume, map_location=torch.device('cpu'))

            state_dict = checkpoint['state_dict']
            if self.n_gpu_use > 1:
                self.model = torch.nn.DataParallel(self.model)
            self.model.load_state_dict(state_dict)
            self.model = self.model.to(self.device)
            self.model.eval()

            if "crop_size" in config["tester"]:
                self.crop_size = config["tester"]["crop_size"]

            if 'postprocessor' in config["tester"]:
                module_name = config["tester"]['postprocessor']['type']
                module_args = dict(config["tester"]['postprocessor']['args'])
                self.postprocessor = getattr(postps_crf, module_name)(**module_args)

            self.tmp_path.mkdir(parents=True, exist_ok=True)

            m_typename = m_cfg["name"].split("-")[1]
            if m_typename == "Deeplab" or m_typename == "UNet":
                from .predthread import SegPredThread
                self.pred_th = SegPredThread(self, paths, metas, self.tmp_path)
            elif m_typename == "CycleGAN":
                # TODO: support CycleGAN
                raise NotImplementedError("CycleGAN is not supported now.")
            else:
                raise NotImplementedError("Model type:", m_typename, "is not supported.")
            self.pred_th.start()
            self.pred_th.is_alive()
        except RuntimeError as e:
            res.code = -1
            res.msg = str(e)
            return res

        res.code = 0
        res.msg = "Success"
        return res
