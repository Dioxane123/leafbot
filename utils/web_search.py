"""
网络搜索模块 - 提供网络搜索功能给聊天插件使用
"""
import os
from typing import Optional
from duckduckgo_search import DDGS

# 初始化 DuckDuckGo 搜索
ddgs = DDGS()


def web_search(query: str, max_results: int = 5) -> str:
    """
    执行网络搜索

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数

    Returns:
        格式化的搜索结果字符串
    """
    try:
        results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return "没有找到相关的搜索结果呢..."

        formatted_results = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "无标题")
            href = result.get("href", "")
            body = result.get("body", "")

            formatted_results.append(f"{i}. {title}\n   {body}\n   来源: {href}")

        return "\n\n".join(formatted_results)

    except Exception as e:
        print(f"搜索出错: {e}")
        return f"搜索功能暂时不可用呢...抱歉啦主人"


def need_search(query: str) -> bool:
    """
    判断查询是否需要搜索

    Args:
        query: 用户查询

    Returns:
        是否需要搜索
    """
    search_indicators = [
        "是什么", "怎么做", "如何", "为什么",
        "多少钱", "哪里有", "哪个好", "什么牌子",
        "天气", "新闻", "最新", "介绍", "推荐",
        "查一下", "搜一下", "帮我找"
    ]

    query_lower = query.lower()
    return any(indicator in query_lower for indicator in search_indicators)
