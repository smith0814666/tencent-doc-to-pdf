# 腾讯文档下载器 (Tencent Docs PDF Downloader)

一个简单易用的命令行工具，可以将腾讯文档（docs.qq.com）下载为 PDF 文件。

## 功能特点

- ✅ 支持公开文档直接下载，无需登录
- ✅ 支持私有文档，扫码登录或密码登录
- ✅ 自动保存 Cookie，无需重复登录
- ✅ 保留文档格式（标题、段落、对齐方式）
- ✅ 支持图片下载
- ✅ 生成的 PDF 兼容 macOS Preview、Chrome、WPS 等阅读器
- ✅ 自动从文档标题生成文件名

## 安装依赖

确保已安装 Python 3.7+，然后安装所需依赖：

```bash
pip install -r requirements.txt
```

### 依赖说明

- `requests` - HTTP 请求
- `selenium` + `chromedriver-autoinstaller` - 浏览器自动化登录（用于私有文档）
- `weasyprint` - PDF 生成备用方案

## 使用方法

### 基本用法

```bash
python main.py <腾讯文档URL>
```

例如：

```bash
python main.py https://docs.qq.com/doc/xxxxx
```

或者只提供文档 ID：

```bash
python main.py xxxxxxxxxx
```

### 交互模式

如果不提供 URL 参数，程序会提示输入：

```bash
python main.py
```

然后输入文档链接即可。

### 指定输出文件名

使用 `-o` 或 `--output` 参数指定输出文件名（可选）：

```bash
python main.py https://docs.qq.com/doc/XXXXX -o 我的文档.pdf
```

如果不指定，会自动从文档标题生成文件名。

### 强制重新登录

使用 `--relogin` 参数清除已保存的 Cookie 并重新登录：

```bash
python main.py https://docs.qq.com/doc/XXXXX --relogin
```

## 工作流程

1. **获取文档** - 首先尝试公开访问，如果文档需要权限则使用已保存的 Cookie，如果 Cookie 失效则打开浏览器登录
2. **解析内容** - 提取文档的标题、正文内容和格式信息
3. **生成 PDF** - 使用 Chrome 或 WeasyPrint 将 HTML 转换为 PDF

## 注意事项

### 浏览器要求

程序会尝试自动查找 Chrome/Chromium 浏览器。如果未找到，会使用 WeasyPrint 作为备用方案生成 PDF。

支持的 Chrome 路径：
- macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- Linux: `google-chrome` 或 `chromium`（在 PATH 中）

### Cookie 文件

- Cookie 保存在项目根目录的 `.cookies.json` 文件中
- 该文件已添加到 `.gitignore`，不会泄露到 Git
- 可以安全删除此文件以清除登录状态

### 私有文档访问

对于需要登录的私有文档：
1. 程序会自动打开 Chrome 浏览器
2. 在打开的页面中扫描二维码或输入账号密码登录
3. 登录成功后，程序会自动获取并保存 Cookie
4. 后续访问同一文档时无需重新登录

### 超时设置

浏览器登录等待时间为 5 分钟（300 秒），超时后会尝试使用已获取的 Cookie。

## 常见问题

### Q: Chrome 未找到怎么办？

A: 确保已安装 Google Chrome 或 Chromium 浏览器，并放在标准路径。或者使用 WeasyPrint 备用方案（会自动降级使用）。

### Q: 生成的 PDF 格式错乱？

A: 请确保使用较新版本的 Chrome 浏览器。某些复杂格式（如表格、多级列表）可能无法完美保留。

### Q: 图片无法显示？

A: 腾讯文档的图片需要登录才能访问。如果文档有访问权限限制，请确保已成功登录。

### Q: 如何批量下载？

A: 可以编写脚本循环调用本工具，或使用 shell 命令：

```bash
while read url; do python main.py "$url"; done < urls.txt
```

## 文件说明

```
.
├── main.py          # 主程序入口
├── fetcher.py       # 文档获取模块
├── parser.py        # 内容解析模块
├── requirements.txt # Python 依赖
├── .cookies.json    # 保存的 Cookie（自动生成）
├── .output.html     # 临时 HTML 文件（自动生成并删除）
└── README.md        # 说明文档
```

## 许可证

本项目仅供学习和个人使用。请遵守腾讯文档的使用条款和相关法律法规。