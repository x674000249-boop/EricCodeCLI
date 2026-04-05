# 🚀 EricCode

**AI驱动的智能编码助手CLI工具**

一个vibe coding出的功能不强大的命令行工具，提供代码生成、补全、解释、对话等辅助功能，支持本地模型和OpenAI API。

## ✨ 核心功能

- **💡 代码生成**：基于自然语言描述生成高质量代码
- **⚡ 代码补全**：实时的智能代码建议
- **📖 代码解释**：深入分析代码功能和逻辑
- **💬 对话模式**：与AI助手进行交互式对话
- **🌐 多模型支持**：OpenAI API + 本地模型执行
- **🔒 敏感信息检测**：自动识别和处理敏感信息
- **📦 格式转换**：智能格式转换工具
- **🎮 文字冒险游戏**：终端文字冒险游戏
- **🤖 Shell命令生成**：自然语言转Shell命令
- **🚀 Git智能提交**：自动生成符合规范的提交信息

## 🛠️ 安装

### 快速安装

```bash
# 克隆代码库
git clone https://github.com/x674000249-boop/ericcode.git

# 进入目录
cd ericcode

# 运行快速启动脚本
./setup.sh
```

### 手动安装

```bash
# 安装依赖
pip install -e ".[all]"

# 配置环境变量（可选）
# 创建 .env 文件并添加以下内容：
# ERICCODE_OPENAI_API_KEY=your_api_key
# ERICCODE_OPENAI_BASE_URL=http://localhost:1234/v1
# ERICCODE_OPENAI_DEFAULT_MODEL=local-model
```

## 🚀 使用

### 基本命令

```bash
# 显示版本信息
ericcode version

# 查看帮助信息
ericcode --help

# 启动对话模式
ericcode chat

# 生成代码
ericcode generate "创建一个Python函数计算斐波那契数列" --lang python

# 代码补全
ericcode complete path/to/your/code.py

# 代码解释
ericcode explain path/to/your/code.py
```

### 小参数模型项目

#### Shell Wizard - 自然语言转Shell命令

```bash
# 示例：查找当前目录下所有Python文件
ericcode shell-wizard "查找当前目录下所有Python文件"

# 示例：删除当前目录大于100M的文件
ericcode shell-wizard "删除当前目录大于100M的文件"
```

#### Secret Scrubber - 敏感信息清洗

```bash
# 示例：清洗敏感信息
echo 'API_KEY=sk-1234567890abcdef' | ericcode secret-scrubber

# 示例：清洗日志文件
cat log.txt | ericcode secret-scrubber
```

#### Git Smart Commit - 智能Git提交信息

```bash
# 先添加文件到暂存区
git add .

# 生成并提交
ericcode git-smart-commit

# 或指定提交信息前缀
ericcode git-smart-commit --message "feat:"
```

#### Format Shifter - 格式转换

```bash
# 示例：JSON转YAML
echo '{"name": "Eric", "age": 25}' | ericcode format-shifter --format yaml

# 示例：转成Markdown表格
curl api/data | ericcode format-shifter "转成Markdown表格"
```

#### Dungeon CLI - 文字冒险游戏

```bash
# 启动游戏
ericcode dungeon-cli --name "冒险者"

# 加载保存的游戏
ericcode dungeon-cli --load
```

### LM Studio 集成

```bash
# 打开LM Studio
ericcode lm-studio open

# 检查LM Studio状态
ericcode lm-studio status

# 查看LM Studio配置
ericcode lm-studio config
```

## 🔧 配置

### 环境变量

创建 `.env` 文件：

```env
# OpenAI API 配置
ERICCODE_OPENAI_API_KEY=your_api_key
ERICCODE_OPENAI_BASE_URL=http://localhost:1234/v1  # LM Studio
ERICCODE_OPENAI_DEFAULT_MODEL=local-model

# 其他配置
ERICCODE_LOG_LEVEL=INFO
ERICCODE_UI_THEME=dark
```

### 配置文件

配置文件位于 `~/.ericcode/config.toml`：

```toml
[openai]
api_key = "your_api_key"
base_url = "http://localhost:1234/v1"
default_model = "local-model"

[local]
model_path = "path/to/model"
device = "cpu"

[cache]
enabled = true
memory_cache_size = 100
file_cache_path = "~/.ericcode/cache"
```

## 📁 项目结构

```
ericcode/
├── src/
│   └── ericcode/
│       ├── cli.py             # CLI入口
│       ├── config/            # 配置管理
│       ├── core/              # 核心功能
│       ├── providers/         # 模型提供商
│       ├── cache/             # 缓存系统
│       └── utils/             # 工具函数
├── tests/                     # 测试文件
├── pyproject.toml             # 项目配置
├── setup.sh                   # 快速启动脚本
└── demo.sh                    # 功能展示脚本
```

## 🎯 技术特点

- **多模型支持**：同时支持OpenAI API和本地模型
- **智能路由**：根据任务类型自动选择合适的模型
- **多级缓存**：内存、文件、Redis三级缓存系统
- **安全扫描**：自动检测和处理敏感信息
- **Git集成**：智能分析diff生成提交信息
- **管道支持**：支持Unix管道操作
- **中英双语**：完整的中文交互支持

## 🚀 性能优化

- **小参数模型**：针对1B~7B量化模型优化
- **毫秒级响应**：本地模型快速推理
- **零网络依赖**：完全离线运行
- **内存优化**：量化模型减少内存占用

## 🔒 安全注意事项

- **本地运行**：敏感代码和数据不离开本地环境
- **敏感信息检测**：自动识别和处理API密钥等敏感信息
- **缓存安全**：加密存储缓存数据
- **权限控制**：最小权限原则

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🌟 作者

- **用户名**: NoWint
- **GitHub**: [https://github.com/x674000249-boop](https://github.com/x674000249-boop)
- **邮箱**: x674000249@gmail.com

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- GitHub Issues: [https://github.com/x674000249-boop/ericcode/issues](https://github.com/x674000249-boop/ericcode/issues)
- 邮箱: x674000249@gmail.com

---

**EricCode** - 依旧vibe coding做着玩的！🚀
