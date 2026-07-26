# 「LMSログから学習と授業を読み解く」合成データ生成
# 実在する学生・授業・LMS の記録は使用していません。

library(tidyverse)

args <- commandArgs(trailingOnly = TRUE)
output_dir <- if (length(args) >= 1) args[[1]] else "../../assets/data"
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

course_design <- tribble(
  ~activity_key, ~week, ~activity_type, ~title, ~required, ~graded, ~points, ~due_day, ~pedagogical_intent,
  "A01", 1, "orientation", "学習目標と進め方の確認", "yes", "no", 0, "none", "学習の見通しを持つ",
  "A02", 1, "material", "概念解説を読む", "yes", "no", 0, "none", "基礎概念を獲得する",
  "A03", 1, "quiz", "理解確認クイズ", "yes", "yes", 5, "Sunday", "誤概念を早期に確認する",
  "A04", 2, "material", "事例動画を視聴する", "yes", "no", 0, "none", "概念を具体例と結びつける",
  "A05", 2, "forum", "事例への見解を投稿する", "yes", "yes", 5, "Sunday", "複数の見方を比較する",
  "A06", 2, "assignment", "短い振り返りを書く", "yes", "yes", 10, "Sunday", "自分の理解を言語化する",
  "A07", 3, "material", "応用課題の説明を読む", "yes", "no", 0, "none", "課題の要件を理解する",
  "A08", 3, "workshop", "同期ワークショップに参加する", "no", "no", 0, "Wednesday", "協働で問いを精緻化する",
  "A09", 3, "assignment", "中間課題を提出する", "yes", "yes", 20, "Sunday", "概念を実際の課題へ適用する",
  "A10", 4, "feedback", "中間課題のフィードバックを読む", "yes", "no", 0, "none", "改善点を次の学習へつなげる",
  "A11", 4, "material", "発展資料を選んで読む", "no", "no", 0, "none", "関心に応じて理解を広げる",
  "A12", 4, "quiz", "再確認クイズ", "yes", "yes", 5, "Sunday", "理解の修正を確認する",
  "A13", 5, "case", "複合事例を分析する", "yes", "no", 0, "none", "複数の観点を統合する",
  "A14", 5, "forum", "分析方針を相互検討する", "yes", "yes", 5, "Sunday", "根拠と反例を吟味する",
  "A15", 5, "assignment", "最終課題案を提出する", "yes", "yes", 15, "Sunday", "形成的フィードバックを得る",
  "A16", 6, "feedback", "相互フィードバックを行う", "yes", "yes", 10, "Wednesday", "評価基準を用いて改善する",
  "A17", 6, "assignment", "最終課題を提出する", "yes", "yes", 30, "Sunday", "学習成果を統合して示す",
  "A18", 6, "reflection", "学習プロセスを振り返る", "yes", "no", 0, "Sunday", "今後の学習方略を計画する"
)

learners <- tibble(
  learner_n = 1:60,
  learner_key = sprintf("S%03d", learner_n),
  study_schedule = if_else(learner_n %% 3 == 0, "evening", "daytime"),
  prior_lms_experience = if_else(learner_n %% 4 %in% c(0, 1), "low", "high"),
  profile = case_when(
    learner_n %% 11 == 0 ~ "efficient",
    learner_n %% 13 == 0 ~ "struggling_active",
    TRUE ~ "typical"
  )
)

learner_week <- crossing(learners, week = 1:6) |>
  mutate(
    base_events = 18 + ((learner_n * 7 + week * 3) %% 12),
    course_demand = case_when(week == 3 ~ 6, week == 5 ~ 3, TRUE ~ 0),
    event_count = base_events + course_demand +
      if_else(profile == "efficient", -10L, 0L) +
      if_else(profile == "struggling_active", 12L, 0L) +
      if_else(prior_lms_experience == "low", 3L, 0L),
    event_count = pmax(2L, event_count),
    active_days = pmin(6L, pmax(1L, 1L + event_count %/% 8L + ((learner_n + week) %% 2L))),
    material_views = pmax(1L, round(event_count * 0.45)),
    quiz_attempts = 1L + ((learner_n + week) %% 3L),
    assignments_due = 1L,
    pressure = (learner_n * 3 + week * 5) %% 10,
    submitted = !(pressure == 9 & week >= 4 & profile != "efficient"),
    late = pressure >= 8 |
      (week == 3 & pressure >= 6) |
      (profile == "struggling_active" & week %in% 3:5),
    late = if_else(profile == "efficient", FALSE, late),
    assignments_submitted = as.integer(submitted),
    assignments_on_time = as.integer(submitted & !late),
    late_submissions = as.integer(submitted & late),
    avg_score = 72 + ((learner_n * 5 + week * 2) %% 17) - 8 +
      if_else(profile == "efficient", 12, 0) +
      if_else(profile == "struggling_active", -18, 0) +
      if_else(prior_lms_experience == "high", 4, 0) -
      if_else(week == 3, 4, 0),
    avg_score = pmin(98, pmax(35, avg_score)),
    forum_posts = (learner_n + week * 2) %% 4,
    support_request = as.integer(
      ((learner_n + week * 2) %% 17 == 0) |
        (profile == "struggling_active" & week >= 2)
    )
  ) |>
  arrange(learner_n, week) |>
  select(
    learner_key, study_schedule, prior_lms_experience, week,
    event_count, active_days, material_views, quiz_attempts,
    assignments_due, assignments_submitted, assignments_on_time,
    late_submissions, avg_score, forum_posts, support_request
  )

early <- learner_week |>
  filter(week <= 3) |>
  group_by(learner_key, study_schedule) |>
  summarise(
    on_time_rate_w1_3 = mean(assignments_on_time),
    mean_score_w1_3 = mean(avg_score),
    active_days_w1_3 = sum(active_days),
    .groups = "drop"
  ) |>
  mutate(
    risk_score_rule = 1 - (
      0.45 * on_time_rate_w1_3 +
        0.30 * mean_score_w1_3 / 100 +
        0.25 * pmin(active_days_w1_3 / 18, 1)
    )
  ) |>
  arrange(desc(risk_score_rule), learner_key) |>
  mutate(selected = row_number() <= 15)

later <- learner_week |>
  filter(week >= 4) |>
  group_by(learner_key) |>
  summarise(
    future_on_time_rate = mean(assignments_on_time),
    final_score = avg_score[week == 6],
    .groups = "drop"
  )

intervention <- early |>
  left_join(later, by = "learner_key") |>
  mutate(
    contacted = selected,
    reached = selected & (study_schedule == "daytime" | as.integer(str_remove(learner_key, "S")) %% 4 == 0),
    consultation_completed = reached & as.integer(str_remove(learner_key, "S")) %% 3 != 0,
    assigned_action = if_else(selected, "individual_consultation", "universal_resources"),
    contact_channel = if_else(selected, "daytime_video_call", "course_announcement"),
    risk_score_rule = round(risk_score_rule, 4),
    future_on_time_rate = round(future_on_time_rate, 3)
  ) |>
  select(
    learner_key, study_schedule, risk_score_rule, selected, contacted,
    reached, consultation_completed, assigned_action, contact_channel,
    future_on_time_rate, final_score
  )

write_csv(course_design, file.path(output_dir, "course-design.csv"))
write_csv(learner_week, file.path(output_dir, "learner-week.csv"))
write_csv(intervention, file.path(output_dir, "intervention.csv"))

message("合成データを書き出しました: ", normalizePath(output_dir))
