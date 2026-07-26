# 初級編：LMSログから授業を見直す
# 作業ディレクトリは content/R を想定しています。

library(tidyverse)

learner_week <- read_csv(
  "../../assets/data/learner-week.csv",
  show_col_types = FALSE
)
course_design <- read_csv(
  "../../assets/data/course-design.csv",
  show_col_types = FALSE
)

# 1. まず授業設計を読む
course_design |>
  count(week, activity_type, graded)

# 2. 週ごとの傾向を把握する
weekly_summary <- learner_week |>
  group_by(week) |>
  summarise(
    learners = n_distinct(learner_key),
    median_events = median(event_count),
    median_active_days = median(active_days),
    on_time_rate = sum(assignments_on_time) / sum(assignments_due),
    mean_score = mean(avg_score),
    support_requests = sum(support_request),
    .groups = "drop"
  )

weekly_summary

weekly_summary |>
  ggplot(aes(week, on_time_rate)) +
  geom_line(linewidth = 1, colour = "#2166ac") +
  geom_point(size = 2.5, colour = "#2166ac") +
  scale_y_continuous(labels = scales::percent_format(accuracy = 1)) +
  labs(
    title = "期限内提出率の週次推移",
    subtitle = "変化を学習者の属性だけでなく授業設計と照合する",
    x = "週",
    y = "期限内提出率"
  ) +
  theme_minimal(base_size = 12)

# 3. 「活動量が少ない＝学習していない」という仮説の反例を探す
learner_summary <- learner_week |>
  group_by(learner_key, study_schedule) |>
  summarise(
    mean_events = mean(event_count),
    on_time_rate = mean(assignments_on_time),
    mean_score = mean(avg_score),
    .groups = "drop"
  )

event_cut <- quantile(learner_summary$mean_events, 0.25)
score_cut <- quantile(learner_summary$mean_score, 0.75)

counterexamples <- learner_summary |>
  filter(mean_events <= event_cut, mean_score >= score_cut)

counterexamples

# 4. 逆方向の反例も確認する
learner_summary |>
  filter(
    mean_events >= quantile(mean_events, 0.75),
    mean_score <= quantile(mean_score, 0.25)
  )

# ここから先は、数値を学生の評価に使うのではなく、
# 授業設計上の問いと、小さく検証可能な改善案へ翻訳します。
