#!/bin/bash

# EricCode 快速启动脚本
# 让用户在git clone后能够一行代码直接使用

echo "🚀 EricCode 快速启动脚本"
echo "================================"
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: Python 3 未安装"
    echo "请先安装Python 3.8或更高版本"
    exit 1
fi

# 检查pip是否安装
if ! command -v pip3 &> /dev/null; then
    echo "❌ 错误: pip 未安装"
    echo "请先安装pip"
    exit 1
fi

# 检查是否在正确的目录
if [ ! -f "pyproject.toml" ]; then
    echo "❌ 错误: 请在EricCode项目根目录运行此脚本"
    exit 1
fi

echo "📦 安装依赖..."
# 先安装核心依赖，避免可选依赖安装失败
pip3 install -e "."
if [ $? -ne 0 ]; then
    echo "❌ 依赖安装失败"
    exit 1
fi

echo "✅ 核心依赖安装成功"

# 尝试安装可选依赖（如果失败也不影响核心功能）
echo "📦 尝试安装可选依赖..."
pip3 install -e ".[all]" 2>/dev/null || echo "⚠️  可选依赖安装失败，核心功能仍可使用"


echo "✅ 依赖安装成功"
echo ""

# 创建.env文件（如果不存在）
if [ ! -f ".env" ]; then
    echo "📝 创建.env文件..."
    cat > .env << EOF
# EricCode 配置文件
# LM Studio API 配置
ERICCODE_OPENAI_API_KEY=sk-lm-wCRaL76B:72O3mheWw5Fc4XSbsJDc
ERICCODE_OPENAI_BASE_URL=http://localhost:1234/v1
ERICCODE_OPENAI_DEFAULT_MODEL=local-model

# 其他配置
ERICCODE_LOG_LEVEL=INFO
ERICCODE_UI_THEME=dark
EOF
    echo "✅ .env文件创建成功"
    echo ""
fi

echo "🔧 检查LM Studio..."
ericcode lm-studio status
if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️ LM Studio未运行"
    echo "请先下载并安装LM Studio: https://lmstudio.ai/"
    echo ""
    echo "安装完成后，请运行: ericcode lm-studio open"
    echo ""
fi

echo ""
echo "✅ 安装完成！"
echo ""
echo "🚀 快速开始:"
echo "1. 启动LM Studio并启用OpenAI兼容API"
echo "2. 运行: ericcode shell-wizard '查找当前目录下所有Python文件'"
echo "3. 或运行: ericcode chat"
echo ""
echo "📖 查看所有命令: ericcode --help"
echo ""
echo "🎮 尝试文字冒险游戏: ericcode dungeon-cli --name '冒险者'"
echo ""
