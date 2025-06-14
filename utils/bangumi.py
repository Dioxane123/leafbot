# -*- coding: utf-8 -*-
# 导入所有需要的库
import os
import re

import feedparser
import requests
from pathlib import Path
from loguru import logger

# --- 1. 初始化和配置加载 (与之前基本相同) ---

# 获取当前脚本文件所在的目录路径
workspace = Path(os.path.realpath(__file__)).parent

# 确定配置文件的路径
if env_config_path := os.getenv("MTA_CONFIGPATH"):
    logger.info(f"从环境变量加载配置文件, 路径: {env_config_path}")
    config_path = Path(env_config_path)
else:
    logger.info("使用默认配置文件路径, .cache/bangumi_config/config.json")
    config_path = Path(".cache/bangumi_config/config.json")

# 从配置文件加载配置
config = None
if config_path.exists() and config_path.is_file():
    if config_path.suffix == '.json':
        import json
        config = json.load(config_path.open(encoding="utf8"))
        logger.info(f"成功加载配置文件: {config_path.as_posix()}")
    else:
        logger.warning(f"不支持的配置文件类型, {config_path.name}")

if not config:
    logger.error("配置文件未找到或加载失败!")
    exit(1)

# 确定历史记录文件的路径
if history_path := os.getenv("MTA_HISTORY_FILE"):
    history_path = Path(history_path)
else:
    history_path = Path(".cache/bangumi_config/history.txt")
logger.info(f"使用历史记录文件: {history_path.as_posix()}")
history_path.parent.mkdir(parents=True, exist_ok=True)

# 确定 .torrent 文件的根保存目录
if torrent_dir := os.getenv("MTA_TORRENTS_DIR"):
    torrent_base_dir = Path(torrent_dir)
else:
    torrent_base_dir = Path("/home/ecs-user/bangumi/bangumi")
logger.info(f"种子文件将保存在根目录: {torrent_base_dir.as_posix()}")
torrent_base_dir.mkdir(parents=True, exist_ok=True)  # 确保根目录存在

# 设置历史记录的最大条目数
MAX_HISTORY = os.getenv("MTA_MAX_HISTORY", max(300, len([f for f in config.get('mikan', []) if f.get('enable', True)]) * 48))
logger.info(f"最大历史记录条数设置为 {MAX_HISTORY}")


# --- 2. 函数定义 ---

def load_history() -> set:
    """从 history.txt 文件中加载下载历史记录"""
    history = set()
    if history_path.exists() and history_path.is_file():
        with history_path.open(encoding='utf8') as f:
            for line in f:
                bang = line.strip()
                if bang == '':
                    continue
                history.add(bang)
                if len(history) >= MAX_HISTORY:
                    break
    else:
        history_path.touch(exist_ok=True)
    return history

# 加载历史记录到全局变量中
downloaded_history = load_history()

# 用于存储本次运行中新下载的项目的标题
cache: list[str] = []

# --- 3. 初始化 HTTP 客户端 (移除了 Aria2 初始化) ---

# 初始化 HTTP 请求会话 (session)
session = requests.session()
# 从环境变量或配置文件中加载代理设置
# if http_proxy := os.getenv("HTTP_PROXY"):
#     session.proxies.update(http=http_proxy)
# if https_proxy := os.getenv("HTTPS_PROXY"):
#     session.proxies.update(https=https_proxy)
# if proxy := config.get('proxy'):
#     session.proxies.update(proxy)

# 设置 User-Agent
agent = os.getenv("MTA_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.82")
session.headers = {"user-agent": agent}


# --- 【核心修改】新增的函数：下载并保存种子文件 ---
def download_and_save_torrent(url: str, save_dir: str, title: str):
    """
    下载 .torrent 文件, 根据标题重命名后保存到指定的子目录中。

    :param url: .torrent 文件的下载链接
    :param save_dir: 要保存在哪个子目录 (通常是番剧名)
    :param title: RSS 条目的原始标题, 用于生成文件名
    """
    # 对原始标题进行清理, 移除在文件名中非法的字符, 使其成为一个安全的文件名
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
    new_filename = f"{safe_title}.torrent"

    # 构造最终的保存路径, 如: torrents/某某番剧/净化后的标题.torrent
    save_path = torrent_base_dir.joinpath(save_dir, new_filename)

    # 确保番剧专属的子目录存在, 如果不存在则创建
    save_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"准备下载种子: {title}")
    try:
        # 使用 session 下载 .torrent 文件
        resp = session.get(url)
        resp.raise_for_status()  # 如果请求失败 (例如 404), 会抛出异常
        
        # 将下载的二进制内容写入文件
        save_path.write_bytes(resp.content)
        logger.success(f"成功保存种子文件到: {save_path.as_posix()}")

    except requests.exceptions.RequestException as e:
        logger.error(f"下载种子文件 {url} 失败, 错误: {e}")


# --- 【核心修改】修改 get_latest 函数, 调用新的保存方法 ---
def get_latest(url, rule=None, savedir=None):
    """获取指定 RSS feed 的最新更新, 并下载保存种子文件"""
    bangumi_cache = set()
    try:
        content = session.get(url).content
    except requests.exceptions.RequestException as e:
        logger.error(f"无法获取 RSS Feed: {url}, 错误: {e}")
        return # 获取失败则直接返回

    entries = feedparser.parse(content)

    if savedir:
        bangumi_name = savedir
    else:
        bangumi_name = entries['feed']['title'].replace("Mikan Project - ", "")

    for entry in entries['entries']:
        title = entry['title'].strip()

        if rule and not re.search(rule, title):
            continue

        if title not in downloaded_history and title not in bangumi_cache:
            download_url = None
            for link in entry['links']:
                if link.get('type') == 'application/x-bittorrent':
                    download_url = link['href']
                    break  # 找到后即可退出循环

            if download_url:
                # 【调用新函数】将下载任务交给新的保存函数处理
                download_and_save_torrent(download_url, bangumi_name, title)
                bangumi_cache.add(title)
                cache.append(title)
        else:
            # logger.debug(f"跳过已处理的条目: {title}")
            continue

    downloaded_history.update(bangumi_cache)


def write_history(line):
    """将新的下载历史写入文件顶部 (此函数未改变)"""
    line = line.strip()
    if line == '':
        return
    with history_path.open(mode='r+', encoding='utf8') as w:
        content = w.read()
        w.seek(0, 0)
        w.write(line + '\n' + content)


# --- 4. 主程序运行 (逻辑基本未变) ---
@logger.catch
def run() -> list[str]:
    """主执行函数"""
    global config
    config = json.load(config_path.open(encoding="utf8"))
    logger.info("开始检查 Mikan RSS Feed 更新...")
    logger.info(config)
    for bangumi in config.get('mikan', []):
        if not bangumi.get('enable', True):
            continue

        url = bangumi.get('url')
        if not url:
            logger.warning("发现一个已启用但没有提供 url 的配置项, 已跳过。")
            continue
            
        rule = bangumi.get('rule') or None
        savedir = bangumi.get('savedir') or None
        
        get_latest(url, rule=rule, savedir=savedir)

    if len(cache) > 0:
        logger.info(f"本次运行共新增 {len(cache)} 个种子文件, 正在更新历史记录...")
        write_history('\n'.join(cache[::-1]))
    else:
        logger.info("本次运行没有发现新更新。")
    logger.info("运行结束。")
    return cache


if __name__ == '__main__':
    run()