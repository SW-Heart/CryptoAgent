# ===========================================
# CryptoQuant - Makefile
# ===========================================

.PHONY: help dev dev-server dev-web build deploy test clean

# Default target
help: ## 显示帮助信息
	@echo ""
	@echo "CryptoQuant 常用命令："
	@echo "─────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─── Development ──────────────────────────

dev-server: ## 启动后端开发服务器
	cd server && fastapi dev main.py

dev-web: ## 启动前端开发服务器
	cd web && npm run dev

dev: ## 同时启动前后端（后台）
	@echo "Starting backend..."
	cd server && fastapi dev main.py &
	@echo "Starting frontend..."
	cd web && npm run dev

# ─── Build & Deploy ──────────────────────

build-web: ## 构建前端生产包
	cd web && npm run build

build-docker: ## 构建 Docker 镜像
	docker build -f deploy/Dockerfile -t cryptoquant:latest .

deploy: ## 使用 docker-compose 部署
	cd deploy && docker-compose up -d

deploy-down: ## 停止 docker-compose 服务
	cd deploy && docker-compose down

# ─── Testing ─────────────────────────────

test: ## 运行后端测试
	cd server && python -m pytest tests/ -v

lint-web: ## 前端代码检查
	cd web && npm run lint

# ─── Utilities ───────────────────────────

clean: ## 清理构建产物和缓存
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf web/dist
	@echo "✅ 清理完成"

db-reset: ## 重置数据库
	cd server && python reset_data.py

install: ## 安装所有依赖
	cd server && pip install -r requirements.txt
	cd web && npm install
