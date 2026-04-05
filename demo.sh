#!/bin/bash

# EricCode 功能展示脚本
# 一键展示所有功能

echo "🚀 EricCode 功能展示脚本"
echo "================================"
echo ""
echo "这个脚本会依次展示 EricCode 的所有核心功能"
echo ""

# 等待用户准备好
read -p "按回车键开始展示..."

# 1. 版本信息
echo ""
echo "1. 📦 版本信息"
echo "----------------"
ericcode version
echo ""

# 2. 帮助信息
echo "2. 📖 帮助信息"
echo "----------------"
ericcode --help
echo ""

# 3. LM Studio 状态
echo "3. 🧠 LM Studio 状态"
echo "----------------"
ericcode lm-studio status
echo ""

# 4. Shell Wizard
echo "4. ⚡ Shell Wizard (自然语言转Shell命令)"
echo "----------------"
echo "输入: 查找当前目录下所有Python文件"
ericcode shell-wizard "查找当前目录下所有Python文件"
echo ""

# 5. Secret Scrubber
echo "5. 🔒 Secret Scrubber (敏感信息清洗)"
echo "----------------"
echo "输入: API_KEY=sk-1234567890abcdef"
echo "API_KEY=sk-1234567890abcdef" | ericcode secret-scrubber
echo ""

# 6. Format Shifter
echo "6. 🔄 Format Shifter (格式转换)"
echo "----------------"
echo "输入: {\"name\": \"Eric\", \"age\": 25}"
echo '{"name": "Eric", "age": 25}' | ericcode format-shifter --format yaml
echo ""

# 7. Git Smart Commit
echo "7. 💡 Git Smart Commit (智能Git提交信息)"
echo "----------------"
echo "注意: 此功能需要Git仓库环境"
echo "如果当前目录不是Git仓库，将跳过此测试"
if [ -d ".git" ]; then
    echo "当前目录是Git仓库，演示Git提交信息生成..."
    # 创建一个测试文件
    echo "# Test file" > test_commit.txt
    git add test_commit.txt
    echo "生成提交信息..."
    ericcode git-smart-commit --message "测试"
    # 清理
    git reset HEAD test_commit.txt
    rm test_commit.txt
else
    echo "当前目录不是Git仓库，跳过此测试"
fi
echo ""

# 8. Dungeon CLI
echo "8. 🎮 Dungeon CLI (文字冒险游戏)"
echo "----------------"
echo "启动一个简短的文字冒险游戏..."
echo "将运行3个步骤后自动退出"
echo ""
echo "输入: 查看状态"
echo "输入: 向前走"
echo "输入: exit"

# 创建一个临时脚本用于游戏交互
cat > /tmp/dungeon_test.sh << 'EOF'
sleep 1
echo "状态"
sleep 2
echo "向前走"
sleep 2
echo "exit"
EOF

chmod +x /tmp/dungeon_test.sh

# 运行游戏并通过管道输入命令
/tmp/dungeon_test.sh | ericcode dungeon-cli --name "冒险者"

# 清理临时文件
rm /tmp/dungeon_test.sh
echo ""

# 9. Generate
echo "9. ✨ Generate (代码生成)"
echo "----------------"
echo "生成一个简单的Python函数..."
ericcode generate "创建一个Python函数，计算斐波那契数列" --lang python --temperature 0.3
echo ""

# 10. Chat
echo "10. 💬 Chat (对话模式)"
echo "----------------"
echo "启动一个简短的对话..."
echo "将问一个问题后自动退出"
echo ""
echo "输入: 你好，你是谁？"
echo "输入: exit"

# 创建一个临时脚本用于对话交互
cat > /tmp/chat_test.sh << 'EOF'
sleep 1
echo "你好，你是谁？"
sleep 3
echo "exit"
EOF

chmod +x /tmp/chat_test.sh

# 运行对话并通过管道输入命令
/tmp/chat_test.sh | ericcode chat

# 清理临时文件
rm /tmp/chat_test.sh
echo ""

# 完成
echo "✅ 功能展示完成！"
echo ""
echo "🚀 你现在可以开始使用 EricCode 了！"
echo ""
echo "常用命令:"
echo "- ericcode shell-wizard '查找当前目录下所有Python文件'"
echo "- ericcode chat"
echo "- ericcode generate '创建一个Python函数' --lang python"
echo "- ericcode dungeon-cli --name '冒险者'"
echo ""
echo "📖 查看所有命令: ericcode --help"
