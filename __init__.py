import httpx
from typing import List, Optional
from pydantic import BaseModel, Field

from nekro_agent.services.plugin.base import NekroPlugin, ConfigBase, SandboxMethodType
from nekro_agent.api.schemas import AgentCtx
from nekro_agent.core import logger

# 插件实例
plugin = NekroPlugin(
    name="ACG图片搜索插件",
    module_name="acg_image_search",
    description="提供二次元图片搜索功能",
    version="1.2.0",
    author="XGGM",
    url="https://github.com/XG2020/acg_image_search",
)

@plugin.mount_config()
class AcgImageConfig(ConfigBase):
    """ACG图片搜索配置"""
    API_URL: str = Field(
        default="https://api.lolicon.app/setu/v2",
        title="API地址",
        description="lolicon API的基础URL",
    )
    R18_ENABLED: bool = Field(
        default=False,
        title="R18内容开关",
        description="是否允许R18内容",
    )
    TIMEOUT: float = Field(
        default=30.0,
        title="请求超时时间",
        description="API请求的超时时间(秒)",
    )
    MAX_TAGS: int = Field(
        default=3,
        title="最大标签数",
        description="允许的最大搜索标签数量",
    )
    MAX_RETRIES: int = Field(
        default=3,
        title="最大重试次数",
        description="当搜索结果为空时的最大重试次数",
    )

# 获取配置
config = plugin.get_config(AcgImageConfig)

async def fetch_image_data(tags: List[str]) -> Optional[str]:
    """获取图片URL数据
    
    Args:
        tags: 搜索标签列表
        
    Returns:
        str: 图片URL，如果找不到图片则返回None
        
    Raises:
        httpx.RequestError: 请求失败时抛出
        httpx.HTTPStatusError: HTTP状态错误时抛出
        KeyError: 数据解析错误时抛出
    """
    params = {
        "r18": 2 if config.R18_ENABLED else 0,
        "num": 1,
        "tag": tags,
        "size": "original"
    }
    
    async with httpx.AsyncClient(timeout=config.TIMEOUT) as client:
        response = await client.post(config.API_URL, json=params)
        response.raise_for_status()
        data = response.json()
        
        # 检查是否有返回数据
        if not data.get("data") or not data["data"]:
            return None
            
        return data["data"][0]["urls"]["original"]

async def download_image(url: str) -> Optional[bytes]:
    """下载图片数据并验证内容
    
    Args:
        url: 图片URL
        
    Returns:
        bytes: 图片字节流，如果下载失败或内容为空则返回None
        
    Raises:
        httpx.RequestError: 请求失败时抛出
        httpx.HTTPStatusError: HTTP状态错误时抛出
    """
    async with httpx.AsyncClient(timeout=config.TIMEOUT) as client:
        response = await client.get(url)
        response.raise_for_status()
        
        # 验证图片内容是否有效
        if not response.content or len(response.content) < 1024:  # 假设小于1KB为无效图片
            return None
        
        return response.content

def adjust_tags(tags: List[str], attempt: int) -> List[str]:
    """根据重试次数调整标签列表
    
    Args:
        tags: 原始标签列表
        attempt: 当前重试次数
        
    Returns:
        List[str]: 调整后的标签列表
    """
    if len(tags) <= 1:
        return tags
        
    # 根据重试次数移除部分标签
    return tags[:max(1, len(tags) - attempt)]

@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="acg_image_search",
    description="二次元高清插画/壁纸/同人图获取工具。仅在用户明确索要高质量美图/涩图时调用，【严禁】用于获取“表情包”、“梗图”或聊天配图。",
)
async def acg_image_search(_ctx: AgentCtx, tags: List[str]) -> bytes:
    """ACG高质量插画搜索工具
    
    专门用于根据标签获取高质量的二次元人物插画、壁纸或同人美术作品，仅返回.jpg格式图片。
    
    【行为约束 - 必读】
    1. 绝非表情包工具：本工具返回的均为完整的高清艺术画作。当用户想要“表情包”、“梗图”、“沙雕图”或聊天辅助配图时，绝对不要调用此工具。
    2. 标签规范：传入的 tags 必须是具体的【作品名】、【角色名】或【美术特征】（如黑丝、女仆等）。严禁在 tags 中加入“表情包”、“搞笑”、“meme”等词汇。
    
    【搜索规则】
    - 最多支持3个标签同时搜索。
    - 当搜索结果为空时，会自动尝试调整标签组合进行多次搜索。
    
    Args:
        tags: 搜索标签列表，最多3个标签。例如：["初音未来", "初音ミク"] 或 ["明日方舟", "能天使"]。
        
    Returns:
        bytes: 图片字节流。如果最终找不到有效图片则返回错误消息的字节流，您需要自行接受图片字节流。
        
    Raises:
        ValueError: 如果标签数量超过限制或为空
    """
    if not tags:
        raise ValueError("至少需要提供一个搜索标签")
    if len(tags) > config.MAX_TAGS:
        raise ValueError(f"最多支持{config.MAX_TAGS}个标签同时搜索")
        
    clean_tags = [t.strip() for t in tags if t.strip()]
    last_error = ""
    
    for attempt in range(config.MAX_RETRIES + 1):
        current_tags = adjust_tags(clean_tags, attempt)
        try:
            # 获取图片URL
            image_url = await fetch_image_data(current_tags)
            
            if not image_url:
                logger.info(f"未找到匹配图片，尝试 {attempt+1}/{config.MAX_RETRIES}，标签: {current_tags}")
                continue
                
            # 下载图片
            image_data = await download_image(image_url) if image_url.startswith("http") else image_url.encode()
            
            if not image_data:
                logger.info(f"下载的图片数据为空，尝试 {attempt+1}/{config.MAX_RETRIES}，标签: {current_tags}")
                continue
                
            return image_data
            
        except httpx.RequestError as e:
            last_error = f"图片搜索请求失败: {str(e)}"
            logger.error(last_error)
        except httpx.HTTPStatusError as e:
            last_error = f"图片搜索HTTP错误: {e.response.status_code}"
            logger.error(last_error)
        except KeyError as e:
            last_error = f"图片数据解析错误: {str(e)}"
            logger.error(last_error)
        except Exception as e:
            last_error = f"图片搜索未知错误: {str(e)}"

@plugin.mount_cleanup_method()
async def clean_up():
    """清理插件资源"""
    logger.info("ACG图片搜索插件资源已清理")
