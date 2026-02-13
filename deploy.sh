#!/bin/bash

# ============================================================
# AGORA AI Debate Arena - 生产环境部署脚本
# ============================================================
# 使用方法:
#   ./deploy.sh [命令]
#
# 命令:
#   build     - 构建 Docker 镜像
#   up        - 启动服务
#   down      - 停止服务
#   restart   - 重启服务
#   logs      - 查看日志
#   db-init   - 初始化数据库
#   db-backup - 备份数据库
#   db-restore - 恢复数据库
#   update    - 更新部署
#   status    - 查看服务状态
#   clean     - 清理旧镜像和容器
#   all       - 完整部署 (build + up + db-init)
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目配置
PROJECT_NAME="agora-ai"
DOCKER_COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
BACKUP_DIR="./backups"
LOG_DIR="./logs"

# 打印信息函数
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查必要文件
check_files() {
    if [ ! -f "$ENV_FILE" ]; then
        print_error "环境变量文件 $ENV_FILE 不存在"
        print_info "请先复制 .env.example 为 .env 并配置"
        exit 1
    fi

    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        print_error "Docker Compose 文件 $DOCKER_COMPOSE_FILE 不存在"
        exit 1
    fi
}

# 创建必要目录
create_dirs() {
    print_info "创建必要目录..."
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "./uploads"
    mkdir -p "./static"
    mkdir -p "./ssl"
    print_success "目录创建完成"
}

# 构建 Docker 镜像
build_image() {
    print_info "开始构建 Docker 镜像..."
    docker-compose build --no-cache
    print_success "Docker 镜像构建完成"
}

# 启动服务
start_services() {
    print_info "启动服务..."
    docker-compose up -d
    print_success "服务启动完成"
    print_info "等待服务就绪..."
    sleep 10
}

# 停止服务
stop_services() {
    print_info "停止服务..."
    docker-compose down
    print_success "服务已停止"
}

# 重启服务
restart_services() {
    print_info "重启服务..."
    docker-compose restart
    print_success "服务已重启"
}

# 查看日志
view_logs() {
    local service=$1
    if [ -z "$service" ]; then
        print_info "查看所有服务日志..."
        docker-compose logs -f
    else
        print_info "查看 $service 服务日志..."
        docker-compose logs -f "$service"
    fi
}

# 查看状态
check_status() {
    print_info "服务状态:"
    docker-compose ps
    print_info "容器资源使用:"
    docker stats --no-stream
}

# 初始化数据库
init_database() {
    print_info "初始化数据库..."
    docker-compose exec -T app python init_db.py || true
    print_success "数据库初始化完成"
}

# 备份数据库
backup_database() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_file="$BACKUP_DIR/db_backup_$timestamp.sql"

    print_info "备份数据库到 $backup_file..."
    docker-compose exec -T postgres pg_dump -U "$(grep DB_USER $ENV_FILE | cut -d '=' -f2)" "$(grep DB_NAME $ENV_FILE | cut -d '=' -f2)" > "$backup_file"
    gzip "$backup_file"
    print_success "数据库备份完成: ${backup_file}.gz"
}

# 恢复数据库
restore_database() {
    local backup_file=$1

    if [ -z "$backup_file" ]; then
        print_error "请指定备份文件"
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        print_error "备份文件不存在: $backup_file"
        exit 1
    fi

    print_warning "即将恢复数据库，这将覆盖现有数据！"
    read -p "确认继续? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        print_info "已取消恢复操作"
        exit 0
    fi

    print_info "从 $backup_file 恢复数据库..."
    if [[ $backup_file == *.gz ]]; then
        gunzip -c "$backup_file" | docker-compose exec -T postgres psql -U "$(grep DB_USER $ENV_FILE | cut -d '=' -f2)" "$(grep DB_NAME $ENV_FILE | cut -d '=' -f2)"
    else
        docker-compose exec -T postgres psql -U "$(grep DB_USER $ENV_FILE | cut -d '=' -f2)" "$(grep DB_NAME $ENV_FILE | cut -d '=' -f2)" < "$backup_file"
    fi
    print_success "数据库恢复完成"
}

# 更新部署
update_deployment() {
    print_info "更新部署..."
    print_info "1. 拉取最新代码"
    git pull || print_warning "Git 拉取失败或不是 Git 仓库"

    print_info "2. 重新构建镜像"
    docker-compose build

    print_info "3. 重启服务"
    docker-compose up -d

    print_success "更新部署完成"
}

# 清理旧镜像和容器
clean_resources() {
    print_info "清理未使用的资源..."
    docker system prune -f
    docker volume prune -f
    print_success "清理完成"
}

# 健康检查
health_check() {
    print_info "执行健康检查..."

    # 检查 Postgres
    if docker-compose exec -T postgres pg_isready -U "$(grep DB_USER $ENV_FILE | cut -d '=' -f2)" > /dev/null 2>&1; then
        print_success "PostgreSQL: 健康"
    else
        print_error "PostgreSQL: 不健康"
    fi

    # 检查 Redis
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        print_success "Redis: 健康"
    else
        print_error "Redis: 不健康"
    fi

    # 检查应用
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        print_success "应用: 健康"
    else
        print_error "应用: 不健康"
    fi
}

# 显示帮助
show_help() {
    cat << EOF
AGORA AI Debate Arena - 部署脚本

使用方法: ./deploy.sh [命令]

命令:
  build         - 构建 Docker 镜像
  up            - 启动服务
  down          - 停止服务
  restart       - 重启服务
  logs [service]- 查看日志
  status        - 查看服务状态
  db-init       - 初始化数据库
  db-backup     - 备份数据库
  db-restore    - 恢复数据库 (需要指定备份文件)
  update        - 更新部署
  clean         - 清理旧镜像和容器
  health        - 健康检查
  all           - 完整部署 (build + up + db-init)
  help          - 显示此帮助信息

示例:
  ./deploy.sh all                    # 完整部署
  ./deploy.sh up                     # 启动服务
  ./deploy.sh logs app               # 查看应用日志
  ./deploy.sh db-backup              # 备份数据库
  ./deploy.sh db-restore backups/db_backup_20240101_120000.sql.gz

EOF
}

# 主函数
main() {
    local command=$1
    shift || true

    case "$command" in
        build)
            check_files
            build_image
            ;;
        up)
            check_files
            create_dirs
            start_services
            ;;
        down)
            check_files
            stop_services
            ;;
        restart)
            check_files
            restart_services
            ;;
        logs)
            check_files
            view_logs "$1"
            ;;
        status)
            check_files
            check_status
            ;;
        db-init)
            check_files
            init_database
            ;;
        db-backup)
            check_files
            create_dirs
            backup_database
            ;;
        db-restore)
            check_files
            restore_database "$1"
            ;;
        update)
            check_files
            update_deployment
            ;;
        clean)
            clean_resources
            ;;
        health)
            check_files
            health_check
            ;;
        all)
            check_files
            create_dirs
            build_image
            start_services
            init_database
            health_check
            print_success "完整部署完成！"
            ;;
        help|--help|-h|"")
            show_help
            ;;
        *)
            print_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
