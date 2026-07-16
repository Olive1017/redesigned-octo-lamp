"""
steps/uploader.py

物流管理系统(LMS) 公路费用录入 —— RPA 自动上传拼图（只上传、不提交）。

设计（精简版，与讨论一致）：
- 直接按文件夹名里的交货单号逐个查询 -> 录入 -> 上传两张拼图 -> 确认。
  不读表格、不分组、不提交（提交交给人工）。
- 幂等/可反复运行：行状态已是“已录入”则跳过，绝不重复上传。
- 两种命运：
    🟢 成功   -> 上传完成（状态变已录入）
    🔴 标黄   -> 拼图缺失 / 页面查无该交货单号 / 压不到3MB / 上传报错
- 验证码：人工登录一次，storage_state 缓存会话，之后复用。
- 3MB 限制：上传前等比压缩。
"""
from __future__ import annotations

import os
import re
import sys
import csv
import time
import tempfile
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image
from playwright.sync_api import (
    sync_playwright,
    Playwright,
    Page,
    BrowserContext,
    TimeoutError as PWTimeout,
)

from dotenv import load_dotenv
load_dotenv()                          # ← 必须在下面两行之前
LMS_ACCOUNT = os.environ.get("LMS_ACCOUNT", "")
LMS_PASSWORD = os.environ.get("LMS_PASSWORD", "")

# ==================== 配置区（建议以后移到 config.py） ====================
LOGIN_URL = "https://lms.chem.petrochina.com.cn/#/login"

# 账号密码：从环境变量读，千万别写死进代码提交！
#   Windows PowerShell:  $env:LMS_ACCOUNT="..."; $env:LMS_PASSWORD="..."
LMS_ACCOUNT = os.environ.get("LMS_ACCOUNT", "")
LMS_PASSWORD = os.environ.get("LMS_PASSWORD", "")

含税金额 = "2280"              # 固定值
MAX_FILE_BYTES = 3 * 1024 * 1024  # 3MB 上限
UPLOAD_TIMEOUT_MS = 30_000
STORAGE_STATE = "auth_state.json"

# 上传位→拼图映射：轨迹截图←三合一；客户签收回单←二合一
SLOT_轨迹 = "轨迹截图"
SLOT_回单 = "客户签收回单"

# 拼图文件名识别（文件夹内包含这些子串）
MARK_二合一 = "二合一"
MARK_三合一 = "三合一"

# 使用模块级 logger，应用入口负责配置 handler/level
log = logging.getLogger("uploader")


# ==================== 验证码识别 ====================
def 识别验证码(图片字节: bytes) -> str:
    """使用 ddddocr 识别验证码（懒加载单例）"""
    global _ocr
    try:
        _ocr
    except NameError:
        import ddddocr
        _ocr = ddddocr.DdddOcr(show_ad=False)
    return _ocr.classification(图片字节).strip()


def 刷新验证码(page: Page, 验证码图: str) -> bool:
    """点击验证码图片刷新，确认 src(uuid) 变化"""
    旧 = page.locator(验证码图).first.get_attribute("src")
    page.locator(验证码图).first.click()
    for _ in range(20):                       # 最多等 2 秒
        page.wait_for_timeout(100)
        if page.locator(验证码图).first.get_attribute("src") != 旧:
            return True
    return False


def 尝试验证码登录(page: Page, 次数: int = 5) -> bool:
    验证码图 = 'img[src^="/api/captcha"]'
    # 账号密码只填一次——不 reload，字段不会被清空
    page.get_by_placeholder("账号").fill(LMS_ACCOUNT)     # ← 换成你已生效的账号定位
    page.get_by_placeholder("密码").fill(LMS_PASSWORD)    # ← 换成你已生效的密码定位
    for n in range(次数):
        try:
            图 = page.locator(验证码图).first.screenshot()
            码 = 识别验证码(图)
            log.info(f"[验证码] 第{n+1}次 识别 = {码!r}")
            框 = page.get_by_placeholder("验证码")
            框.fill("")            # 清掉上一次的
            框.fill(码)
            page.get_by_role("button", name="登录").click()
            page.wait_for_timeout(1500)
            if "login" not in page.url.lower():
                log.info(f"[验证码] 第{n+1}次 登录成功")
                return True
            # 失败 → 点图换新验证码（不 reload，账号密码保留）
            log.warning(f"[验证码] 第{n+1}次 失败，点图刷新")
            if not 刷新验证码(page, 验证码图):
                log.warning("  ⚠️ 点图似乎没换新验证码，可能得找专门的刷新按钮")
        except Exception as e:
            log.warning(f"[验证码] 第{n+1}次 异常: {e}")
            page.wait_for_timeout(500)
    return False


# ==================== 数据结构 ====================
@dataclass
class Delivery:
    交货单号: str
    车牌: str
    文件夹路径: Path
    二合一: Optional[Path] = None
    三合一: Optional[Path] = None


@dataclass
class 结果:
    交货单号: str
    命运: str        # 成功 / 跳过 / 标黄人工
    原因: str = ""


# ==================== 扫本地文件夹 ====================
def _规整单号(s: str) -> str:
    """去掉首尾和中间所有空白（含全角空格\u3000、制表符、换行）——交货单号是纯数字"""
    return re.sub(r"\s+", "", s or "")


def 扫描文件夹(输入目录: Path):
    """每个子文件夹名 = {车牌}_{交货单号}，内含二合一/三合一拼图"""
    deliveries = []
    for d in 输入目录.iterdir():
        if not d.is_dir():
            continue
        if "_" not in d.name:
            log.warning("跳过不符命名的文件夹：%s", d.name)
            continue
        车牌, 交货单号 = d.name.rsplit("_", 1)
        交货单号 = _规整单号(交货单号)
        二 = next((p for p in d.iterdir() if MARK_二合一 in p.name), None)
        三 = next((p for p in d.iterdir() if MARK_三合一 in p.name), None)
        deliveries.append(Delivery(交货单号, 车牌, d, 二, 三))
    log.info("扫到 %d 个本地文件夹", len(deliveries))
    return deliveries


# ==================== 3MB 压缩 ====================
def 确保小于3MB(路径: Path) -> Path:
    if 路径.stat().st_size <= MAX_FILE_BYTES:
        return 路径
    img = Image.open(路径).convert("RGB")
    tmp = Path(tempfile.gettempdir()) / f"cmp_{路径.name}"
    for q in range(90, 39, -10):
        img.save(tmp, "JPEG", quality=q)
        if tmp.stat().st_size <= MAX_FILE_BYTES:
            log.info("压缩 %s -> quality=%d", 路径.name, q)
            return tmp
    w, h = img.size
    for scale in (0.8, 0.6, 0.5):
        img.resize((int(w * scale), int(h * scale))).save(tmp, "JPEG", quality=75)
        if tmp.stat().st_size <= MAX_FILE_BYTES:
            log.info("压缩 %s -> scale=%.1f", 路径.name, scale)
            return tmp
    raise RuntimeError(f"{路径.name} 无法压到 3MB 以内")


# ==================== 登录（会话复用） ====================
def 准备页面(pw: Playwright,等待人工=None):
    browser = pw.chromium.launch(channel="msedge", headless=False)
    if Path(STORAGE_STATE).exists():
        context = browser.new_context(storage_state=STORAGE_STATE)
    else:
        context = browser.new_context()
    page = context.new_page()
    page.goto(LOGIN_URL)
    page.wait_for_timeout(2000)
    if "login" in page.url.lower() or page.get_by_role("textbox", name="账号").count():
        登录(page, context, 等待人工)
    return browser, context, page


def 登录(page: Page, context, 等待人工=None):
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")
    if 尝试验证码登录(page):
        context.storage_state(path=STORAGE_STATE)   # 保持你原来的会话保存写法
        return
    # OCR 多次失败 → 转人工：先填好账号密码，人只需输验证码
    page.get_by_placeholder("账号").fill(LMS_ACCOUNT)     # 同上，用你能用的定位
    page.get_by_placeholder("密码").fill(LMS_PASSWORD)
    if 等待人工:
        等待人工()          # GUI：弹窗提示人工输验证码后点继续
    else:
        input("请在浏览器手动输入验证码并登录，然后回车继续...")
    context.storage_state(path=STORAGE_STATE)


# ==================== 导航（只需一次） ====================
def 进入费用录入(page: Page):
    page.get_by_text("新调运管理").click()
    page.get_by_text("公路进出厂协同").click()
    page.get_by_text("公路费用管理").click()
    page.get_by_text("公路费用录入").click()
    page.get_by_role("tab", name="销售交货单").click()
    page.wait_for_load_state("networkidle")


# ==================== 按交货单号查询 ====================)
def 查询交货单号(page: Page, 交货单号: str) -> bool:
    # 填单号 + 点查询
    交货单号 = _规整单号(交货单号)
    表单项 = page.locator(".el-form-item").filter(
        has=page.locator(".el-form-item__label", has_text=re.compile(r"^交货单号"))
    )
    box = 表单项.get_by_role("textbox")
    box.click(); box.fill(""); box.fill(交货单号)
    page.get_by_role("button", name=re.compile("查询")).click()

    # 关键：不靠“箭头出现了”判断（旧结果的箭头会骗过去），
    # 而是反复“展开 + 检查本单号是否真的出现在子表里”，直到看见它为止。
    # 这样即使新数据慢一拍，也会一直等到本单号就位，绝不读上一单。
    命中 = page.locator("td:visible").filter(
        has_text=re.compile(rf"^\s*{re.escape(交货单号)}\s*$")
    )
    截止 = time.time() + 15          # 最多等 15 秒
    while time.time() < 截止:
        # 本单号已经在子表里出现 = 新结果就位，收工
        if 命中.count() > 0:
            return True
        # 母行出现且未展开，就点开它
        箭头 = page.locator(".el-table__expand-icon:visible").first
        if 箭头.count() and "expanded" not in (箭头.get_attribute("class") or ""):
            try:
                箭头.scroll_into_view_if_needed()
                箭头.click()
            except Exception:
                pass
        page.wait_for_timeout(400)
    return False   # 15 秒都没等到本单号 = 查无此单
    

def 找行(page: Page, 交货单号: str):
    表头 = page.locator("th").filter(has_text=re.compile(r"^\s*交货单号\s*$")).first
    try:
        表头.wait_for(state="attached", timeout=3000)   # 没展开就 3 秒放弃，不再卡 30 秒
    except PWTimeout:
        return None
    m = re.search(r"(el-table_\d+_column_\d+)", 表头.get_attribute("class") or "")
    if not m:
        return None
    列类 = m.group(1)
    格 = page.locator(f"td.{列类}:visible").filter(
        has_text=re.compile(rf"^\s*{re.escape(交货单号)}\s*$")
    )
    try:
        格.first.wait_for(state="visible", timeout=8000)
    except PWTimeout:
        return None
    return 格.first.locator("xpath=ancestor::tr[1]")


def 行已录入(row) -> bool:
    # 列序（0基）：0序号 1交货单号 2erp 3车船号 4过账日期 5过账量 6总金额 7状态 8操作
    try:
        状态 = row.locator("td").nth(7).inner_text().strip()
        return ("已录入" in 状态) or ("已提交" in 状态)
    except Exception:
        return False


# ==================== 录入 + 上传一行 ====================
def _列类(page: Page, 列名前缀: str) -> Optional[str]:
    """按表头文字前缀，动态解析它的 el-table_N_column_M 列类（数字每次会变）"""
    th = page.locator("th").filter(
        has_text=re.compile(rf"^\s*{re.escape(列名前缀)}")
    ).first
    try:
        th.wait_for(state="attached", timeout=3000)
    except PWTimeout:
        return None
    m = re.search(r"(el-table_\d+_column_\d+)", th.get_attribute("class") or "")
    return m.group(1) if m else None

def 填含税金额如为空(page: Page, 费用名: str = "干线运费", 金额: str = 含税金额):
    列类 = _列类(page, "含税金额")   # ^含税金额 前缀，天然排除“不含税金额”
    if not 列类:
        log.warning("找不到“含税金额”列，跳过填金额")
        return
    行 = page.locator("tr").filter(
        has=page.locator("td .cell", has_text=re.compile(r"^\s*干线运费"))
    ).first
    inp = 行.locator(f"td.{列类} input.el-input__inner")
    try:
        if not (inp.input_value() or "").strip():   # 只有空才填，填过就跳过
            inp.fill(金额)
    except PWTimeout:
        log.warning("干线运费·含税金额 输入框没找到，跳过填金额")


def 录入一行(page: Page, row, d: Delivery):
    row.get_by_role("button", name="录入", exact=True).click()
    page.wait_for_timeout(800)

    填含税金额如为空(page, "干线运费", 含税金额)         # ← 精准填“干线运费·含税金额”

    上传位(page, SLOT_轨迹, 确保小于3MB(d.三合一))       # 轨迹截图 ← 三合一
    上传位(page, SLOT_回单, 确保小于3MB(d.二合一))       # 客户签收回单 ← 二合一

    page.get_by_role("button", name="确认", exact=True).click()   # 只确认，不提交
    page.wait_for_load_state("networkidle")


def 上传位(page: Page, 位名: str, 文件: Path):
    行 = page.locator("tr").filter(
        has=page.locator("td .cell", has_text=re.compile(rf"^\s*{re.escape(位名)}\s*$"))
    ).first
    行.locator("input.el-upload__input").set_input_files(str(文件))

    # 关键：等这一行“上传时间”列出现时间戳，才算传完，再返回
    上传时间格 = 行.locator("td").nth(2)   # 0序号 1文件名称 2上传时间 3操作
    for _ in range(150):                   # 最多等 15 秒
        page.wait_for_timeout(100)
        if (上传时间格.inner_text() or "").strip():
            return
    raise RuntimeError(f"{位名} 上传超时：“上传时间”一直是空的")

# ==================== 处理一个交货单号 ====================
def 处理一个(page: Page, d: Delivery, 结果表):
    if not d.二合一 or not d.三合一:
        标黄(结果表, d.交货单号, "二合一/三合一拼图缺失")
        return

    if not 查询交货单号(page, d.交货单号):     # ← 现在真的会用返回值
        标黄(结果表, d.交货单号, "页面查不到该交货单号")
        return

    row = 找行(page, d.交货单号)
    if row is None:
        标黄(结果表, d.交货单号, "展开后仍未定位到子行")
        return

    if 行已录入(row):
        log.info("✔ %s 已录入，跳过", d.交货单号)
        结果表.append(结果(d.交货单号, "跳过", "已录入"))
        return

    try:
        录入一行(page, row, d)
        log.info("⬆ %s 上传完成", d.交货单号)
        结果表.append(结果(d.交货单号, "成功"))
    except RuntimeError as e:        # 压缩失败、上传超时等硬故障
        标黄(结果表, d.交货单号, str(e))
    except PWTimeout as e:           # 页面元素超时
        标黄(结果表, d.交货单号, f"上传失败（超时）：{e}")
    except Exception as e:           # 其它未预期
        标黄(结果表, d.交货单号, f"上传失败：{e}")

def 标黄(结果表, 交货单号, 原因):
    log.warning("🔴 标黄人工 %s：%s", 交货单号, 原因)
    结果表.append(结果(交货单号, "标黄人工", 原因))


# ==================== 主流程 ====================
def main(输入目录: str, 等待人工=None):
    目录 = Path(输入目录)
    结果表: list[结果] = []
    deliveries = 扫描文件夹(目录)
    if not deliveries:
        log.info("没有可处理的文件夹")
        return

    with sync_playwright() as pw:
        browser, context, page = 准备页面(pw, 等待人工)
        try:
            进入费用录入(page)          # 导航一次，后续只换查询条件
            for d in deliveries:
                try:
                    处理一个(page, d, 结果表)
                except Exception as e:
                    标黄(结果表, d.交货单号, f"未预期异常：{e}")
        finally:
            context.close()
            browser.close()

    log.info("处理完成")




if __name__ == "__main__":
    目录 = sys.argv[1] if len(sys.argv) > 1 else input("请输入文件夹目录：").strip()
    main(目录)
