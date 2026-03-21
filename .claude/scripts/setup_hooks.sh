#!/bin/bash
# Claude Agent Hooks 环境设置脚本（Linux/macOS）
# 用途：安装所有必需的工具和依赖
# 使用：bash setup_hooks.sh

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🔧 Claude Agent Hooks 环境设置${NC}"
echo -e "${CYAN}================================${NC}\n"

# 检查 Python
echo -e "${YELLOW}检查 Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✅ Python: $PYTHON_VERSION${NC}"
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version)
    echo -e "${GREEN}✅ Python: $PYTHON_VERSION${NC}"
    PYTHON_CMD="python"
else
    echo -e "${RED}❌ Python 未安装${NC}"
    exit 1
fi

# 检查 pip
echo -e "${YELLOW}检查 pip...${NC}"
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
else
    echo -e "${RED}❌ pip 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✅ pip: $($PIP_CMD --version)${NC}"

# 检查 Node.js
echo -e "${YELLOW}检查 Node.js...${NC}"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✅ Node.js: $NODE_VERSION${NC}"
else
    echo -e "${RED}❌ Node.js 未安装${NC}"
    exit 1
fi

# 检查 npm
echo -e "${YELLOW}检查 npm...${NC}"
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}✅ npm: v$NPM_VERSION${NC}"
else
    echo -e "${RED}❌ npm 未安装${NC}"
    exit 1
fi

# 安装 Python 工具
echo -e "\n${YELLOW}📦 安装 Python 开发工具...${NC}"
PYTHON_TOOLS=("black" "ruff" "mypy" "pytest" "pytest-cov" "pytest-asyncio" "pip-audit")

for tool in "${PYTHON_TOOLS[@]}"; do
    echo -ne "  - 安装 $tool..."
    if $PIP_CMD install "$tool" --quiet 2>&1; then
        echo -e " ${GREEN}✅${NC}"
    else
        echo -e " ${RED}❌${NC}"
    fi
done

# 安装后端开发依赖
echo -e "\n${YELLOW}📦 安装后端开发依赖...${NC}"
if [ -f "backend/requirements-dev.txt" ]; then
    cd backend
    $PIP_CMD install -r requirements-dev.txt
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 后端开发依赖安装完成${NC}"
    else
        echo -e "${RED}❌ 后端开发依赖安装失败${NC}"
    fi
    cd ..
else
    echo -e "${YELLOW}⚠️  backend/requirements-dev.txt 不存在${NC}"
fi

# 安装前端依赖
echo -e "\n${YELLOW}📦 安装前端依赖...${NC}"
if [ -f "package.json" ]; then
    npm install --silent
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 前端依赖安装完成${NC}"
    else
        echo -e "${RED}❌ 前端依赖安装失败${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  package.json 不存在${NC}"
fi

# 安装前端开发工具
echo -e "\n${YELLOW}📦 安装前端开发工具...${NC}"
FRONTEND_TOOLS=("prettier" "eslint" "@typescript-eslint/parser" "@typescript-eslint/eslint-plugin")

for tool in "${FRONTEND_TOOLS[@]}"; do
    echo -ne "  - 安装 $tool..."
    if npm install --save-dev "$tool" --silent 2>&1; then
        echo -e " ${GREEN}✅${NC}"
    else
        echo -e " ${YELLOW}⚠️ (可能已存在)${NC}"
    fi
done

# 创建日志目录
echo -e "\n${YELLOW}📁 创建日志目录...${NC}"
LOG_DIR=".claude/logs"
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
    echo -e "${GREEN}✅ 日志目录已创建: $LOG_DIR${NC}"
else
    echo -e "${GREEN}✅ 日志目录已存在${NC}"
fi

# 创建备份目录
echo -e "${YELLOW}📁 创建备份目录...${NC}"
BACKUP_DIR=".claude/backups"
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    echo -e "${GREEN}✅ 备份目录已创建: $BACKUP_DIR${NC}"
else
    echo -e "${GREEN}✅ 备份目录已存在${NC}"
fi

# 创建配置文件（如果不存在）
echo -e "\n${YELLOW}📄 检查配置文件...${NC}"

if [ ! -f ".prettierrc" ]; then
    echo -ne "创建 .prettierrc..."
    cat > .prettierrc << 'EOF'
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": true,
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false
}
EOF
    echo -e " ${GREEN}✅${NC}"
fi

if [ ! -f "backend/.ruff.toml" ]; then
    echo -ne "创建 backend/.ruff.toml..."
    cat > backend/.ruff.toml << 'EOF'
line-length = 100
target-version = "py310"

[lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "DTZ", "T10", "EM", "ISC", "ICN", "G", "PIE", "PT", "Q", "RET", "SIM", "TID", "ARG", "ERA", "PD", "PL", "TRY", "NPY", "RUF"]
ignore = ["E501", "B008", "TRY003"]

[lint.per-file-ignores]
"__init__.py" = ["F401"]
"tests/**/*.py" = ["ARG", "PLR2004"]
EOF
    echo -e " ${GREEN}✅${NC}"
fi

# 测试配置
echo -e "\n${YELLOW}🧪 测试 Hooks 配置...${NC}"

echo -ne "  - 测试 Black..."
if echo "print('test')" | $PYTHON_CMD -m black - --quiet > /dev/null 2>&1; then
    echo -e " ${GREEN}✅${NC}"
else
    echo -e " ${RED}❌${NC}"
fi

echo -ne "  - 测试 Ruff..."
TEST_FILE="backend/test_temp.py"
echo "print('test')" > "$TEST_FILE"
cd backend
if ruff check test_temp.py --quiet > /dev/null 2>&1; then
    echo -e " ${GREEN}✅${NC}"
else
    echo -e " ${RED}❌${NC}"
fi
rm -f test_temp.py
cd ..

echo -ne "  - 测试 Prettier..."
if echo "console.log('test')" | npx prettier --parser typescript --stdin-filepath test.ts > /dev/null 2>&1; then
    echo -e " ${GREEN}✅${NC}"
else
    echo -e " ${RED}❌${NC}"
fi

echo -ne "  - 测试 pytest..."
cd backend
if pytest --version > /dev/null 2>&1; then
    echo -e " ${GREEN}✅${NC}"
else
    echo -e " ${RED}❌${NC}"
fi
cd ..

echo -ne "  - 测试 Vitest..."
if npx vitest --version > /dev/null 2>&1; then
    echo -e " ${GREEN}✅${NC}"
else
    echo -e " ${RED}❌${NC}"
fi

# 设置脚本可执行权限
echo -e "\n${YELLOW}🔐 设置脚本权限...${NC}"
chmod +x .claude/scripts/*.sh .claude/scripts/*.py 2>/dev/null || true
echo -e "${GREEN}✅ 脚本权限已设置${NC}"

# 完成
echo -e "\n${CYAN}✨ 环境设置完成！${NC}\n"
echo -e "${YELLOW}📖 下一步：${NC}"
echo -e "  ${NC}1. 查看配置：.claude/hooks.json${NC}"
echo -e "  ${NC}2. 阅读文档：.claude/HOOKS_GUIDE.md${NC}"
echo -e "  ${NC}3. 启用需要的 Hooks：编辑 hooks.json 中的 'enabled' 字段${NC}"
echo -e "  ${NC}4. 测试 Hooks：修改一个文件并观察 Claude Code 的行为${NC}\n"
