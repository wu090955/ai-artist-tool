# Changelog

## [v12.1] - 2026-04-07

### ✨ 新功能 (New Feature)

#### 画师串反向导入 (Prompt String Import)
- 右侧「咒语生成」区域的文本框改为**可编辑**，支持直接粘贴画师串
- 新增琥珀色 **「导入串」** 按钮，点击后自动解析并填充右侧画师栏
- **解析格式支持**：
  - NAI 加权格式：`0.8::artist1, artist2::` → artist1/artist2 权重 0.8
  - NAI 混合格式：`0.8::artistA::, artistB, 1.2::artistC, artistD::` → 各自权重
  - NAI `artist:` 限定词前缀：`artist:nixeu` → 自动剥除前缀识别为 `nixeu`
  - WebUI 加权格式：`(artist_name:1.1)` → 权重 1.1
  - 普通逗号分隔：`artist1, artist2` → 默认权重 1.0
- **匹配策略**（多层容错）：
  1. 精确匹配 tag 或 name（不区分大小写）
  2. DB tag 带 `artist:` 前缀但输入不带（自动适配）
  3. 输入带 `artist:` 前缀但 DB 不带（反向适配）
- **未匹配画师**显示为 Ghost 占位卡（虚线边框 + 🔶「未匹配」徽章），权重可调、可删除
- 导入完成后显示 Toast 通知，提示已匹配数量和未找到占位数量
- 清空按钮同步清理所有 Ghost 占位条目

### 🐛 Bug 修复 (Bug Fixes)

#### 修复 NAI 解析器正则匹配错误
- **问题 1（数字歧义）**：旧正则 `[\d]*\.?[\d]*` 可匹配空字符串，导致字符串中任意 `::content::` 均能被视为带权重的 NAI 组，引发无权重内容被错误分组
  - **修复**：权重改为严格 `\d+(?:\.\d+)?`，要求至少一位数字，不再匹配空字符串
- **问题 2（`artist:` 前缀）**：旧版不处理 NAI 的 `artist:` qualifier，导致 `artist:nixeu` 在 DB 中查找 `artist:nixeu` 而非 `nixeu`，命中率为零
  - **修复**：新增 `stripArtistPrefix()` 函数，解析阶段统一剥除 `artist:` 前缀；查库时也尝试带/不带前缀两种形式
- **问题 3（单冒号画师名导致 NAI 组解析失败）**：旧正则内容部分 `[^:]+?` 遇到**任何** `:` 就中止，导致画师名含单冒号时（如 `artist:bm94199`）整个 NAI 组无法识别，进而产生三个错误副产物：
  - `1.3:: artist:bm`（错误的 bare text）
  - `1.7`（被错误识别为 NAI 组的"内容"）
  - `nixeu ::`（未被识别为组成员、以 bare text 处理后残留结尾 `::`)
  - **修复**：内容部分改为 `(?:[^:]|:(?!:))+?`，使用负前瞻 `(?!:)` 区分单冒号（允许）与双冒号（停止），彻底解决单冒号画师名解析问题

### 🔧 其他改进 (Other Improvements)

- 修复卡片选中样式：CSS 中 `ring: 3px` 改为标准属性 `outline: 3px`+`outline-offset: 2px`（Tailwind 的 `ring` 不能直接用于 `<style>` 块）
- 右侧空画师栏提示文字更新，增加「粘贴画师串导入」引导
- 完善 HTML `<head>` SEO 元数据（meta description、Open Graph、内联 SVG Favicon）
- NAI 格式输出去掉多余空格：`${w}:: ${tag} ::` → `${w}::${tag}::`

---

## [v12.0] - 2026-03-21

首个正式版本。核心功能：IndexedDB 图片存储、画师 Tag 组合与权重调节、饼图可视化、拖拽排序、批量管理、风格预设系统。
