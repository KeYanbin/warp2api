#!/bin/bash
# Warp2API 生产环境启动脚本

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 打印Logo
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║           Warp2API Production Deployment            ║"
echo "║                  生产环境部署脚本                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 加载生产环境配置
if [ -f "config/production.env" ]; then
    echo -e "${YELLOW}📋 加载生产环境配置...${NC}"
    set -a  # 自动导出所有变量
    source config/production.env
    set +a
else
    echo -e "${YELLOW}⚠️  未找到生产配置文件，使用默认配置${NC}"
    export POOL_SERVICE_URL="http://localhost:8019"
    export USE_POOL_SERVICE="true"
    export LOG_LEVEL="INFO"
fi

# 创建必要目录
mkdir -p logs
mkdir -p data

# 函数：检查Python环境
check_python() {
    echo -e "${YELLOW}🔍 检查Python环境...${NC}"
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ 未找到Python3，请先安装Python3${NC}"
        exit 1
    fi
    
    python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    echo -e "${GREEN}✓ Python版本: $python_version${NC}"
}

# 函数：安装依赖
install_dependencies() {
    echo -e "${YELLOW}📦 安装生产环境依赖...${NC}"
    
    # 账号池服务依赖
    if [ -d "account-pool-service" ]; then
        echo "  安装账号池服务依赖..."
        cd account-pool-service
        if [ -f "requirements.txt" ]; then
            python3 -m pip install -r requirements.txt --quiet
        fi
        cd ..
    fi
    
    # Warp2API主服务依赖
    if [ -d "warp2api-main" ]; then
        echo "  安装Warp2API服务依赖..."
        cd warp2api-main
        if [ -f "requirements.txt" ]; then
            python3 -m pip install -r requirements.txt --quiet
        fi
        cd ..
    fi
    
    echo -e "${GREEN}✓ 依赖安装完成${NC}"
}

# 函数：检查端口占用
check_port() {
    local port=$1
    local name=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}❌ 端口 $port 已被占用 ($name)${NC}"
        echo "请停止占用端口的服务或更改配置"
        return 1
    fi
    return 0
}

# 函数：启动账号池服务
start_pool_service() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}1️⃣  启动账号池服务...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    check_port 8019 "账号池服务" || return 1
    
    cd account-pool-service
    
    # 启动服务（使用nohup在后台运行）
    nohup python3 main.py > ../logs/pool-service.log 2>&1 &
    local pid=$!
    echo "  PID: $pid"
    echo "$pid" > ../data/pool-service.pid
    
    # 等待服务启动
    echo -n "  等待服务就绪"
    for i in {1..30}; do
        if curl -s http://localhost:8019/health > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}✅ 账号池服务已启动 (http://localhost:8019)${NC}"
            cd ..
            return 0
        fi
        echo -n "."
        sleep 2
    done
    
    echo ""
    echo -e "${RED}❌ 账号池服务启动失败，请检查日志: logs/pool-service.log${NC}"
    cd ..
    return 1
}

# 函数：启动Warp2API服务
start_warp2api() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}2️⃣  启动Warp2API服务...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    check_port 8000 "Warp2API服务" || return 1
    
    cd warp2api-main
    
    # 启动服务
    if [ -f "server.py" ]; then
        nohup python3 server.py > ../logs/warp2api.log 2>&1 &
    elif [ -f "main.py" ]; then
        nohup python3 main.py > ../logs/warp2api.log 2>&1 &
    else
        echo -e "${RED}❌ 找不到启动文件${NC}"
        cd ..
        return 1
    fi
    
    local pid=$!
    echo "  PID: $pid"
    echo "$pid" > ../data/warp2api.pid
    
    # 等待服务启动
    echo -n "  等待服务就绪"
    for i in {1..30}; do
        if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}✅ Warp2API服务已启动 (http://localhost:8000)${NC}"
            cd ..
            return 0
        fi
        echo -n "."
        sleep 2
    done
    
    echo ""
    echo -e "${RED}❌ Warp2API服务启动失败，请检查日志: logs/warp2api.log${NC}"
    cd ..
    return 1
}

# 函数：显示服务状态
show_status() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}📊 服务状态${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # 检查账号池服务
    if curl -s http://localhost:8019/health > /dev/null 2>&1; then
        echo -e "🔹 账号池服务:  ${GREEN}✓ 运行中${NC}"
    else
        echo -e "🔹 账号池服务:  ${RED}✗ 未运行${NC}"
    fi
    
    # 检查Warp2API服务
    if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
        echo -e "🔹 Warp2API服务: ${GREEN}✓ 运行中${NC}"
    else
        echo -e "🔹 Warp2API服务: ${RED}✗ 未运行${NC}"
    fi
}

# 函数：创建系统服务文件（可选）
create_systemd_service() {
    echo -e "${YELLOW}🔧 是否创建systemd服务文件? [y/N]: ${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "创建systemd服务文件..."
        # 这里可以添加systemd服务文件的创建逻辑
        echo "请手动配置systemd服务文件"
    fi
}

# 函数：启动OpenAI兼容服务
start_openai_service() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}3️⃣  启动OpenAI兼容服务...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    check_port 8010 "OpenAI兼容服务" || return 1
    
    cd warp2api-main
    # 重要：设置HOST为0.0.0.0以便Docker容器访问
    export HOST="0.0.0.0"
    export PORT="8010"
    export WARP_BRIDGE_URL="http://localhost:8000"
    
    nohup python3 start.py > ../logs/openai-compat.log 2>&1 &
    local pid=$!
    echo $pid > ../data/openai-compat.pid
    cd ..
    
    echo "  PID: $pid"
    
    # 等待服务就绪
    echo -n "  等待服务就绪"
    local count=0
    while [ $count -lt 10 ]; do
        if kill -0 $pid 2>/dev/null; then
            echo -n "."
            sleep 1
            count=$((count + 1))
        else
            echo -e "\n${RED}❌ OpenAI兼容服务启动失败${NC}"
            return 1
        fi
    done
    
    echo -e "\n${GREEN}✅ OpenAI兼容服务已启动 (http://0.0.0.0:8010)${NC}"
    return 0
}

# 主函数
main() {
    # 检查环境
    check_python
    
    # 安装依赖
    install_dependencies
    
    echo ""
    echo -e "${GREEN}🚀 开始启动生产环境服务...${NC}"
    echo ""
    
    # 启动账号池服务
    if ! start_pool_service; then
        echo -e "${RED}❌ 启动失败${NC}"
        exit 1
    fi
    
    echo ""
    
    # 启动Warp2API服务
    if ! start_warp2api; then
        echo -e "${RED}❌ 启动失败${NC}"
        exit 1
    fi
    
    echo ""
    
    # 启动OpenAI兼容服务
    if ! start_openai_service; then
        echo -e "${YELLOW}⚠️  OpenAI兼容服务启动失败，但其他服务正常${NC}"
    fi
    
    echo ""
    
    # 显示状态
    show_status
    
    echo ""
    
    # 可选：创建系统服务
    create_systemd_service
    
    echo ""
    echo -e "${GREEN}✨ 生产环境服务启动完成！${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "📝 服务地址:"
    echo "  • Warp2API主服务: http://localhost:8000
  • OpenAI兼容API: http://0.0.0.0:8010 (Docker可访问)"
    echo "  • 账号池服务: http://localhost:8019"
    echo ""
    echo "📁 重要文件:"
    echo "  • 日志目录: ./logs/"
    echo "  • PID文件: ./data/*.pid"
    echo "  • 配置文件: ./config/production.env"
    echo ""
    echo "🔧 管理命令:"
    echo "  • 停止服务: ./stop_production.sh"
    echo "  • 查看日志: tail -f logs/warp2api.log"
    echo ""
}

# 执行主函数

# 在主函数前添加OpenAI服务启动调用
main
# 函数：启动OpenAI兼容服务
