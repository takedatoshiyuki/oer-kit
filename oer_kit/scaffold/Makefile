# oer-kit を使う OER プロジェクトのビルド。使い方: make site / make preview
# oer-kit を pip インストールしていない場合はパスを指定する:
#   make site OER_KIT=../oer-kit
OER_KIT ?=
PY = $(if $(OER_KIT),PYTHONPATH=$(OER_KIT) )python3 -m
QUARTO ?= quarto

.PHONY: validate prerender render catalog site preview clean

validate:            ## metadata.yaml の検証
	$(PY) oer_kit.validate

prerender:           ## metadata.yaml → site/r/ のページ生成 (+ _quarto.yml)
	$(PY) oer_kit.prerender

render: prerender    ## Quarto で _site/ へレンダリング
	$(QUARTO) render site

catalog:             ## catalog.json + JSON-LD 全件 (+ sitemap は Quarto 優先)
	$(PY) oer_kit.build_catalog

site: validate render catalog  ## 検証 → レンダリング → カタログ (公開一式)

preview: prerender   ## ローカルプレビュー
	$(QUARTO) preview site

clean:
	rm -rf _site site/r site/_quarto.yml site/.quarto
