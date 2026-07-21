# 公開一式のビルド。使い方: make site / make preview
QUARTO ?= quarto

.PHONY: validate prerender render catalog site preview clean

validate:            ## metadata.yaml の検証
	python3 tools/validate.py

prerender:           ## metadata.yaml → site/r/ のページ生成 (+ _quarto.yml)
	python3 tools/prerender.py

render: prerender    ## Quarto で _site/ へレンダリング
	$(QUARTO) render site

catalog:             ## catalog.json + JSON-LD 全件 (+ sitemap は Quarto 優先)
	python3 tools/build_catalog.py

site: validate render catalog  ## 検証 → レンダリング → カタログ (公開一式)

preview: prerender   ## ローカルプレビュー
	$(QUARTO) preview site

clean:
	rm -rf _site site/r site/_quarto.yml site/.quarto
