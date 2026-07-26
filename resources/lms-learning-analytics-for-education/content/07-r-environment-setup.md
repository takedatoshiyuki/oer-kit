---
title: "R実行環境の構築"
lang: ja
toc: true
---

このページでは、教材のRスクリプトを実行するための環境をmacOSとWindowsに準備します。
Rを初めて使う場合は、CRAN公式インストーラーとRStudio Desktopを使う方法が分かりやすいです。

## 必要なもの

- R 4.4以降
- 任意：RStudio Desktop
- Rパッケージ：`tidyverse`、`lubridate`、`broom`、`yardstick`
- 教材フォルダー一式

RStudioはR本体とは別の操作画面です。先にRをインストールしてからRStudioを導入してください。

## macOS：CRAN公式インストーラーを使う

### 1. Macの種類を確認する

画面左上のAppleメニューから「このMacについて」を開きます。

- チップにM1、M2、M3、M4等と表示：Apple silicon版
- プロセッサにIntelと表示：Intel版

### 2. Rをインストールする

[CRANのR for macOS](https://cran.r-project.org/bin/macosx/)から、Macの種類に合う`.pkg`を取得して実行します。
通常は標準設定のままで構いません。

ターミナルで確認します。

```bash
Rscript --version
```

バージョンが表示されればR本体の準備は完了です。

### 3. RStudioをインストールする（任意）

[RStudio Desktopの公式案内](https://docs.posit.co/ide/user/#rstudio-ide-oss-downloads)からmacOS版を取得し、
アプリケーションフォルダーへ追加します。

### 4. 教材用Rパッケージをインストールする

ターミナルで次を実行します。

```bash
Rscript -e 'lib <- path.expand(Sys.getenv("R_LIBS_USER")); dir.create(lib, recursive=TRUE, showWarnings=FALSE); .libPaths(c(lib, .libPaths())); install.packages(c("tidyverse", "lubridate", "broom", "yardstick"), lib=lib, repos="https://cloud.r-project.org")'
```

CRAN公式版Rでバイナリパッケージが提供されている場合、通常はOS側の追加ライブラリを準備せずに導入できます。

## macOS：Homebrew版Rを使う場合

すでにHomebrew版Rを使っている場合、画像・文字描画パッケージをソースからコンパイルするために
OS側のライブラリが必要になることがあります。

```bash
brew install r pkgconf harfbuzz fribidi libtiff
```

依存ライブラリを確認します。

```bash
pkg-config --cflags harfbuzz freetype2 fribidi
pkg-config --cflags libtiff-4 libwebp libwebpmux
```

エラーがなければ、前節の`install.packages()`を実行します。

### macOSでよくあるエラー

| 表示 | 原因 | 対応 |
|---|---|---|
| `there is no package called 'tidyverse'` | パッケージが未導入、または保存先がRから見えない | ユーザー用ライブラリを作成して再インストール |
| `hb-ft.h file not found` | HarfbuzzまたはFribidiがない | `brew install harfbuzz fribidi` |
| `tiffio.h file not found` | libtiffがない | `brew install libtiff` |
| `library is not writable` | システムライブラリに書き込もうとしている | `R_LIBS_USER`で示されるユーザー用ライブラリを使う |

`sudo R`や`sudo Rscript`は使わないでください。パッケージは利用者ごとのライブラリへ導入します。

## Windows

### 1. Rをインストールする

[CRANのR for Windows](https://cran.r-project.org/bin/windows/base/)から64-bit版インストーラーを取得します。
インストーラーを起動し、特別な指定がなければ標準設定で進めます。

PowerShellまたはコマンドプロンプトを開き、確認します。

```powershell
Rscript --version
```

`Rscript`が見つからない場合は、いったんWindowsからサインアウトして入り直すか、
RStudioのConsoleから以降のRコードを実行してください。

### 2. RStudioをインストールする（任意）

[RStudio Desktopの公式案内](https://docs.posit.co/ide/user/#rstudio-ide-oss-downloads)からWindows版を取得して
インストールします。

### 3. 教材用Rパッケージをインストールする

PowerShellで次を実行します。

```powershell
Rscript -e 'lib <- path.expand(Sys.getenv("R_LIBS_USER")); dir.create(lib, recursive=TRUE, showWarnings=FALSE); .libPaths(c(lib, .libPaths())); install.packages(c("tidyverse", "lubridate", "broom", "yardstick"), lib=lib, repos="https://cloud.r-project.org")'
```

または、RStudioのConsoleへ次を入力します。

```r
install.packages(
  c("tidyverse", "lubridate", "broom", "yardstick"),
  repos = "https://cloud.r-project.org"
)
```

Windowsでは通常、CRANが提供するバイナリパッケージが使われます。ソースからのコンパイルを求められた場合だけ、
利用中のRに合う[Rtools](https://cran.r-project.org/bin/windows/Rtools/)を導入してください。

### Windowsでよくあるエラー

| 表示・状況 | 対応 |
|---|---|
| `Rscript`が認識されない | RStudioから実行するか、Rの`bin`フォルダーをPATHへ追加 |
| パッケージを更新できない | RStudioとRを再起動し、パッケージを読み込んでいない状態で再実行 |
| `00LOCK`フォルダーに関するエラー | Rをすべて終了し、表示されたライブラリ内の該当`00LOCK`だけを削除して再実行 |
| コンパイラがない | CRANバイナリを選ぶ。ソース導入が必要なら対応するRtoolsを導入 |

## 共通の動作確認

教材の`content/R`フォルダーを作業ディレクトリにして、環境確認スクリプトを実行します。

macOSのターミナル：

```bash
cd "/教材を保存した場所/lms-learning-analytics-for-education/content/R"
Rscript 03-check-environment.R
```

Windows PowerShell：

```powershell
cd "C:\教材を保存した場所\lms-learning-analytics-for-education\content\R"
Rscript 03-check-environment.R
```

最後に`教材を実行できる環境です`と表示されれば準備完了です。

## 教材を実行する

同じ`content/R`フォルダーで実行します。

```bash
Rscript 00-generate-data.R
Rscript 01-beginner.R
Rscript 02-intermediate.R
Rscript 04-masters-extension.R
```

`00-generate-data.R`は`assets/data`の合成CSVを再生成します。
`01-beginner.R`をターミナルから実行すると、グラフは作業フォルダーの`Rplots.pdf`へ保存されます。
`04-masters-extension.R`は、修士発展編を実施する場合に使用します。

RStudioを使う場合は、各スクリプトを開き、上から順に実行してください。
相対パスを使っているため、最初に`content/R`を作業ディレクトリとして設定します。

## 確認情報を共有する

問題を報告するときは、個人情報や実データを添付せず、次の出力を共有してください。

```r
sessionInfo()
.libPaths()
Sys.getenv("R_LIBS_USER")
```

エラーメッセージは、最初の`ERROR`から末尾までを共有すると原因を特定しやすくなります。
