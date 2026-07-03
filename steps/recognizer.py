"""识别器 - HTTP POST 调用 OCR 服务并解析结果"""

import time
import requests
from PIL import Image
import io
import config
from core.models import Photo, PhotoLabel


class Recognizer:
    """识别器 - HTTP POST 调用 + 解析 → 照片对象"""

    def __init__(self):
        self.url = config.OCR_URL
        self.timeout = config.OCR_TIMEOUT
        self.max_retries = config.OCR_MAX_RETRIES
        self.retry_delay = config.OCR_RETRY_DELAY
        self.app_id = config.OCR_APP_ID
        self.app_key = config.OCR_APP_KEY
        self.app_secret = config.OCR_APP_SECRET
        self.org_id = config.OCR_ORG_ID
        self.sys_code = config.OCR_SYS_CODE
        self.model_id = config.OCR_MODEL_ID
        self.doc_type = config.OCR_DOC_TYPE
        self.ocr_config = config.OCR_CONFIG
        self.if_need_ocr = config.OCR_IF_NEED_OCR

    def 识别(self, path: str) -> Photo:
        """识别单张照片（调用+解析同一文件）"""
        raw = self._post(path)
        parsed = self._解析(raw)
        return Photo(path=path, **parsed)

    def _post(self, path: str) -> dict:
        """HTTP POST 调用 OCR 服务"""
        if path.lower().endswith('.pdf'):
            with open(path, 'rb') as f:
                file_bytes = f.read()
            media_type = 'application/pdf'
        else:
            with Image.open(path) as img:
                output = io.BytesIO()
                img.convert('RGB').save(output, format='JPEG', quality=95)
                file_bytes = output.getvalue()
            media_type = 'image/jpeg'

        filename = path.split('\\')[-1].split('/')[-1]
        files = {"files": (filename, file_bytes, media_type)}

        data = {
            "docType": self.doc_type,
            "modelId": self.model_id,
            "appId": self.app_id,
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "orgId": self.org_id,
            "sysCode": self.sys_code,
            "config": self.ocr_config,
            "ifNeedOcr": self.if_need_ocr,
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.url, files=files, data=data, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise Exception(f"OCR 请求失败（路径: {path}）: {e}")
                time.sleep(self.retry_delay)

    def _解析(self, raw: dict) -> dict:
        """解析 OCR 返回数据，提取目标字段"""
        try:
            if raw.get("error", False) or not raw.get("success", False):
                raise Exception(f"OCR 服务返回错误: {raw.get('resultMessage', '未知错误')}")

            result = raw["values"]["data"][0]["data"]["commitResult"]

            交货单号 = result.get("交货单号", "")
            交货单号 = 交货单号 if 交货单号 else None

            销售订单号 = result.get("销售订单号", "")
            销售订单号 = 销售订单号 if 销售订单号 else None

            车牌号 = result.get("车牌号", "")
            车牌号 = self._清洗车牌(车牌号) if 车牌号 else None

            打标识 = result.get("打标识", "")
            label = None
            for photo_label in PhotoLabel:
                if photo_label.value in 打标识:
                    label = photo_label
                    break

            return {
                "label": label,
                "plate": 车牌号,
                "交货单号": 交货单号,
                "销售订单号": 销售订单号,
            }
        except (KeyError, IndexError, TypeError) as e:
            raise Exception(f"解析 OCR 结果失败: {e}")

    @staticmethod
    def _清洗车牌(plate: str) -> str:
        """清洗车牌：去空格、去点号等分隔符，统一大写"""
        if not plate:
            return None
        cleaned = plate.upper()
        cleaned = cleaned.replace(" ", "").replace(".", "").replace("-", "")
        return cleaned if cleaned else None
