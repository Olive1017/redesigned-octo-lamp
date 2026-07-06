"""配置文件 - 所有可变参数集中管理"""

# OCR 服务配置
OCR_URL = "http://172.30.197.3:10000/OcrPlugins/core/ocr"
OCR_TIMEOUT = 30
OCR_MAX_RETRIES = 3
OCR_RETRY_DELAY = 1

# 鉴权信息
OCR_APP_ID = "RZc6PeUt"
OCR_APP_KEY = "0ofRqy6c"
OCR_APP_SECRET = "e9a099bbae340783ffe717969987588e"
OCR_ORG_ID = "your_org_id"
OCR_SYS_CODE = "your_sys_code"
OCR_MODEL_ID = "lscc_petrochina_guangzhou_receipt_99999_1503"
OCR_DOC_TYPE = "SINGLE_LLM_EXTRACT"
OCR_CONFIG = "{}"
OCR_IF_NEED_OCR = "true"

# 分批识别配置
# 公司大模型一次只能识别几张，太多会识别失败，所以每个子文件夹内分批识别
BATCH_SIZE = 5              # 每批识别的图片数
MAX_ROUNDS_PER_IMAGE = 3   # 识别失败的图片最多重试的轮次，超过则该文件夹标黄人工

# 拼图参数
COLLAGE_BACKGROUND_COLOR = (255, 255, 255)  # 白色背景
COLLAGE_QUALITY = 95

# 输入路径
DEFAULT_INPUT_DIR = ""

# 并发配置
MAX_WORKERS = 20
