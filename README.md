# ACG图片搜索插件（Nekro Agent）

为 Nekro Agent 提供二次元图片搜索能力的插件。通过 Lolicon API v2 获取图片链接并下载图片字节流，支持标签数量限制、自动重试与标签动态缩减，包含基础的错误处理与日志记录。

## 功能概述
- 通过标签搜索图片并返回图片字节流
- 最多支持 3 个标签，自动清理空白标签
- 当结果为空时自动重试，并逐步减少标签组合
- 可配置 R18 内容、超时、重试次数与 API 地址
- 提供清理方法用于插件资源释放日志记录


## 集成与加载
- 插件实例、配置与沙盒方法均在 `init.py` 中声明并通过装饰器自动挂载
- 将本模块放置于 Nekro Agent 插件路径即可被自动发现与加载

## 使用方法
沙盒方法名称：`acg_image_search`

签名：

```python
async def acg_image_search(ctx: AgentCtx, tags: List[str]) -> bytes
```

说明：
- `tags` 为搜索标签列表（最多 3 个）
- 返回图片字节流（`bytes`），可直接写入 `.jpg` 文件
- 当搜索失败或内容无效时会进行最多 `MAX_RETRIES` 次的重试

示例（伪代码）：

```python
import asyncio
from nekro_agent.api.schemas import AgentCtx
from acg_image_search.init import acg_image_search

async def main():
    ctx = AgentCtx()  # 根据实际框架上下文初始化
    data = await acg_image_search(ctx, ["初音未来", "能天使"])
    with open("output.jpg", "wb") as f:
        f.write(data)

asyncio.run(main())
```

## 配置项
配置类：`AcgImageConfig`

- `API_URL`（默认 `https://api.lolicon.app/setu/v2`）：Lolicon API 基础地址
- `R18_ENABLED`（默认 `False`）：是否允许 R18 内容（开启则请求参数 `r18=2`，否则 `r18=0`）
- `TIMEOUT`（默认 `30.0`）：HTTP 请求超时秒数
- `MAX_TAGS`（默认 `3`）：最大标签数限制
- `MAX_RETRIES`（默认 `3`）：当结果为空时的最大重试次数

## 行为与约束
- 标签为空或超过最大数量会抛出 `ValueError`
- 内容为空或无效图片（<1KB）会被视为失败并继续重试
- 错误会通过 Nekro Agent 的 `logger` 进行记录
- 清理方法 `clean_up` 会输出插件资源释放日志

## 错误处理
可能抛出的错误类型：
- `httpx.RequestError`：网络请求失败
- `httpx.HTTPStatusError`：HTTP 状态码错误
- `KeyError`：返回数据结构解析失败
- `ValueError`：参数校验失败（标签为空或超限）

