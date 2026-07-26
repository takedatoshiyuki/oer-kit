# 教材用R環境の確認
# content/R を作業ディレクトリとして実行してください。

required_packages <- c("tidyverse", "lubridate", "broom", "yardstick")
installed <- rownames(installed.packages())
missing_packages <- setdiff(required_packages, installed)

cat("R:", R.version.string, "\n")
cat("Platform:", R.version$platform, "\n")
cat("Library paths:\n")
writeLines(paste0("  - ", .libPaths()))

if (length(missing_packages) > 0) {
  stop(
    "不足しているパッケージ: ",
    paste(missing_packages, collapse = ", "),
    "\n07-r-environment-setup.md の手順でインストールしてください。"
  )
}

cat("Packages:\n")
for (package in required_packages) {
  cat("  -", package, as.character(packageVersion(package)), "\n")
}

data_files <- file.path(
  "../../assets/data",
  c("course-design.csv", "learner-week.csv", "intervention.csv")
)

if (!all(file.exists(data_files))) {
  stop(
    "教材データが見つかりません。\n",
    "content/R を作業ディレクトリにしているか確認してください。"
  )
}

learner_week <- readr::read_csv(
  "../../assets/data/learner-week.csv",
  show_col_types = FALSE
)

if (nrow(learner_week) != 360L ||
    dplyr::n_distinct(learner_week$learner_key) != 60L ||
    dplyr::n_distinct(learner_week$week) != 6L) {
  stop("learner-week.csv の行数、学習者数、または週数が想定と異なります。")
}

cat("Data: 60 learners × 6 weeks = 360 rows\n")
cat("教材を実行できる環境です\n")
