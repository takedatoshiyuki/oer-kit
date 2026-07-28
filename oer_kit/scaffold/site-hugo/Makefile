# oer-kit を使う OER プロジェクトのビルド (Hugo エンジン)。使い方: make site / make preview
# oer-kit を pip インストールしていない場合はパスを指定する:
#   make site OER_KIT=../oer-kit
OER_KIT ?=
PY = $(if $(OER_KIT),PYTHONPATH=$(OER_KIT) )python -m
HUGO ?= hugo

.PHONY: validate prerender render catalog site preview clean

validate:            ## metadata.yaml の検証
	$(PY) oer_kit.validate

prerender:           ## metadata.yaml → site/content/r/ のページ生成 (+ hugo.yaml)
	$(PY) oer_kit.prerender

render: prerender    ## Hugo で site/_site へレンダリング → _site/ へ同期
	cd site && $(HUGO) --quiet
	rsync -a --delete --exclude catalog.json --exclude jsonld --exclude .nojekyll \
	  site/_site/ _site/

catalog:             ## catalog.json + JSON-LD 全件 (+ sitemap は Hugo 優先)
	$(PY) oer_kit.build_catalog

site: validate render catalog  ## 検証 → レンダリング → カタログ (公開一式)

preview: prerender   ## ローカルプレビュー
	cd site && $(HUGO) server

clean:
	rm -rf _site site/_site site/content/r site/hugo.yaml
