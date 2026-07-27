.PHONY: doctor test demo build package typecheck clean
PY ?= python3

doctor:          ## 环境体检:版本 / 证书 / 依赖 / 校验服务能力
	$(PY) scripts/doctor.py

test:            ## 跑全部回归套件(需网络) —— 清单见 tests/SUITES
	@fail=0; for t in $$(sed 's/#.*//' tests/SUITES | tr -d '[:blank:]' | grep .); do \
		printf "%-18s " $$t; \
		if out=$$($(PY) tests/$$t.py 2>&1); then echo "$$out" | tail -1; \
		else echo "FAILED"; echo "$$out" | sed 's/^/    /'; fail=1; fi; \
	done; exit $$fail

demo:            ## 端到端演示:多进程链路 + 飞轮闭环
	@bash demo.sh

build:           ## 构建 Python wheel
	$(PY) -m build --wheel

typecheck:       ## TS 大脑类型检查
	cd orchestrator-ts && npm i && npm run typecheck

package: build   ## 全量打包(wheel + TS bundle + 提示 Tauri)
	@echo "→ TS orchestrator 打单文件:cd orchestrator-ts && npx esbuild src/server.ts --bundle --platform=node --outfile=dist/server.cjs"
	@echo "→ Tauri 安装包:cd apps/shell && npm run tauri build"

clean:
	rm -rf dist orchestrator-ts/dist *.db /tmp/*.db __pycache__ */__pycache__
