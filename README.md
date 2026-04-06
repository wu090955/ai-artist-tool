<div align="center">

# 🎨 AI Artist Manager / 画师串管理工具 V3

**一款专为 AI 绘画（Stable Diffusion/NovelAI）打造的个人画师风格、Prompt 本地管理小工具。**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Online%20Demo-success)](https://desperati0n.github.io/ai-artist-tool/)

无需安装，双击即用，帮助你高效整理、预览和组合画师标签 (Tags)，突破浏览器缓存限制。

### [🚀 点击这里在线使用 (GitHub Pages)](https://desperati0n.github.io/ai-artist-tool/)

</div>

---


## ✨ 核心功能 (Features)

| 功能 | 描述 |
| --- | --- |
| 🚀 **纯本地运行** | 单文件 HTML，0 服务端依赖。断网状态下依旧双击即用。 |
| 🎨 **极致界面与动效** | 基于 Tailwind CSS 的现代化琉璃质感 UI，平滑微动画，支持**深色模式(Dark Mode)**随意切换。 |
| 💾 **IndexedDB 大容量存储** | 抛弃了传统 LocalStorage 5MB 的存储限制，本地直接缓存海量高清画师预览图。 |
| ⚡ **即用即组 Tag** | 点击画师卡片自动在侧边栏组合 Tag，支持自由调整权重如 `(tag:1.1)`，一键复制送往 WebUI/NovelAI。 |
| 📦 **风格预设能力 (Presets)** | 支持将自己搭配的多个画师组合一键保存为“风格预设”，后续一键调用。 |
| 🛠 **批量与拖拽管理** | 提供批量选中、批量打组（分类）、批量移出以及批量删除。支持画师排序拖拽。 |
| 🔒 **数据绝对隐私** | 所有画师数据、图片素材仅存储在您的浏览器本地 IndexDB 库内，绝不上传到任何服务器。 |
| 📂 **一键本地备份** | 支持 JSON 格式的导入与导出（包含所有 Tag、基础设定及图片），换电脑依然轻松迁移数据。 |

## 📖 快速上手 (Quick Start)

### 方案一：本地离线使用 (🌟 强烈推荐)

因为本工具的数据保存在浏览器本地（IndexedDB/LocalStorage），**极度建议**大家下载到本地固定一个浏览器使用。如果完全依赖在线页面，万一浏览器清理缓存，或者在多个项目网页间穿插使用，会导致辛苦收集的画师数据丢失！

1. **下载项目**：点击仓库右上角绿色的 `Code` -> `Download ZIP`。
2. 解压到一个不会被轻易删除的文件夹。
3. 双击直接使用浏览器打开里面的 `index.html` 开始管理。
*(也可以通过 `git clone https://github.com/desperati0n/ai-artist-tool.git` 拉取最新代码)*

> ⚠️ **强烈提醒：请务必养成定期点击左侧「导出」按钮备份数据的习惯！硬盘损坏、系统重装或清理浏览器数据都可能导致数据丢失，常导出压缩包能确保您的心血万无一失。**

### 方案二：在线体验评估

如果你只是想先看看长什么样，项目已部署到 GitHub Pages，可以直接访问：
👉 **[https://desperati0n.github.io/ai-artist-tool/](https://desperati0n.github.io/ai-artist-tool/)**
*(仅适合临时体验，千万不要在这里长期存放重要数据)*

## ⚙️ 使用指南 (Guide)

1. **💡 作者的推荐用法 (测试/对比画师)**
   - 找到数个你想尝试的画师组合在右边。
   - 使用这些画师 tag，配合**极少量的质量词** (如 `masterpiece, best quality, 1girl`) 和**统一的负面词**跑一个相同特征的画面/固定随机种子。
   - 这是非常直观的对比不同AI画师风格影响力的好习惯！

2. **添加画师**
   - 点击右上角的 `+ 添加` 按钮。
   - 填写**显示名称** (例如 Mika Pikazo) 与 **Tag** (例如 `mika_pikazo`)。
   - 设定画师所在的分类，您也可以上传一张本地图片作为预览封面。
   - 保存后即可在主界面进行管理。
   
2. **构建提示词组合**
   - 点击不同画师卡片，右侧栏会自动汇总这些画师。
   - 可以点击上下箭头微调不同画师对画面的权重影响，并一键拷贝。
   
3. **导出/备份数据**
   - ⚠️ **重要提示**：因为数据保存在浏览器本地（IndexedDB/LocalStorage）中，重装系统或强行清空浏览器所有缓存会导致数据丢失。
   - **备份**：点击侧边栏的 `导出` 按钮，保存打包好的 `.json` 文件 到你的硬盘内。
   - **恢复**：在新设备上打开工具，点击侧边栏的 `导入` 按钮，读取刚才的 `.json` 即可满血复活包括所有配图在内的数据。

## 🤝 贡献 (Contributing)

欢迎提交意见反馈、Issue 或 Pull Request！
如果你觉得这个工具好用，请给一个 ⭐️ Star 支持一下！

<div align="center">
<p>Made with ❤️ for the AI Art Community</p>
</div>
